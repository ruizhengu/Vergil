import os
import json

from pathlib import Path
from typing import Optional, List, Any
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
from grafi.common.models.function_spec import FunctionSpec
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.events.topic_events.publish_to_topic_event import PublishToTopicEvent
from grafi.nodes.node import Node
from tools.zai_tool import ZaiTool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.tools.function_calls.impl.agent_calling_tool import AgentCallingTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from models.agent_responses import ReasoningResponse, FinalAgentResponse

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
COMPILE_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "compile_action.md"))
REASONING_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "reasoning.md"))
DEPLOYMENT_REQUEST_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_request.md"))
DEPLOYMENT_APPROVAL_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_approval.md"))
FINAL_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "final_output.md"))
CONTRACT_GENERATION_DELEGATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "contract_generation_delegation.md"))


class OrchestrationAssistant(Assistant):
    name: str = Field(default="OrchestrationAgent")
    type: str = Field(default="OrchestrationAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ZAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv('ZAI_MODEL', 'glm-4.7'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    generate_contract_assistant: Optional[Any] = Field(default=None)

    @classmethod
    def builder(cls):
        return OrchestrationAssistantBuilder(cls)

    def get_function_specs_from_mcp_tool(self) -> List[FunctionSpec]:
        """Extract function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return self.function_call_tool.function_specs

    def get_compile_function_specs(self) -> List[FunctionSpec]:
        """Extract only compile-related function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return [
            spec for spec in self.function_call_tool.function_specs
            if spec.name == "compile_contract"
        ]

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
                    return json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    return None
            if isinstance(content, dict):
                return content
            # Pydantic model - convert to dict
            if hasattr(content, 'model_dump'):
                return content.model_dump()
            if hasattr(content, '__dict__'):
                return vars(content)
            return None

        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                not parsed.get('requires_compile', False) and
                not parsed.get('requires_deployment', False) and
                not parsed.get('requires_contract_generation', False)
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

        compile_topic = Topic(
            name="compile_topic",
            condition=lambda event: any(
                (parsed := _parse_reasoning(msg)) is not None and
                parsed.get('requires_compile', False)
                for msg in event.data
            )
        )

        compile_action_output_topic = Topic(name="compile_action_output_topic")
        compile_tool_output_topic = Topic(name="compile_tool_output_topic")

        deployment_approval_topic = InWorkflowInputTopic(name="deployment_approval_topic")
        prepare_deployment_output_topic = InWorkflowOutputTopic(
            name="prepare_deployment_output_topic",
            paired_in_workflow_input_topic_name="prepare_deployment_output_topic"
        )
        broadcast_deployment_output_topic = Topic(name="broadcast_deployment_output_topic")
        deployment_request_output_topic = Topic(name="deployment_request_output_topic")
        deployment_approval_output_topic = Topic(name="deployment_approval_output_topic")

        contract_agent_result_topic = Topic(name="contract_agent_result_topic")

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
                .subscribed_to(compile_tool_output_topic)
                .or_()
                .subscribed_to(broadcast_deployment_output_topic)
                .or_()
                .subscribed_to(contract_agent_result_topic)
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
            .publish_to(compile_topic)
            .publish_to(deployment_topic)
            .build()
        )

        # Compile action node - translates reasoning to compile_contract function call
        compile_action_zai_tool = (
            ZaiTool.builder()
            .name("compile_action_llm")
            
            .model(self.model)
            .system_message(COMPILE_ACTION_PROMPT)
            .build()
        )
        compile_specs = self.get_compile_function_specs()
        compile_action_zai_tool.add_function_specs(compile_specs)

        compile_action_node = (
            Node.builder()
            .name("compile_action_node")
            .type("compile_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(compile_topic)
                .build()
            )
            .tool(compile_action_zai_tool)
            .publish_to(compile_action_output_topic)
            .build()
        )

        # Compile tool node - executes compile_contract MCP call
        compile_tool_node = (
            Node.builder()
            .name("compile_tool_node")
            .type("compile_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(compile_action_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(compile_tool_output_topic)
            .build()
        )

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
            async def call_generate_agent(invoke_context, message):
                """Invoke the generate contract assistant and collect results."""
                import uuid
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
                async for response_event in self.generate_contract_assistant.invoke(input_event):
                    if hasattr(response_event, 'data') and response_event.data:
                        for msg in response_event.data:
                            if hasattr(msg, 'content') and msg.content:
                                result_content = msg.content
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
                .publish_to(contract_agent_result_topic)
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
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("output_llm")
                
                .model(self.model)
                .system_message(FINAL_OUTPUT_PROMPT)
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )

        # Deployment nodes
        deployment_request_node = (
            Node.builder()
            .name("deployment_request_node")
            .type("deployment_request_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deployment_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("deployment_request_llm")
                
                .model(self.model)
                .system_message(DEPLOYMENT_REQUEST_PROMPT)
                .build()
            )
            .publish_to(deployment_request_output_topic)
            .build()
        )

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

        prepare_deployment_node = (
            Node.builder()
            .name("prepare_deployment_node")
            .type("prepare_deployment_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deployment_request_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(prepare_deployment_output_topic)
            .build()
        )

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

        # --- Build Workflow ---
        workflow_builder = (
            EventDrivenWorkflow.builder()
            .name("orchestration_workflow")
            .node(reasoning_node)
            .node(compile_action_node)
            .node(compile_tool_node)
            .node(output_node)
            .node(deployment_request_node)
            .node(deployment_approval_node)
            .node(prepare_deployment_node)
            .node(broadcast_deployment_node)
        )

        if self.generate_contract_assistant is not None:
            workflow_builder = (
                workflow_builder
                .node(contract_delegation_node)
                .node(contract_agent_execution_node)
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
