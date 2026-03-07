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
from models.execution_agent_responses import ExecutionResult as ExecutionAgentResult
from db.session import SessionLocal
from db import repository as db_repo

from routers.approval import approval_requests
from routers.wallet import get_wallet_for_conversation

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Base URL for MCP server REST endpoints (strip /mcp/ suffix)
MCP_SERVER_BASE = os.getenv("MCP_SERVER_URL", "http://localhost:8081/mcp/").replace("/mcp/", "").rstrip("/")

# In-memory cache for prepared transactions extracted from MCP tool results.
# Key: compilation_id, Value: full prepared transaction dict with bytecode
prepared_tx_cache: dict = {}


async def _fetch_mcp_transaction(compilation_id: str) -> Optional[dict]:
    """Fetch the full prepared transaction (with bytecode) from the MCP server.
    Retries up to 3 times with increasing timeout to handle slow MCP responses.
    """
    for attempt in range(3):
        try:
            timeout = 10 + (attempt * 10)  # 10s, 20s, 30s
            async with httpx.AsyncClient(timeout=timeout) as client:
                url = f"{MCP_SERVER_BASE}/api/transaction/{compilation_id}"
                print(f"[ChatAPI] Fetching full tx from MCP (attempt {attempt+1}): {url}", flush=True)
                resp = await client.get(url)
                print(f"[ChatAPI] MCP response status: {resp.status_code}", flush=True)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        tx = data["transaction"]
                        if tx.get("data") and len(str(tx["data"])) > 10:
                            print(f"[ChatAPI] Got full tx with bytecode (data len: {len(str(tx['data']))})", flush=True)
                            return tx
                        else:
                            print(f"[ChatAPI] WARNING: MCP returned tx but 'data' field is empty/missing!", flush=True)
                    else:
                        print(f"[ChatAPI] MCP returned success=false: {data.get('error')}", flush=True)
                elif resp.status_code == 404:
                    print(f"[ChatAPI] Transaction not found in MCP cache for {compilation_id}", flush=True)
                    break
                else:
                    print(f"[ChatAPI] Unexpected MCP status: {resp.status_code} - {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"[ChatAPI] Failed to fetch full transaction from MCP (attempt {attempt+1}): {e}", flush=True)
    return None


async def _get_tx_data_from_events(conversation_id: str, compilation_id: str) -> Optional[str]:
    """Query the Grafi event store for the prepare_deployment_transaction result.
    Returns transaction.data (bytecode + ABI-encoded constructor args).
    Sub-agents use their own conversation_id, so we search all recent events.
    """
    import re
    try:
        from db.session import engine as _engine
        import sqlalchemy as sa
        with _engine.connect() as conn:
            result = conn.execute(sa.text(
                "SELECT event_data FROM events "
                "WHERE event_data::text LIKE :comp_pat "
                "AND event_data::text LIKE '%\"transaction\"%' "
                "ORDER BY id DESC LIMIT 20"
            ), {"comp_pat": f"%{compilation_id}%"})
            for row in result:
                raw = json.dumps(row[0])
                for content_str in re.findall(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', raw):
                    try:
                        unescaped = bytes(content_str, "utf-8").decode("unicode_escape")
                        obj = json.loads(unescaped)
                        if (isinstance(obj, dict) and obj.get("compilation_id") == compilation_id
                                and isinstance(obj.get("transaction"), dict)):
                            tx_data = obj["transaction"].get("data")
                            if tx_data and len(str(tx_data)) > 10:
                                print(f"[ChatAPI] Found prepared tx data from event store (len: {len(str(tx_data))})", flush=True)
                                return tx_data if str(tx_data).startswith("0x") else "0x" + str(tx_data)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[ChatAPI] Event store tx query failed: {e}", flush=True)
    return None


async def _fetch_mcp_call(call_id: str) -> Optional[dict]:
    """Fetch the full prepared contract call transaction from the MCP server by call_id."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{MCP_SERVER_BASE}/api/call/{call_id}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data["transaction"]
    except Exception as e:
        print(f"[ChatAPI] Failed to fetch call transaction from MCP: {e}")
    return None


async def _fetch_mcp_compilation(compilation_id: str) -> Optional[dict]:
    """Fetch compilation data (abi, bytecode, source_code) from the MCP server."""
    try:
        url = f"{MCP_SERVER_BASE}/api/compilation/{compilation_id}"
        print(f"[ChatAPI] Fetching compilation from: {url}", flush=True)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            print(f"[ChatAPI] Compilation fetch status: {resp.status_code}", flush=True)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    bc = data.get("bytecode")
                    print(f"[ChatAPI] Compilation data: bytecode={'present, len=' + str(len(bc)) if bc else 'MISSING'}, abi={'present' if data.get('abi') else 'MISSING'}", flush=True)
                    return data
                else:
                    print(f"[ChatAPI] Compilation fetch returned success=false", flush=True)
            else:
                print(f"[ChatAPI] Compilation fetch failed: {resp.status_code} - {resp.text[:200]}", flush=True)
    except Exception as e:
        print(f"[ChatAPI] Failed to fetch compilation from MCP: {e}", flush=True)
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

                # Inject connected wallet address so agents can use it for deployment
                # Fall back to "default" session if conversation-specific wallet not set
                wallet_address = get_wallet_for_conversation(conversation_id) or get_wallet_for_conversation("default")

                # Inject deployed contract info so reasoning node knows what's already live
                deployed_context = ""
                try:
                    _dep_db = SessionLocal()
                    try:
                        deployments = db_repo.get_deployments_by_conversation(
                            _dep_db, conversation_id, deployer_address=wallet_address
                        )
                        if deployments:
                            deployed_context = "[Deployed contracts:\n"
                            for d in deployments:
                                deployed_context += (
                                    f"  - {d['contract_name']} at {d['contract_address']}"
                                    f" (compilation_id: {d['compilation_id']})\n"
                                )
                            deployed_context += "]\n"
                            print(f"[ChatAPI] Injecting {len(deployments)} deployed contract(s) into message", flush=True)
                    finally:
                        _dep_db.close()
                except Exception as _e:
                    print(f"[ChatAPI] Failed to fetch deployed contracts for injection: {_e}", flush=True)

                prefix = ""
                if wallet_address:
                    prefix += f"[Connected wallet: {wallet_address}]\n"
                if deployed_context:
                    prefix += deployed_context
                user_message = f"{prefix}\n{chat_request.message}" if prefix else chat_request.message

                input_data = conversation_history + [Message(role="user", content=user_message)]

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
                                            # Try extracting leading JSON (GLM hybrid: JSON + plain text)
                                            if raw.startswith('{'):
                                                try:
                                                    _decoder = json.JSONDecoder()
                                                    _parsed, _remainder = _decoder.raw_decode(raw)
                                                    if isinstance(_parsed, dict):
                                                        parsed_content = _parsed
                                                    else:
                                                        parsed_content = raw
                                                except json.JSONDecodeError:
                                                    parsed_content = raw
                                            else:
                                                parsed_content = raw
                                    else:
                                        parsed_content = message.content
                                    print('parsed_content', str(parsed_content)[:200])
                                    print('parsed_content_type', type(parsed_content))

                                    # Unwrap AgentCallingTool result: {"content": "<JSON>"} → parse inner
                                    if (isinstance(parsed_content, dict) and
                                            set(parsed_content.keys()) <= {"content"} and
                                            isinstance(parsed_content.get("content"), str)):
                                        try:
                                            inner = json.loads(parsed_content["content"])
                                            if isinstance(inner, dict):
                                                print(f"[ChatAPI] Unwrapped AgentCallingTool result, inner keys: {list(inner.keys())}", flush=True)
                                                parsed_content = inner
                                        except (json.JSONDecodeError, TypeError):
                                            pass

                                    # Handle ExecutionResult from execution agent
                                    if (
                                        isinstance(parsed_content, dict) and
                                        'function_type' in parsed_content and
                                        'function_name' in parsed_content and
                                        parsed_content.get('status') in ('success', 'pending_signature', 'failed')
                                    ):
                                        print(f"[ChatAPI] Processing ExecutionResult with status: {parsed_content['status']}")
                                        execution_result = ExecutionAgentResult(**parsed_content)

                                        if execution_result.status == "success":
                                            full_response = execution_result.summary
                                            if execution_result.return_value:
                                                full_response += f"\n\n**Result:** {execution_result.return_value}"
                                            final_status = "completed"
                                            structured_response = execution_result.model_dump()

                                        elif execution_result.status == "pending_signature":
                                            # Parse tx metadata from LLM output
                                            tx_metadata = {}
                                            call_id = None
                                            if execution_result.transaction_data:
                                                try:
                                                    tx_metadata = json.loads(execution_result.transaction_data)
                                                    call_id = tx_metadata.get("call_id")
                                                except (json.JSONDecodeError, TypeError):
                                                    tx_metadata = {}

                                            # Fetch the full transaction (with encoded data) from MCP server
                                            full_tx = None
                                            if call_id:
                                                full_tx = await _fetch_mcp_call(call_id)
                                            tx_data = full_tx if full_tx else tx_metadata

                                            full_response = execution_result.summary
                                            full_response += "\n\nPlease approve the transaction in your connected wallet."

                                            final_status = "pending_signature"
                                            structured_response = execution_result.model_dump()

                                            # Create approval request for frontend polling
                                            approval_id = f"exec_{uuid.uuid4().hex}"
                                            approval_requests[approval_id] = {
                                                "approval_id": approval_id,
                                                "transaction_data": tx_data,
                                                "timestamp": datetime.now(),
                                                "contract_type": "Contract Function Call",
                                                "deployment_details": {
                                                    "user_address": tx_metadata.get("from"),
                                                    "chain_id": tx_metadata.get("chainId", 11155111),
                                                },
                                                "estimated_gas": tx_metadata.get("gas"),
                                                "message": execution_result.summary,
                                                "processed": False,
                                                "conversation_id": conversation_id,
                                                "invoke_id": invoke_context.invoke_id,
                                                "assistant_request_id": invoke_context.assistant_request_id,
                                                "paused_event_id": getattr(response_event, 'event_id', None),
                                            }
                                            print(f"[ChatAPI] Created execution approval request: {approval_id}")

                                        else:
                                            full_response = f"Execution failed: {execution_result.error or execution_result.summary}"
                                            final_status = "failed"
                                            structured_response = execution_result.model_dump()

                                    # Handle DeploymentResult from deployment agent (has transaction_data field)
                                    elif isinstance(parsed_content, dict) and 'transaction_data' in parsed_content and parsed_content.get('status') in ('ready_for_signing', 'compilation_failed', 'failed'):
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

                                            comp_id = deployment_result.compilation_id
                                            tx_data = dict(tx_metadata)

                                            # Fetch prepared tx — bytecode must be present for on-chain deployment.
                                            # Sub-agents use their own conversation_id so event store search is global.
                                            if comp_id and not (tx_data.get("data") and len(str(tx_data.get("data", ""))) > 10):
                                                tx_data_field = await _get_tx_data_from_events(conversation_id, comp_id)
                                                if tx_data_field:
                                                    tx_data["data"] = tx_data_field
                                                    print(f"[ChatAPI] Resolved bytecode from event store (len: {len(tx_data_field)})", flush=True)

                                            if comp_id and not (tx_data.get("data") and len(str(tx_data.get("data", ""))) > 10):
                                                mcp_tx = await _fetch_mcp_transaction(comp_id)
                                                if mcp_tx and mcp_tx.get("data") and len(str(mcp_tx["data"])) > 10:
                                                    tx_data.update(mcp_tx)
                                                    print(f"[ChatAPI] Resolved bytecode from MCP REST (len: {len(str(mcp_tx['data']))})", flush=True)

                                            if not (tx_data.get("data") and len(str(tx_data.get("data", ""))) > 10):
                                                print(f"[ChatAPI] WARNING: No bytecode resolved for {comp_id}", flush=True)

                                            # Save compilation data to DB
                                            if comp_id:
                                                compilation_data = await _fetch_mcp_compilation(comp_id)
                                                if compilation_data:
                                                    try:
                                                        comp_db = SessionLocal()
                                                        try:
                                                            # Link compilation to the latest contract for this conversation
                                                            conv_contracts = db_repo.get_contracts_by_conversation(comp_db, conversation_id)
                                                            contract_id_link = conv_contracts[0].id if conv_contracts else None
                                                            db_repo.save_compilation(
                                                                session=comp_db,
                                                                compilation_id=comp_id,
                                                                contract_id=contract_id_link,
                                                                abi=compilation_data.get("abi"),
                                                                bytecode=compilation_data.get("bytecode"),
                                                                success=True,
                                                            )
                                                            print(f"DB: Saved compilation {comp_id} linked to contract {contract_id_link}")
                                                        finally:
                                                            comp_db.close()
                                                    except Exception as comp_db_err:
                                                        print(f"DB: Error saving compilation: {comp_db_err}")

                                            lines = ["Deployment transaction ready."]
                                            if deployment_result.compilation_id:
                                                lines.append(f"Compilation ID: {deployment_result.compilation_id}")
                                            if deployment_result.estimated_gas:
                                                lines.append(f"Estimated gas: {deployment_result.estimated_gas:,}")
                                            if deployment_result.gas_price_gwei:
                                                lines.append(f"Gas price: {deployment_result.gas_price_gwei} gwei")
                                            lines.append(f"Network: Sepolia ({deployment_result.chain_id})")
                                            lines.append("\nPlease approve the transaction in your wallet to complete the deployment.")
                                            full_response = "\n".join(lines)

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
                                            lines = ["Deployment transaction ready."]
                                            if mcp_response.get('estimated_gas'):
                                                lines.append(f"Estimated gas: {mcp_response['estimated_gas']:,}")
                                            if mcp_response.get('gas_price_gwei'):
                                                lines.append(f"Gas price: {mcp_response['gas_price_gwei']} gwei")
                                            if mcp_response.get('chain_id'):
                                                lines.append(f"Network: Sepolia ({mcp_response['chain_id']})")
                                            full_response = "\n".join(lines)
                                            
                                            full_response += "\n\nPlease approve the transaction in your wallet to complete the deployment."
                                            
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