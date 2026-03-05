import uuid
import sys
import os
import asyncio
import re
import json
import httpx

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from deps.assistant import get_assistant
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from memory.context import get_conversation_context
from models.agent_responses import FinalAgentResponse, DeploymentApprovalRequest
from models.deployment_agent_responses import DeploymentResult
from db.session import SessionLocal
from db import repository as db_repo

from routers.approval import approval_requests

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Base URL for MCP server REST endpoints (strip /mcp/ suffix)
MCP_SERVER_BASE = os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp/").replace("/mcp/", "").rstrip("/")


async def _fetch_mcp_transaction(compilation_id: str) -> Optional[dict]:
    """Fetch the full prepared transaction (with bytecode) from the MCP server."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MCP_SERVER_BASE}/api/transaction/{compilation_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data["transaction"]
    except Exception as e:
        print(f"[ChatAPI] Failed to fetch full transaction from MCP: {e}")
    return None


async def _fetch_mcp_compilation(compilation_id: str) -> Optional[dict]:
    """Fetch compilation data (abi, bytecode, source_code) from the MCP server."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MCP_SERVER_BASE}/api/compilation/{compilation_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data
    except Exception as e:
        print(f"[ChatAPI] Failed to fetch compilation from MCP: {e}")
    return None

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest, assistant = Depends(get_assistant)):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        conversation_id = chat_request.conversation_id or uuid.uuid4().hex
        message_id = uuid.uuid4().hex
        
        print(f"Backend API: Processing message: {chat_request.message[:50]}...")

        if not assistant:
            return ChatResponse(
                success=False,
                error="Assistant not initialized. Check backend logs for startup errors."
            )

        print("Backend API: Using orchestration assistant with MCP tools")

        try:
                invoke_context = InvokeContext(
                    conversation_id=conversation_id,
                    invoke_id=uuid.uuid4().hex,
                    assistant_request_id=message_id,
                )
                
                # get context
                conversation_history = await get_conversation_context(conversation_id)

                input_data = conversation_history + [Message(role="user", content=chat_request.message)]

                print("input_data", input_data)

                input_event = PublishToTopicEvent(
                    invoke_context=invoke_context,
                    publisher_name="chat_api",
                    publisher_type="api",
                    topic_name="agent_input_topic",
                    data=input_data,
                    consumed_events=[]
                )


                full_response = ""
                structured_response = {}
                final_status = "completed"
                deployment_request = False

                try:
                    response_count = 0
                    print(f"[ChatAPI] Starting assistant.invoke...", flush=True)
                    import time as _chat_time
                    _invoke_start = _chat_time.time()
                    async for response_event in assistant.invoke(input_event):
                        _elapsed = _chat_time.time() - _invoke_start
                        topic = getattr(response_event, 'topic_name', 'unknown')
                        print(f"[ChatAPI] Event #{response_count+1} from '{topic}' at {_elapsed:.1f}s", flush=True)
                        response_count += 1
                        
                        if hasattr(response_event, 'data') and response_event.data:
                            for message in response_event.data:

                                # if response_event.topic_name not in ["agent_output_topic", "deployment_request_topic"]:
                                #     print(f"Debug: Skipping message from intermediate topic: {response_event.topic_name}")
                                #     continue
                                
                                if hasattr(message, 'content') and message.content:
                                    parsed_content = None
                                    if isinstance(message.content, str):
                                        raw = message.content.strip()
                                        # Strip markdown code fences if present
                                        if raw.startswith("```json"):
                                            raw = raw[7:]
                                        elif raw.startswith("```"):
                                            raw = raw[3:]
                                        if raw.endswith("```"):
                                            raw = raw[:-3]
                                        raw = raw.strip()
                                        try:
                                            parsed_content = json.loads(raw)
                                        except json.JSONDecodeError:
                                            # Not valid JSON, use as plain string
                                            parsed_content = raw
                                    else:
                                        parsed_content = message.content
                                    print('parsed_content', str(parsed_content)[:200])
                                    print('parsed_content_type', type(parsed_content))

                                    # Handle DeploymentResult from deployment agent (has transaction_data field)
                                    if isinstance(parsed_content, dict) and 'transaction_data' in parsed_content and parsed_content.get('status') in ('ready_for_signing', 'compilation_failed', 'failed'):
                                        print(f"Debug: Processing DeploymentResult with status: {parsed_content['status']}")
                                        deployment_result = DeploymentResult(**parsed_content)
                                        deployment_request = True

                                        if deployment_result.status == "ready_for_signing":
                                            # Parse LLM-provided transaction metadata (no bytecode)
                                            tx_metadata = {}
                                            if deployment_result.transaction_data:
                                                try:
                                                    tx_metadata = json.loads(deployment_result.transaction_data)
                                                except (json.JSONDecodeError, TypeError):
                                                    tx_metadata = {}

                                            # Fetch the FULL transaction (with bytecode) from MCP server
                                            full_tx = None
                                            if deployment_result.compilation_id:
                                                full_tx = await _fetch_mcp_transaction(deployment_result.compilation_id)
                                            # Use full tx if available, fall back to LLM metadata
                                            tx_data = full_tx if full_tx else tx_metadata
                                            if full_tx:
                                                print(f"[ChatAPI] Using full transaction from MCP (data len: {len(str(tx_data.get('data', '')))})")
                                            else:
                                                print(f"[ChatAPI] WARNING: Using LLM-provided tx metadata (may lack bytecode)")

                                            # Fetch and save compilation data from MCP server
                                            if deployment_result.compilation_id:
                                                compilation_data = await _fetch_mcp_compilation(deployment_result.compilation_id)
                                                if compilation_data:
                                                    try:
                                                        comp_db = SessionLocal()
                                                        try:
                                                            db_repo.save_compilation(
                                                                session=comp_db,
                                                                compilation_id=deployment_result.compilation_id,
                                                                abi=compilation_data.get("abi"),
                                                                bytecode=compilation_data.get("bytecode"),
                                                                success=True,
                                                            )
                                                            print(f"DB: Saved compilation {deployment_result.compilation_id} with abi/bytecode")
                                                        finally:
                                                            comp_db.close()
                                                    except Exception as comp_db_err:
                                                        print(f"DB: Error saving compilation: {comp_db_err}")

                                            full_response = f"**Deployment Transaction Prepared**\n\n"
                                            full_response += f"**Compilation ID:** {deployment_result.compilation_id}\n"
                                            if deployment_result.estimated_gas:
                                                full_response += f"**Estimated Gas:** {deployment_result.estimated_gas:,}\n"
                                            if deployment_result.gas_price_gwei:
                                                full_response += f"**Gas Price:** {deployment_result.gas_price_gwei} gwei\n"
                                            full_response += f"**Chain:** Sepolia ({deployment_result.chain_id})\n"
                                            full_response += f"\n**Transaction Details:**\n```json\n{json.dumps(tx_metadata, indent=2)}\n```"
                                            full_response += "\n\nPlease approve the transaction in your connected wallet to complete the deployment."

                                            final_status = "pending_signature"
                                            structured_response = deployment_result.model_dump()

                                            # Create approval request for frontend polling — uses FULL tx with bytecode
                                            approval_id = f"deploy_{uuid.uuid4().hex}"
                                            approval_requests[approval_id] = {
                                                "approval_id": approval_id,
                                                "transaction_data": tx_data,
                                                "timestamp": datetime.now(),
                                                "contract_type": "Smart Contract",
                                                "deployment_details": {
                                                    "compilation_id": deployment_result.compilation_id,
                                                    "user_address": deployment_result.user_address,
                                                    "estimated_gas": deployment_result.estimated_gas,
                                                    "gas_price_gwei": deployment_result.gas_price_gwei,
                                                    "chain_id": deployment_result.chain_id or 11155111,
                                                },
                                                "estimated_gas": deployment_result.estimated_gas,
                                                "message": deployment_result.summary,
                                                "processed": False,
                                                "conversation_id": conversation_id,
                                                "invoke_id": invoke_context.invoke_id,
                                                "assistant_request_id": invoke_context.assistant_request_id,
                                                "paused_event_id": getattr(response_event, 'event_id', None),
                                            }
                                            print(f"Created deployment approval request: {approval_id}")
                                            print(f"Stored paused_event_id: {getattr(response_event, 'event_id', None)}")
                                        else:
                                            # compilation_failed or failed
                                            full_response = f"Deployment failed: {deployment_result.error or deployment_result.summary}"
                                            final_status = "failed"
                                            structured_response = deployment_result.model_dump()

                                    # Handle structured FinalAgentResponse - check for specific fields
                                    elif isinstance(parsed_content, dict) and 'status' in parsed_content and 'summary' in parsed_content:
                                        # This is a FinalAgentResponse
                                        final_response = FinalAgentResponse(**parsed_content)
                                        
                                        full_response = final_response.summary
                                        final_status = final_response.status
                                        structured_response = final_response.model_dump()
                                        
                                        # Add formatted results if present
                                        if final_response.results:
                                            # Parse results if it's a JSON string
                                            if isinstance(final_response.results, str):
                                                try:
                                                    results_dict = json.loads(final_response.results)
                                                    if "solidity_code" in results_dict:
                                                        full_response += f"\n\n```solidity\n{results_dict['solidity_code']}\n```"
                                                    else:
                                                        full_response += f"\n\nResults: {json.dumps(results_dict, indent=2)}"
                                                except json.JSONDecodeError:
                                                    full_response += f"\n\nResults: {final_response.results}"
                                            else:
                                                # Results is already a dict/object
                                                if "solidity_code" in final_response.results:
                                                    full_response += f"\n\n```solidity\n{final_response.results['solidity_code']}\n```"
                                                else:
                                                    full_response += f"\n\nResults: {json.dumps(final_response.results, indent=2)}"
                                        
                                        # Add artifacts info
                                        if final_response.artifacts:
                                            full_response += f"\n\nGenerated: {', '.join(final_response.artifacts)}"
                                        
                                        # Add warnings
                                        if final_response.warnings:
                                            full_response += f"\n\n⚠️ Warnings: {'; '.join(final_response.warnings)}"
                                    
                                    # Handle prepare_deployment_transaction response - check for MCP-specific fields
                                    elif isinstance(parsed_content, dict) and 'success' in parsed_content and 'transaction' in parsed_content:
                                        print(f"Debug: Processing MCP prepare_deployment response")
                                        mcp_response = parsed_content
                                        deployment_request = True
                                        
                                        if mcp_response.get('success'):
                                            # Create user-friendly deployment preparation message
                                            full_response = f"🔧 **Deployment Transaction Prepared**\n\n"
                                            full_response += f"**Contract Ready for Deployment**\n"
                                            if mcp_response.get('estimated_gas'):
                                                full_response += f"**Estimated Gas:** {mcp_response['estimated_gas']:,}\n"
                                            if mcp_response.get('gas_price_gwei'):
                                                full_response += f"**Gas Price:** {mcp_response['gas_price_gwei']} gwei\n"
                                            if mcp_response.get('chain_id'):
                                                full_response += f"**chain_id:** {mcp_response['chain_id']} gwei\n"
                                            if mcp_response.get('user_address'):
                                                full_response += f"**user_address:** {mcp_response['user_address']} gwei\n"
                                            
                                            # Include transaction for frontend to handle
                                            transaction_data = mcp_response.get('transaction', {})
                                            full_response += f"\n**Transaction Details:**\n```json\n{json.dumps(transaction_data, indent=2)}\n```"
                                            
                                            full_response += "\n\n🔔 **Ready to Sign:** Please approve the transaction in your connected wallet to complete the deployment."
                                            
                                            final_status = "pending_signature"
                                            structured_response = mcp_response

                                            # Extract transaction data from MCP response (not deployment_request object)
                                            transaction_data = mcp_response.get('transaction', {})
                                            transaction_data_str = str(transaction_data.get('data', ''))  # Use transaction data as key
                                            
                                            # Check if there's already a pending approval request for this transaction
                                            existing_approval = None
                                            for existing_id, existing_request in approval_requests.items():
                                                if (not existing_request.get("processed", False) and 
                                                    str(existing_request.get("transaction_data", {}).get('data', '')) == transaction_data_str):
                                                    existing_approval = existing_id
                                                    break
                                            
                                            if existing_approval:
                                                print(f"Found existing pending approval request: {existing_approval}")
                                                print("Skipping duplicate approval request creation")
                                            else:
                                                approval_id = f"chat_approval_{uuid.uuid4().hex}"
                                                
                                                approval_request_data = {
                                                    "approval_id": approval_id,
                                                    "transaction_data": transaction_data,
                                                    "timestamp": datetime.now(),
                                                    "contract_type": "Smart Contract",  # Generic since MCP response doesn't have contract_type
                                                    "deployment_details": {
                                                        "user_address": mcp_response.get('user_address'),
                                                        "estimated_gas": mcp_response.get('estimated_gas'),
                                                        "gas_price_gwei": mcp_response.get('gas_price_gwei'),
                                                        "chain_id": mcp_response.get('chain_id', 11155111)
                                                    },
                                                    "security_considerations": ["Verify transaction details before signing"],
                                                    "estimated_gas": mcp_response.get('estimated_gas'),
                                                    "message": "Smart contract deployment approval required",
                                                    "processed": False,
                                                    "conversation_id": conversation_id,
                                                    "invoke_id": invoke_context.invoke_id,
                                                    "assistant_request_id": invoke_context.assistant_request_id,
                                                    "paused_event_id": getattr(response_event, 'event_id', None),
                                                }

                                                approval_requests[approval_id] = approval_request_data
                                                print(f"Created MCP approval request: {approval_id}")
                                                print(f"Total approval requests now: {len(approval_requests)}")

                                        else:
                                            full_response = f"❌ **Deployment Failed**: {mcp_response.get('message', 'Unknown error occurred during deployment preparation')}"
                                            final_status = "failed"
                                            structured_response = mcp_response
                                    
                                    # Handle other structured responses or fallback to string
                                    else:
                                        print(f"Debug: Received content: {type(parsed_content)}")
                                        if full_response:
                                            full_response += "\n\n"
                                        full_response += str(parsed_content)
                                
                                elif hasattr(message, 'tool_calls') and message.tool_calls:
                                    print(f"Debug: Tool calls: {[(tc.function.name, tc.function.arguments) for tc in message.tool_calls]}")
                                else:
                                    print(f"Debug: Message with no structured content from {response_event.topic_name}")
                    
                    print(f"Debug: Full response: {full_response[:200]}...")

                    # Save to database
                    try:
                        db = SessionLocal()
                        try:
                            # Save contract if FinalAgentResponse contains solidity_code in results
                            if structured_response and isinstance(structured_response, dict):
                                results_data = structured_response.get("results")
                                if results_data:
                                    if isinstance(results_data, str):
                                        try:
                                            results_data = json.loads(results_data)
                                        except json.JSONDecodeError:
                                            results_data = None
                                    if isinstance(results_data, dict) and results_data.get("solidity_code"):
                                        db_repo.save_contract(
                                            session=db,
                                            conversation_id=conversation_id,
                                            contract_name=results_data.get("contract_name", "Contract"),
                                            solidity_code=results_data["solidity_code"],
                                            contract_type=results_data.get("contract_type"),
                                            parameters=results_data.get("extracted_params"),
                                        )
                                        print(f"DB: Saved contract for conversation {conversation_id}")

                                # Save compilation if results contain compilation_id
                                if isinstance(results_data, dict) and results_data.get("compilation_id"):
                                    db_repo.save_compilation(
                                        session=db,
                                        compilation_id=results_data["compilation_id"],
                                        success=True,
                                    )
                                    print(f"DB: Saved compilation {results_data['compilation_id']}")

                            # Save deployment record if broadcast succeeded (tx_hash in response)
                            if structured_response and isinstance(structured_response, dict):
                                tx_hash = structured_response.get("transaction_hash") or structured_response.get("tx_hash")
                                if tx_hash:
                                    db_repo.save_deployment(
                                        session=db,
                                        transaction_hash=tx_hash,
                                        contract_address=structured_response.get("contract_address"),
                                        deployer_address=structured_response.get("deployer_address") or structured_response.get("user_address"),
                                        chain_id=structured_response.get("chain_id", 11155111),
                                        status="deployed",
                                    )
                                    print(f"DB: Saved deployment with tx_hash {tx_hash}")
                        finally:
                            db.close()
                    except Exception as db_error:
                        print(f"DB: Error saving to database: {db_error}")

                except asyncio.TimeoutError:
                    print("Backend API: ReAct agent timed out, using fallback")
                    raise Exception("ReAct agent timed out")
                except Exception as e:
                    print(f"Debug: Error in assistant invocation: {e}")
                    print(f"Debug: Error type: {type(e)}")
                    raise
    
                return ChatResponse(
                    success=True,
                    data={
                        "response": full_response,
                        "structured_response": structured_response,
                        "status": final_status,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "timestamp": datetime.now().isoformat(),
                        "backend_mode": "structured_react_assistant"
                    }
                )
                
        except Exception as react_error:
                print(f"Backend API: ReAct assistant failed: {react_error}, falling back to default response")
                # Return fallback response instead of continuing
                return ChatResponse(
                    success=True,
                    data={
                        "response": None,
                        "conversation_id": conversation_id,
                        "message_id": message_id,
                        "timestamp": datetime.now().isoformat(),
                        "backend_mode": "fallback_mode"
                    }
                )
        
    except Exception as e:
        print(f"Backend API: Error processing chat request: {e}")
        return ChatResponse(
            success=False,
            error=str(e)
        )

