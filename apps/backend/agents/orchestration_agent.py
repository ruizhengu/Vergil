import os
import json

from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv
from pydantic import Field

from grafi.assistants.assistant import Assistant
from grafi.assistants.assistant_base import AssistantBaseBuilder
from grafi.topics.topic_impl.input_topic import InputTopic
from grafi.topics.topic_impl.output_topic import OutputTopic
from grafi.topics.expressions.subscription_builder import SubscriptionBuilder
from grafi.topics.topic_impl.topic import Topic
from grafi.topics.topic_impl.in_workflow_input_topic import InWorkflowInputTopic
from grafi.topics.topic_impl.in_workflow_output_topic import InWorkflowOutputTopic
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from grafi.nodes.node import Node
from tools.zai_tool import ZaiTool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.tools.function_calls.impl.agent_calling_tool import AgentCallingTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from grafi.common.models.message import Message
from models.agent_responses import ReasoningResponse, FinalAgentResponse
from grafi.common.models.function_spec import FunctionSpec
from typing import List

# Import Anyway tracing decorators
# from anyway.sdk.decorators import workflow

COMPILE_TOOL_NAMES = {"compile_contract"}

# Monkey patch AgentCallingTool.invoke to handle empty input and missing tool calls gracefully
original_agent_invoke = AgentCallingTool.invoke
async def patched_agent_invoke(self, invoke_context, input_data):
    if not input_data:
        yield []
        return
    if input_data[0].tool_calls is None:
        # Instead of raising ValueError and crashing, return an empty list gracefully
        yield []
        return
    async for msgs in original_agent_invoke(self, invoke_context, input_data):
        yield msgs

AgentCallingTool.invoke = patched_agent_invoke

# Also patch MCPTool to avoid similar crashes
original_mcp_invoke = MCPTool.invoke
async def patched_mcp_invoke(self, invoke_context, input_data):
    if not input_data:
        yield []
        return
    if input_data[0].tool_calls is None:
        yield []
        return
    async for msgs in original_mcp_invoke(self, invoke_context, input_data):
        yield msgs

MCPTool.invoke = patched_mcp_invoke

load_dotenv()

def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")


backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REASONING_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "reasoning.md"))
DEPLOYMENT_APPROVAL_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_approval.md"))
FINAL_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "final_output.md"))
CONTRACT_GENERATION_DELEGATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "contract_generation_delegation.md"))
DEPLOYMENT_DELEGATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_delegation.md"))
EXECUTION_DELEGATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "execution_delegation.md"))
CONTRACT_VERIFICATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "contract_verification.md"))
# COMPILE_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "compile_action.md"))

# Track verification retries per invoke_id (max 2 retries before proceeding with warnings)
_verification_retries: Dict[str, int] = {}


