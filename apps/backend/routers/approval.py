from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import logging
from datetime import datetime

from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from grafi.topics.topic_impl.in_workflow_input_topic import InWorkflowInputTopic
from grafi.topics.topic_impl.in_workflow_output_topic import InWorkflowOutputTopic

from db.session import SessionLocal
from db import repository as db_repo

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["approval"])

# In-memory storage for approval requests and topics
# In production, this should be replaced with proper persistent storage
approval_requests = {}
active_topics = {}

class ApprovalRequest(BaseModel):
    approval_id: str
    transaction_data: Dict[str, Any]
    timestamp: datetime
    message: str

class ApprovalResponse(BaseModel):
    approval_id: str
    approved: bool
    signed_transaction_hex: Optional[str] = None
    rejection_reason: Optional[str] = None

class PollResponse(BaseModel):
    has_requests: bool
    requests: List[ApprovalRequest] = []

class ApprovalSubmitResponse(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None

@router.get("/poll", response_model=PollResponse)
async def poll_approval_requests(request: Request):
    """
    Poll for pending approval requests from the deployment workflow
    """
    try:
        assistant = getattr(request.app.state, "assistant", None)
        
        if assistant is None:
            logger.error("Assistant not available for approval polling")
            return PollResponse(has_requests=False, requests=[])

        workflow = getattr(assistant, "workflow", None)
        if workflow is None:
            logger.error("Workflow not available for approval polling")
            return PollResponse(has_requests=False, requests=[])

        # Debug: Log all approval requests and their status
        logger.info(f"Total approval requests in memory: {len(approval_requests)}")
        for req_id, req_data in approval_requests.items():
            logger.info(f"  - {req_id}: processed={req_data.get('processed', False)}")
        
        pending_requests = [
            ApprovalRequest(**request_data) 
            for request_data in approval_requests.values()
            if not request_data.get("processed", False)
        ]
        
        logger.info(f"Returning {len(pending_requests)} pending approval requests")
        
        return PollResponse(
            has_requests=len(pending_requests) > 0,
            requests=pending_requests
        )

    except Exception as e:
        logger.error(f"Error polling approval requests: {e}")
        return PollResponse(has_requests=False, requests=[])

@router.post("/respond", response_model=ApprovalSubmitResponse)
async def submit_approval_response(approval_response: ApprovalResponse, request: Request):
    """
    Submit approval/rejection response back to the workflow
    """
    try:
        # Get the assistant from app state
        assistant = getattr(request.app.state, "assistant", None)
        
        if assistant is None:
            logger.error("Assistant not available for approval response")
            raise HTTPException(
                status_code=503, 
                detail="Smart contract assistant not available"
            )

        # Look up the original approval request to get workflow context
        approval_data = approval_requests.get(approval_response.approval_id)
        if not approval_data:
            logger.warning(f"Approval request {approval_response.approval_id} not found")
            logger.info(f"Available approval request IDs: {list(approval_requests.keys())}")
            return ApprovalSubmitResponse(
                success=False,
                message="Approval request not found",
                error=f"Unknown approval_id: {approval_response.approval_id}"
            )

        # Use the original conversation context to resume the workflow
        original_conversation_id = approval_data.get("conversation_id", uuid.uuid4().hex)
        original_invoke_id = approval_data.get("invoke_id", uuid.uuid4().hex)
        original_request_id = approval_data.get("assistant_request_id", uuid.uuid4().hex)

        invoke_context = InvokeContext(
            conversation_id=original_conversation_id,
            invoke_id=original_invoke_id,
            assistant_request_id=original_request_id,
        )

        # Mark the approval request as processed
        approval_data["processed"] = True

        # Check if wallet already broadcast the transaction (sendTransaction fallback)
        signed_hex = approval_response.signed_transaction_hex or ""
        already_broadcast = signed_hex.startswith("ALREADY_BROADCAST:")

        if approval_response.approved and already_broadcast:
            # Wallet already sent the tx — no need to resume workflow for broadcast
            tx_hash = signed_hex.replace("ALREADY_BROADCAST:", "")
            logger.info(f"Transaction already broadcast by wallet. Hash: {tx_hash}")

            # Save deployment record to DB
            try:
                db = SessionLocal()
                try:
                    deployment_details = approval_data.get("deployment_details", {})
                    db_repo.save_deployment(
                        session=db,
                        compilation_id_ref=None,
                        transaction_hash=tx_hash,
                        deployer_address=deployment_details.get("user_address"),
                        chain_id=deployment_details.get("chain_id", 11155111),
                        status="deployed",
                    )
                    logger.info(f"DB: Saved deployment with tx_hash {tx_hash}")
                finally:
                    db.close()
            except Exception as db_error:
                logger.error(f"DB: Error saving deployment: {db_error}")

            return ApprovalSubmitResponse(
                success=True,
                message=f"Transaction already broadcast by wallet. Hash: {tx_hash}"
            )

        # Format the approval response message
        if approval_response.approved and signed_hex:
            response_content = f"APPROVED: Deployment approved by user. Signed transaction: {signed_hex}"
        elif approval_response.approved:
            response_content = "APPROVED: Deployment approved by user. Please proceed with transaction preparation."
        else:
            reason = approval_response.rejection_reason or "User rejected deployment"
            response_content = f"REJECTED: {reason}"

        # Create message for the approval input topic
        approval_message = Message(
            role="user",
            content=response_content
        )

        # Get the paused event ID from the InWorkflowOutputTopic — required for workflow resume
        paused_event_id = approval_data.get("paused_event_id")
        consumed_ids = [paused_event_id] if paused_event_id else []

        # Create input event targeting the InWorkflowInputTopic to resume the paused workflow
        input_event = PublishToTopicEvent(
            invoke_context=invoke_context,
            publisher_name="approval_api",
            publisher_type="api",
            topic_name="deployment_approval_topic",
            data=[approval_message],
            consumed_event_ids=consumed_ids,
        )

        logger.info(f"Submitting approval response: {response_content[:100]}...")
        logger.info(f"Resuming workflow with conversation_id={original_conversation_id}, invoke_id={original_invoke_id}, paused_event_id={paused_event_id}")

        if approval_response.approved and signed_hex:
            # Resume the workflow by publishing to the InWorkflowInputTopic
            response_count = 0
            async for response_event in assistant.invoke(input_event):
                response_count += 1
                topic = getattr(response_event, 'topic_name', 'unknown')
                logger.info(f"Approval workflow event #{response_count} from '{topic}'")

            # After workflow resume, save deployment record if we have a signed tx
            try:
                db = SessionLocal()
                try:
                    deployment_details = approval_data.get("deployment_details", {})
                    db_repo.save_deployment(
                        session=db,
                        compilation_id_ref=None,
                        transaction_hash=None,  # tx_hash not available here; broadcast happens in workflow
                        deployer_address=deployment_details.get("user_address"),
                        chain_id=deployment_details.get("chain_id", 11155111),
                        status="pending",
                    )
                    logger.info(f"DB: Saved pending deployment record after workflow resume")
                finally:
                    db.close()
            except Exception as db_error:
                logger.error(f"DB: Error saving deployment after resume: {db_error}")
        else:
            logger.info("Rejection or no signed tx — workflow not resumed")

        logger.info("Approval response submitted successfully")

        return ApprovalSubmitResponse(
            success=True,
            message="Approval response submitted successfully"
        )

    except Exception as e:
        logger.error(f"Error submitting approval response: {e}")
        return ApprovalSubmitResponse(
            success=False,
            message="Failed to submit approval response",
            error=str(e)
        )

@router.post("/mock-request")
async def create_mock_approval_request():
    """
    Development endpoint to create mock approval requests for testing
    """
    try:
        approval_id = uuid.uuid4().hex
        mock_request = {
            "approval_id": approval_id,
            "transaction_data": {
                "to": None,
                "data": "0x608060405234801561001057600080fd5b50...",
                "gas": 2000000,
                "gasPrice": "10000000000",
                "chainId": 11155111,
                "value": "0"
            },
            "timestamp": datetime.now(),
            "message": "Mock deployment transaction ready for approval",
            "processed": False
        }
        
        approval_requests[approval_id] = mock_request
        
        logger.info(f"Created mock approval request: {approval_id}")
        
        return {
            "success": True,
            "approval_id": approval_id,
            "message": "Mock approval request created"
        }
        
    except Exception as e:
        logger.error(f"Error creating mock approval request: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/status")
async def get_approval_status():
    """
    Get the current status of the approval system
    """
    return {
        "active_requests": len([r for r in approval_requests.values() if not r.get("processed", False)]),
        "total_requests": len(approval_requests),
        "system_status": "active"
    }