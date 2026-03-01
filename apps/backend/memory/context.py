import logging

from grafi.common.models.message import Message
from grafi.common.containers.container import container
from models.agent_responses import FinalAgentResponse, ReasoningResponse, DeploymentApprovalRequest, ApprovalResponse
from routers.wallet import get_wallet_for_conversation
import json
from fastmcp.server.middleware import Middleware, MiddlewareContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_structured_content(msg: Message) -> dict:
    result = {
        "text_content": None,
        "structured_data": None,
        "type": None
    }
    
    if hasattr(msg, 'content') and msg.content:
        if isinstance(msg.content, FinalAgentResponse):
            result["structured_data"] = msg.content
            result["text_content"] = msg.content.summary
            result["type"] = "final_response"
        elif isinstance(msg.content, ReasoningResponse):
            result["structured_data"] = msg.content
            result["text_content"] = msg.content.reasoning
            result["type"] = "reasoning"
        elif isinstance(msg.content, DeploymentApprovalRequest):
            result["structured_data"] = msg.content
            result["text_content"] = f"Deployment approval requested for {msg.content.contract_type}"
            result["type"] = "approval_request"
        elif isinstance(msg.content, ApprovalResponse):
            result["structured_data"] = msg.content
            result["text_content"] = f"Approval {msg.content.approval_status}: {msg.content.reasoning}"
            result["type"] = "approval_response"
        else:
            result["text_content"] = str(msg.content)
            result["type"] = "text"
    
    return result

def extract_and_dedupe_messages(events) -> list[Message]:
    messages = []
    
    for event in events:
        if hasattr(event, 'input_data'):
            if isinstance(event.input_data, list):
                for item in event.input_data:
                    if hasattr(item, 'data') and isinstance(item.data, list):
                        for msg in item.data:
                            if isinstance(msg, Message):
                                messages.append(msg)
                    elif isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.input_data, Message):
                messages.append(event.input_data)
        
        # Extract from output_data
        if hasattr(event, 'output_data'):
            if isinstance(event.output_data, list):
                for item in event.output_data:
                    if isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.output_data, Message):
                messages.append(event.output_data)
        
        # Extract from data attribute
        if hasattr(event, 'data'):
            if isinstance(event.data, list):
                for item in event.data:
                    if isinstance(item, Message):
                        messages.append(item)
            elif isinstance(event.data, Message):
                messages.append(event.data)
    
    # Sort by timestamp
    messages.sort(key=lambda m: m.timestamp if hasattr(m, 'timestamp') else 0)
    
    # Deduplicate messages
    seen_messages = set()
    deduped_messages = []
    for msg in messages:
        key = (msg.message_id, msg.timestamp, msg.role, msg.content[:100] if msg.content else None)
        if key not in seen_messages:
            seen_messages.add(key)
            deduped_messages.append(msg)
    
    return deduped_messages

def get_conversation_context(conversation_id: str) -> list[Message]:
    event_store = container.event_store
    events = event_store.get_conversation_events(conversation_id)
    
    # Extract and deduplicate messages
    messages = extract_and_dedupe_messages(events)
    
    if messages:
        logger.info(f"Extracted messages: {messages}")
        logger.info(f"type of message {type(messages[0])}")
    
    # Build conversation flow
    conversation_flow = []
    pending_tool_call = None
    latest_tool_results = {}  
    
    for msg in messages:
        
        if msg.role == "user":
            conversation_flow.append(msg)
            
        elif msg.role == "assistant" and msg.content:
            # Handle structured responses
            content_info = extract_structured_content(msg)
            
            if content_info["type"] == "final_response":
                # Final agent response - include it
                final_response = content_info["structured_data"]
                
                # Create user-friendly context message
                context_text = final_response.summary
                if final_response.results and "solidity_code" in final_response.results:
                    context_text += f" Generated contract: {final_response.results.get('contract_name', 'Contract')}"
                if final_response.artifacts:
                    context_text += f" Artifacts: {', '.join(final_response.artifacts)}"
                    
                summary_msg = Message(
                    role="assistant",
                    content=context_text
                )
                conversation_flow.append(summary_msg)
                pending_tool_call = None
                
            elif content_info["type"] == "reasoning":
                # Reasoning response - only include if it doesn't require tools
                reasoning = content_info["structured_data"]
                if not reasoning.requires_tool_call and not reasoning.requires_deployment:
                    # This reasoning led to a final output, include context
                    summary_msg = Message(
                        role="assistant", 
                        content=reasoning.reasoning[:200] + "..." if len(reasoning.reasoning) > 200 else reasoning.reasoning
                    )
                    conversation_flow.append(summary_msg)
                    
            elif content_info["type"] in ["approval_request", "approval_response"]:
                # Include approval flow messages
                conversation_flow.append(msg)
                
            elif msg.tool_calls:
                # Track what action was attempted
                tool_names = [tc.function.name for tc in msg.tool_calls if tc.function]
                if tool_names:
                    pending_tool_call = tool_names[0]
            
        elif msg.role == "tool" and msg.content:
            # Tool response received - store for context but don't add to conversation
            # The structured final response will handle user communication
            tool_name = pending_tool_call or "unknown_tool"
            logger.info(f"tool found: {msg}")
            
            try:
                tool_response = json.loads(msg.content)
                if tool_response.get("success", True):
                    latest_tool_results[tool_name] = msg.content
            except (json.JSONDecodeError, AttributeError):
                # Store raw content for fallback
                latest_tool_results[tool_name] = msg.content
            
            pending_tool_call = None
    
    # Handle any pending failed actions
    if pending_tool_call:
        failure_msg = Message(
            role="assistant", 
            content=f"Previous action ({pending_tool_call}) encountered an issue."
        )
        conversation_flow.append(failure_msg)
    
    # Add context about available tool results (simplified for structured output)
    if latest_tool_results:
        context_items = []
        
        for tool, result in latest_tool_results.items():
            if tool in ["generate_erc20_contract", "generate_erc721_contract"]:
                try:
                    parsed = json.loads(result)
                    if "solidity_code" in parsed:
                        contract_name = parsed.get("contract_name", "Contract")
                        context_items.append(f"{contract_name} generated and ready for compilation")
                except:
                    context_items.append("Contract code generated")
                    
            elif tool == "compile_contract":
                try:
                    parsed = json.loads(result)
                    if parsed.get("compilation_id"):
                        compilation_id = parsed['compilation_id']
                        context_items.append(f"Contract compiled (ID: {compilation_id})")
                except:
                    context_items.append("Contract compilation completed")
        
        # Only add context if we have useful information and limited conversation
        if context_items and len(conversation_flow) < 3:
            availability_text = f"Context: {', '.join(context_items)}"
            context_msg = Message(
                role="assistant",
                content=availability_text
            )
            conversation_flow.append(context_msg)
    
    # Keep recent context - increased limit for structured responses
    final_context = conversation_flow[-15:]
    
    # Ensure we have sufficient context for reasoning
    if len(final_context) < 2 and messages:
        # Add the most recent user message at minimum
        for msg in reversed(messages[-10:]):
            if msg.role == "user":
                final_context.insert(0, msg)
                break
    
    # Add wallet context if available
    wallet_address = get_wallet_for_conversation(conversation_id)
    if wallet_address:
        wallet_context_msg = Message(
            role="system",
            content=f"[User's connected wallet address: {wallet_address}]"
        )
        # Insert wallet context near the beginning but after any user messages
        if len(final_context) > 1:
            final_context.insert(-1, wallet_context_msg)
        else:
            final_context.append(wallet_context_msg)
    
    return final_context