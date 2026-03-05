import os
import json

from pathlib import Path
from typing import Optional, Any
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
from grafi.tools.llms.impl.openai_tool import OpenAITool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.tools.function_calls.impl.agent_calling_tool import AgentCallingTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from models.agent_responses import ReasoningResponse, FinalAgentResponse


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


class OrchestrationAssistant(Assistant):
    name: str = Field(default="OrchestrationAgent")
    type: str = Field(default="OrchestrationAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv('OPENAI_MODEL', 'gpt-4o'))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    generate_contract_assistant: Optional[Any] = Field(default=None)
    deployment_assistant: Optional[Any] = Field(default=None)

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
                .subscribed_to(contract_agent_result_topic)
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("reasoning_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(REASONING_PROMPT)
                .chat_params({"response_format": ReasoningResponse})
                .build()
            )
            .publish_to(reasoning_output_topic)
            .publish_to(contract_generation_topic)
            .publish_to(deployment_topic)
            .build()
        )

        # Contract generation delegation
        contract_delegation_output_topic = Topic(name="contract_delegation_output_topic")

        contract_delegation_openai_tool = (
            OpenAITool.builder()
            .name("contract_delegation_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(CONTRACT_GENERATION_DELEGATION_PROMPT)
            .build()
        )

        if self.generate_contract_assistant is not None:
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

            contract_delegation_openai_tool.add_function_specs(agent_calling_tool.function_specs)

            contract_delegation_node = (
                Node.builder()
                .name("contract_delegation_node")
                .type("contract_delegation_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(contract_generation_topic)
                    .build()
                )
                .tool(contract_delegation_openai_tool)
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
                OpenAITool.builder()
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
                OpenAITool.builder()
                .name("deployment_approval_llm")
                .api_key(self.api_key)
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
        deployment_delegation_openai_tool = (
            OpenAITool.builder()
            .name("deployment_delegation_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(DEPLOYMENT_DELEGATION_PROMPT)
            .build()
        )

        if self.deployment_assistant is not None:
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

            deployment_delegation_openai_tool.add_function_specs(deployment_agent_calling_tool.function_specs)

            deployment_delegation_node = (
                Node.builder()
                .name("deployment_delegation_node")
                .type("deployment_delegation_node")
                .subscribe(
                    SubscriptionBuilder()
                    .subscribed_to(deployment_topic)
                    .build()
                )
                .tool(deployment_delegation_openai_tool)
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
            )

        if self.deployment_assistant is not None:
            workflow_builder = (
                workflow_builder
                .node(deployment_delegation_node)
                .node(deployment_agent_execution_node)
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
