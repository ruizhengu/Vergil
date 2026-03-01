from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import os
import logging
import uuid
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent

from deps.assistant import get_assistant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

class BroadcastTransactionRequest(BaseModel):
    signed_transaction_hex: str

class BroadcastTransactionResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

@router.post("/broadcast", response_model=BroadcastTransactionResponse)
async def broadcast_signed_transaction(request: BroadcastTransactionRequest, app_request: Request, assistant = Depends(get_assistant)):
    try:
        if assistant is None:
            logger.error("Assistant not available - running in fallback mode")
            raise HTTPException(
                status_code=503, 
                detail="Smart contract assistant not available. Please ensure the MCP server is running."
            )

        # Use the assistant to call the broadcast_signed_transaction MCP tool
        logger.info(f"Broadcasting signed transaction via assistant...")
        
        # Create invoke context
        invoke_context = InvokeContext(
            conversation_id=uuid.uuid4().hex,
            invoke_id=uuid.uuid4().hex,
            assistant_request_id=uuid.uuid4().hex,
        )
        
        # Format the message for the assistant
        broadcast_message = f"Please broadcast this signed transaction: {request.signed_transaction_hex}"
        input_data = [Message(role="user", content=broadcast_message)]
        
        # Create the proper input event for the assistant
        input_event = PublishToTopicEvent(
            invoke_context=invoke_context,
            publisher_name="transaction_api",
            publisher_type="api",
            topic_name="agent_input_topic",
            data=input_data,
            consumed_events=[]
        )
        
        # Send message to assistant
        response = await assistant.a_invoke(input_event)
        
        # Process the assistant's response
        assistant_response = ""
        async for message_batch in response:
            for message in message_batch:
                if message.content:
                    assistant_response += message.content + "\n"

        logger.info(f"Assistant broadcast response: {assistant_response[:200]}...")

        # Parse the response to extract transaction details
        if "success" in assistant_response.lower() and "transaction_hash" in assistant_response.lower():
            # Try to extract transaction hash and other details
            import re
            
            # Look for transaction hash in the response
            tx_hash_match = re.search(r'"transaction_hash":\s*"([^"]+)"', assistant_response)
            contract_addr_match = re.search(r'"contract_address":\s*"([^"]+)"', assistant_response)
            
            result_data = {}
            if tx_hash_match:
                result_data["transaction_hash"] = tx_hash_match.group(1)
            if contract_addr_match:
                result_data["contract_address"] = contract_addr_match.group(1)
            
            result_data["raw_response"] = assistant_response
            
            return BroadcastTransactionResponse(
                success=True,
                data=result_data
            )
        else:
            # Transaction failed
            return BroadcastTransactionResponse(
                success=False,
                error=f"Transaction broadcast failed: {assistant_response}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error broadcasting transaction: {e}")
        return BroadcastTransactionResponse(
            success=False,
            error=f"Internal server error: {str(e)}"
        )

@router.get("/status")
async def get_transaction_status(tx_hash: str):
    return {
        "transaction_hash": tx_hash,
        "status": "pending",
        "message": "Transaction status checking not yet implemented"
    }