class OrchestrationAssistant(Assistant):
    name: str = Field(default="OrchestrationAgent")
    type: str = Field(default="OrchestrationAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ZAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv('ZAI_MODEL', 'glm-4.7'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    generate_contract_assistant: Optional[Any] = Field(default=None)
    deployment_assistant: Optional[Any] = Field(default=None)
    execution_assistant: Optional[Any] = Field(default=None)

    def get_compile_function_specs(self) -> List[FunctionSpec]:
        """Extract compile-related function specs from the MCP tool."""
        if self.function_call_tool is None:
            return []
        return [
            spec for spec in self.function_call_tool.function_specs
            if spec.name in COMPILE_TOOL_NAMES
        ]

    @classmethod
    def builder(cls):
        return OrchestrationAssistantBuilder(cls)

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for OrchestrationAssistant. "
                "Use OrchestrationAssistant.builder().function_call_tool(...).build()"
            )

        # --- Topics ---
        agent_input_topic = InputTopic(name="agent_input_topic")
        agent_output_topic = OutputTopic(name="agent_output_topic")

        def _parse_reasoning(msg):
            """Parse reasoning content from either JSON string or Pydantic object."""
            if not hasattr(msg, 'content') or not msg.content:
                return None
            content = msg.content
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    print(f"[_parse_reasoning] Parsed from string: {parsed}", flush=True)
                    return parsed
                except (json.JSONDecodeError, ValueError):
                    return None
            if isinstance(content, dict):
                print(f"[_parse_reasoning] Content is dict: {content}", flush=True)
                return content
            # Pydantic model - convert to dict
            if hasattr(content, 'model_dump'):
                dumped = content.model_dump()
                print(f"[_parse_reasoning] model_dump: {dumped}", flush=True)
                return dumped
            if hasattr(content, '__dict__'):
                return vars(content)
            print(f"[_parse_reasoning] Could not parse content type: {type(content)}", flush=True)
            return None

        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                not parsed.get('requires_deployment', False) and
                not parsed.get('requires_contract_generation', False) and
                not parsed.get('requires_execution', False)
                for msg in event.data
            )
        )

        contract_generation_topic = Topic(
            name="contract_generation_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                parsed.get('requires_contract_generation', False)
                for msg in event.data
            )
        )

        deployment_approval_topic = InWorkflowInputTopic(
            name="deployment_approval_topic",
        )
        prepare_deployment_output_topic = InWorkflowOutputTopic(
            name="prepare_deployment_output_topic",
            paired_in_workflow_input_topic_names=["deployment_approval_topic"],
        )
        broadcast_deployment_output_topic = Topic(name="broadcast_deployment_output_topic")
        deployment_approval_output_topic = Topic(name="deployment_approval_output_topic")
        deployment_delegation_output_topic = Topic(name="deployment_delegation_output_topic")

        contract_agent_result_topic = Topic(name="contract_agent_result_topic")

        execution_topic = Topic(
            name="execution_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                parsed.get('requires_execution', False)
                for msg in event.data
            )
        )
        execution_delegation_output_topic = Topic(name="execution_delegation_output_topic")
        execution_agent_result_topic = Topic(name="execution_agent_result_topic")

        # Split contract agent result into verification required (has code) vs skip (needs input)
        def _has_contract_code(msg):
            if not hasattr(msg, 'content') or not msg.content:
                return False
            content = msg.content
            if isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    return parsed.get("status") != "needs_input"
                except:
                    return False
            return False

        verification_required_topic = Topic(
            name="verification_required_topic",
            condition=lambda event: any(_has_contract_code(msg) for msg in event.data)
        )

        verification_skip_topic = Topic(
            name="verification_skip_topic",
            condition=lambda event: not any(_has_contract_code(msg) for msg in event.data)
        )

        # --- Verification Topics ---
        def _parse_verification(msg):
            """Parse verification result from message content."""
            if not hasattr(msg, 'content') or not msg.content:
                return None
            content = msg.content
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    return None
            if isinstance(content, dict):
                return content
            if hasattr(content, 'model_dump'):
                return content.model_dump()
            if hasattr(content, '__dict__'):
                return vars(content)
            return None

        def _get_retry_count(event) -> int:
            """Get current retry count from event context."""
            invoke_id = "default"
            if hasattr(event, 'invoke_context') and hasattr(event.invoke_context, 'invoke_id'):
                invoke_id = event.invoke_context.invoke_id
            return _verification_retries.get(invoke_id, 0)

        def _check_verification_pass(event) -> bool:
            """Check if verification passed or max retries reached."""
            passed = any(
                (parsed := _parse_verification(msg)) is not None and
                parsed.get('pass_verification', False)
                for msg in event.data
            )
            if passed:
                return True
            # If failed but max retries reached, pass anyway (with warnings in the data)
            if _get_retry_count(event) >= 2:
                return True
            return False

        def _check_verification_fail(event) -> bool:
            """Check if verification failed and retries remain. Increments retry counter."""
            failed = any(
                (parsed := _parse_verification(msg)) is not None and
                not parsed.get('pass_verification', True)
                for msg in event.data
            )
            if not failed:
                return False
            retries = _get_retry_count(event)
            if retries >= 2:
                return False  # Max retries reached, will route to pass topic instead
            # Increment retry counter
            invoke_id = "default"
            if hasattr(event, 'invoke_context') and hasattr(event.invoke_context, 'invoke_id'):
                invoke_id = event.invoke_context.invoke_id
            _verification_retries[invoke_id] = retries + 1
            return True

        verification_pass_topic = Topic(
            name="verification_pass_topic",
            condition=_check_verification_pass
        )

        verification_fail_topic = Topic(
            name="verification_fail_topic",
            condition=_check_verification_fail
        )

        deployment_topic = Topic(
            name="deployment_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                parsed.get('requires_deployment', False)
                for msg in event.data
            )
        )

        # --- Nodes ---

        reasoning_node = (
            Node.builder()
            .name("reasoning_node")
            .type("reasoning_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .or_()
                .subscribed_to(broadcast_deployment_output_topic)
                .or_()
                .subscribed_to(verification_pass_topic)
                .or_()
                .subscribed_to(verification_skip_topic)
                .or_()
                .subscribed_to(execution_agent_result_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("reasoning_llm")

                .model(self.model)
                .system_message(REASONING_PROMPT)
                .build()
            )
            .publish_to(reasoning_output_topic)
            .publish_to(contract_generation_topic)
            .publish_to(deployment_topic)
            .publish_to(execution_topic)
            .build()
        )

        # Compile action node - translates reasoning to compile_contract function call
        # NOTE: This section has incomplete variable definitions (compile_topic, compile_action_output_topic, compile_tool_output_topic)
        # Skipping compile functionality for now
        compile_action_zai_tool = None
        compile_action_node = None
        compile_tool_node = None

        # Contract generation delegation
        contract_delegation_output_topic = Topic(name="contract_delegation_output_topic")

        contract_delegation_zai_tool = (
            ZaiTool.builder()
            .name("contract_delegation_llm")
            
            .model(self.model)
            .system_message(CONTRACT_GENERATION_DELEGATION_PROMPT)
            .build()
        )

        if self.generate_contract_assistant is not None:
            # @workflow(name="generate_contract")
            async def call_generate_agent(invoke_context, message):
                """Invoke the generate contract assistant and collect results."""
                import uuid
                import time as _time
                _start = _time.time()
                print(f"[OrchestrationAgent] Invoking generate contract agent...")
                # Create a fresh invoke context for the sub-agent to avoid
                # topic name collisions with the parent orchestration workflow
                child_context = InvokeContext(
                    conversation_id=invoke_context.conversation_id,
                    invoke_id=uuid.uuid4().hex,
                    assistant_request_id=uuid.uuid4().hex,
                )
                input_event = PublishToTopicEvent(
                    invoke_context=child_context,
                    publisher_name="orchestration_agent_delegation",
                    publisher_type="agent",
                    topic_name="agent_input_topic",
                    data=[message],
                    consumed_events=[],
                )
                result_content = ""
                event_count = 0
                async for response_event in self.generate_contract_assistant.invoke(input_event):
                    event_count += 1
                    elapsed = _time.time() - _start
                    topic = getattr(response_event, 'topic_name', 'unknown')
                    print(f"[GenerateContractAgent] Event #{event_count} from '{topic}' at {elapsed:.1f}s")
                    if hasattr(response_event, 'data') and response_event.data:
                        for msg in response_event.data:
                            if hasattr(msg, 'content') and msg.content:
                                content_preview = str(msg.content)[:100]
                                print(f"[GenerateContractAgent]   content: {content_preview}...")
                                result_content = msg.content
                total = _time.time() - _start
                print(f"[GenerateContractAgent] Completed in {total:.1f}s with {event_count} events")
                return {"content": result_content}

            agent_calling_tool = (
                AgentCallingTool.builder()
                .agent_name("generate_contract_agent")
                .agent_description(
                    "Generate smart contracts (ERC20, ERC721, or custom). "
                    "Pass the user's full contract generation request as the prompt."
                )
                .argument_description("The user's contract generation request with all details")
                .agent_call(call_generate_agent)
                .build()
            )

            contract_delegation_zai_tool.add_function_specs(agent_calling_tool.function_specs)

            contract_delegation_node = (
                Node.builder()
                .name("contract_delegation_node")
                .type("contract_delegation_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(contract_generation_topic)
                    .or_()
                    .subscribed_to(verification_fail_topic)
                    .build()
                )
                .tool(contract_delegation_zai_tool)
                .publish_to(contract_delegation_output_topic)
                .build()
            )

            contract_agent_execution_node = (
                Node.builder()
                .name("contract_agent_execution_node")
                .type("contract_agent_execution_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(contract_delegation_output_topic)
                    .build()
                )
                .tool(agent_calling_tool)
                .publish_to(verification_required_topic)
                .publish_to(verification_skip_topic)
                .build()
            )

        # Verification nodes — LLM + MCP tool pattern (action → tool)
        verification_action_output_topic = Topic(name="verification_action_output_topic")

        verification_zai_tool = (
            ZaiTool.builder()
            .name("verification_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(CONTRACT_VERIFICATION_PROMPT)
            .build()
        )
        # Add verify_contract_code function spec from MCP tool
        verification_specs = [
            spec for spec in self.function_call_tool.function_specs
            if spec.name == "verify_contract_code"
        ]
        verification_zai_tool.add_function_specs(verification_specs)

        verification_action_node = (
            Node.builder()
            .name("verification_action_node")
            .type("verification_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(verification_required_topic)
                .build()
            )
            .tool(verification_zai_tool)
            .publish_to(verification_action_output_topic)
            .build()
        )

        verification_tool_node = (
            Node.builder()
            .name("verification_tool_node")
            .type("verification_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(verification_action_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(verification_pass_topic)
            .publish_to(verification_fail_topic)
            .build()
        )

        # Output node
        output_node = (
            Node.builder()
            .name("output_node")
            .type("output_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(reasoning_output_topic)
                .or_()
                .subscribed_to(verification_skip_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("output_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(FINAL_OUTPUT_PROMPT)
                .chat_params({"response_format": FinalAgentResponse})
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )

        # Deployment approval node (resumes after wallet signing)
        deployment_approval_node = (
            Node.builder()
            .name("deployment_approval_node")
            .type("deployment_approval_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deployment_approval_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("deployment_approval_llm")
                
                .model(self.model)
                .system_message(DEPLOYMENT_APPROVAL_PROMPT)
                .build()
            )
            .publish_to(deployment_approval_output_topic)
            .build()
        )

        # Broadcast signed transaction after approval
        broadcast_deployment_node = (
            Node.builder()
            .name("broadcast_deployment_node")
            .type("broadcast_deployment_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deployment_approval_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(broadcast_deployment_output_topic)
            .build()
        )

        # Deployment delegation (AgentCallingTool pattern — same as contract generation)
        deployment_delegation_zai_tool = (
            ZaiTool.builder()
            .name("deployment_delegation_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(DEPLOYMENT_DELEGATION_PROMPT)
            .build()
        )

        if self.deployment_assistant is not None:
            # @workflow(name="deploy_contract")
            async def call_deployment_agent(invoke_context, message):
                """Invoke the deployment assistant and collect results."""
                import uuid as _uuid
                child_context = InvokeContext(
                    conversation_id=invoke_context.conversation_id,
                    invoke_id=_uuid.uuid4().hex,
                    assistant_request_id=_uuid.uuid4().hex,
                )
                input_event = PublishToTopicEvent(
                    invoke_context=child_context,
                    publisher_name="orchestration_agent_deployment_delegation",
                    publisher_type="agent",
                    topic_name="agent_input_topic",
                    data=[message],
                    consumed_events=[],
                )
                result_content = ""
                async for response_event in self.deployment_assistant.invoke(input_event):
                    if hasattr(response_event, 'data') and response_event.data:
                        for msg in response_event.data:
                            if hasattr(msg, 'content') and msg.content:
                                result_content = msg.content
                return {"content": result_content}

            deployment_agent_calling_tool = (
                AgentCallingTool.builder()
                .agent_name("deployment_agent")
                .agent_description(
                    "Handle contract deployment: compile if needed, then prepare deployment transaction. "
                    "Pass the full deployment context including any Solidity code, compilation IDs, and wallet addresses."
                )
                .argument_description("The deployment request with all relevant context")
                .agent_call(call_deployment_agent)
                .build()
            )

            deployment_delegation_zai_tool.add_function_specs(deployment_agent_calling_tool.function_specs)

            deployment_delegation_node = (
                Node.builder()
                .name("deployment_delegation_node")
                .type("deployment_delegation_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(deployment_topic)
                    .build()
                )
                .tool(deployment_delegation_zai_tool)
                .publish_to(deployment_delegation_output_topic)
                .build()
            )

            deployment_agent_execution_node = (
                Node.builder()
                .name("deployment_agent_execution_node")
                .type("deployment_agent_execution_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(deployment_delegation_output_topic)
                    .build()
                )
                .tool(deployment_agent_calling_tool)
                .publish_to(prepare_deployment_output_topic)
                .build()
            )

        # Execution delegation (AgentCallingTool pattern — same as contract generation/deployment)
        execution_delegation_zai_tool = (
            ZaiTool.builder()
            .name("execution_delegation_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(EXECUTION_DELEGATION_PROMPT)
            .build()
        )

        if self.execution_assistant is not None:
            async def call_execution_agent(invoke_context, message):
                """Invoke the execution assistant with deployed contract context injected."""
                import uuid as _uuid
                import json as _json

                # Fetch deployed contracts for this conversation and inject into message
                deployed_context = ""
                wallet_context = ""
                try:
                    from db.session import SessionLocal
                    from db import repository as db_repo
                    from routers.wallet import get_wallet_for_conversation
                    db = SessionLocal()
                    try:
                        deployments = db_repo.get_deployments_by_conversation(
                            db, invoke_context.conversation_id
                        )
                        if deployments:
                            deployed_context = "[Deployed contracts:\n"
                            for d in deployments:
                                abi_str = _json.dumps(d["abi"])
                                deployed_context += (
                                    f"  - {d['contract_name']} ({d['contract_type'] or 'Contract'}) "
                                    f"at {d['contract_address']} "
                                    f"(compilation_id: {d['compilation_id']}, ABI: {abi_str})\n"
                                )
                            deployed_context += "]\n"
                    finally:
                        db.close()
                    wallet_addr = get_wallet_for_conversation(invoke_context.conversation_id)
                    if wallet_addr:
                        wallet_context = f"[Connected wallet: {wallet_addr}]\n"
                except Exception as e:
                    print(f"[OrchestrationAgent] Failed to fetch execution context: {e}")

                original_content = message.content if hasattr(message, 'content') else str(message)
                augmented_content = f"{wallet_context}{deployed_context}\nUser request: {original_content}"
                augmented_message = Message(role="user", content=augmented_content)

                print(f"[OrchestrationAgent] Routing to execution agent")
                child_context = InvokeContext(
                    conversation_id=invoke_context.conversation_id,
                    invoke_id=_uuid.uuid4().hex,
                    assistant_request_id=_uuid.uuid4().hex,
                )
                input_event = PublishToTopicEvent(
                    invoke_context=child_context,
                    publisher_name="orchestration_agent_execution_delegation",
                    publisher_type="agent",
                    topic_name="agent_input_topic",
                    data=[augmented_message],
                    consumed_events=[],
                )
                result_content = ""
                async for response_event in self.execution_assistant.invoke(input_event):
                    if hasattr(response_event, 'data') and response_event.data:
                        for msg in response_event.data:
                            if hasattr(msg, 'content') and msg.content:
                                result_content = msg.content
                return {"content": result_content}

            execution_agent_calling_tool = (
                AgentCallingTool.builder()
                .agent_name("execution_agent")
                .agent_description(
                    "Call functions on deployed smart contracts (read-only view functions or state-changing write functions). "
                    "Pass the user's full execution request."
                )
                .argument_description("The user's contract execution request")
                .agent_call(call_execution_agent)
                .build()
            )

            execution_delegation_zai_tool.add_function_specs(execution_agent_calling_tool.function_specs)

            execution_delegation_node = (
                Node.builder()
                .name("execution_delegation_node")
                .type("execution_delegation_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(execution_topic)
                    .build()
                )
                .tool(execution_delegation_zai_tool)
                .publish_to(execution_delegation_output_topic)
                .build()
            )

            execution_agent_execution_node = (
                Node.builder()
                .name("execution_agent_execution_node")
                .type("execution_agent_execution_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(execution_delegation_output_topic)
                    .build()
                )
                .tool(execution_agent_calling_tool)
                .publish_to(execution_agent_result_topic)
                .build()
            )

        # --- Build Workflow ---
        workflow_builder = (
            EventDrivenWorkflow.builder()
            .name("orchestration_workflow")
            .node(reasoning_node)
            .node(output_node)
            .node(deployment_approval_node)
            .node(broadcast_deployment_node)
        )

        if self.generate_contract_assistant is not None:
            workflow_builder = (
                workflow_builder
                .node(contract_delegation_node)
                .node(contract_agent_execution_node)
                .node(verification_action_node)
                .node(verification_tool_node)
            )

        if self.deployment_assistant is not None:
            workflow_builder = (
                workflow_builder
                .node(deployment_delegation_node)
                .node(deployment_agent_execution_node)
            )

        if self.execution_assistant is not None:
            workflow_builder = (
                workflow_builder
                .node(execution_delegation_node)
                .node(execution_agent_execution_node)
            )

        self.workflow = workflow_builder.build()

        return self


class OrchestrationAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def function_call_tool(self, function_call_tool):
        self.kwargs["function_call_tool"] = function_call_tool
        return self

    def generate_contract_assistant(self, generate_contract_assistant):
        self.kwargs["generate_contract_assistant"] = generate_contract_assistant
        return self

    def deployment_assistant(self, deployment_assistant):
        self.kwargs["deployment_assistant"] = deployment_assistant
        return self

    def execution_assistant(self, execution_assistant):
        self.kwargs["execution_assistant"] = execution_assistant
        return self