@router.post("/test-generate")
async def test_generate_endpoint(chat_request: ChatRequest, request: Request):
    """Temporary endpoint to test generate contract agent directly."""
    import time as _time
    gen_assistant = getattr(request.app.state, "generate_contract_assistant", None)
    if not gen_assistant:
        return {"success": False, "error": "Generate contract assistant not available"}

    _start = _time.time()
    print(f"[TestGenerate] Starting direct invoke...", flush=True)

    invoke_context = InvokeContext(
        conversation_id=uuid.uuid4().hex,
        invoke_id=uuid.uuid4().hex,
        assistant_request_id=uuid.uuid4().hex,
    )
    input_event = PublishToTopicEvent(
        invoke_context=invoke_context,
        publisher_name="test_api",
        publisher_type="api",
        topic_name="agent_input_topic",
        data=[Message(role="user", content=chat_request.message)],
        consumed_events=[],
    )

    results = []
    event_count = 0
    try:
        async for response_event in gen_assistant.invoke(input_event):
            event_count += 1
            elapsed = _time.time() - _start
            topic = getattr(response_event, 'topic_name', 'unknown')
            print(f"[TestGenerate] Event #{event_count} from '{topic}' at {elapsed:.1f}s", flush=True)
            if hasattr(response_event, 'data') and response_event.data:
                for msg in response_event.data:
                    if hasattr(msg, 'content') and msg.content:
                        results.append(str(msg.content)[:500])
    except Exception as e:
        print(f"[TestGenerate] Error: {e}", flush=True)
        return {"success": False, "error": str(e), "elapsed": _time.time() - _start}

    total = _time.time() - _start
    print(f"[TestGenerate] Done in {total:.1f}s, {event_count} events", flush=True)
    return {"success": True, "events": event_count, "elapsed": total, "results": results}

@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """Get conversation history for a specific conversation"""
    try:
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": [],
            "note": "Simple agent mode - history tracking not implemented yet"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/new")
async def new_conversation():
    """Start a new conversation and return a conversation ID"""
    try:
        conversation_id = uuid.uuid4().hex
        return {
            "success": True,
            "conversationId": conversation_id,
            "message": "New conversation started"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}