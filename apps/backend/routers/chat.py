import uuid
import sys
import os
import asyncio
import re
import json

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from deps.assistant import get_assistant
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from memory.context import get_conversation_context
from models.agent_responses import FinalAgentResponse, DeploymentApprovalRequest, FinalAgentResponse

from routers.approval import approval_requests

router = APIRouter(prefix="/api/chat", tags=["chat"])

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

        if assistant:
            print("Backend API: Using ReAct assistant with MCP tools")
            
            try:
                invoke_context = InvokeContext(
                    conversation_id=conversation_id,
                    invoke_id=uuid.uuid4().hex,
                    assistant_request_id=message_id,
                )
                
                # get context
                conversation_history = get_conversation_context(conversation_id)

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
                    async for response_event in assistant.a_invoke(input_event):
                        response_count += 1
                        
                        if hasattr(response_event, 'data') and response_event.data:
                            for message in response_event.data:

                                # if response_event.topic_name not in ["agent_output_topic", "deployment_request_topic"]:
                                #     print(f"Debug: Skipping message from intermediate topic: {response_event.topic_name}")
                                #     continue
                                
                                if hasattr(message, 'content') and message.content:
                                    parsed_content = None
                                    if isinstance(message.content, str):
                                        parsed_content = json.loads(message.content)
                                    else:
                                        parsed_content = message.content # pure string
                                    print('parsed_content', parsed_content)
                                    print('parsed_content_type', type(parsed_content))

                                    # Handle structured FinalAgentResponse - check for specific fields
                                    if isinstance(parsed_content, dict) and 'status' in parsed_content and 'summary' in parsed_content:
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
                                                    "processed": False
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