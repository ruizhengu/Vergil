import os
import json

from pathlib import Path
from typing import Optional, List
from pydantic import Field

from grafi.assistants.assistant import Assistant
from grafi.assistants.assistant_base import AssistantBaseBuilder
from grafi.topics.topic_impl.input_topic import InputTopic
from grafi.topics.topic_impl.output_topic import OutputTopic
from grafi.topics.expressions.subscription_builder import SubscriptionBuilder
from grafi.topics.topic_impl.topic import Topic
from grafi.common.models.function_spec import FunctionSpec
from grafi.nodes.node import Node
from tools.zai_tool import ZaiTool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from models.execution_agent_responses import ExecutionIntentResponse, ExecutionResult


def load_prompt(file_path: str) -> str:
    return Path(file_path).read_text(encoding="utf-8")


backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTION_INTENT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "execution_intent.md"))
EXECUTION_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "execution_action.md"))
EXECUTION_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "execution_output.md"))

EXECUTION_TOOL_NAMES = {"call_contract_function", "prepare_contract_call_transaction"}


class ExecutionAssistant(Assistant):
    name: str = Field(default="ExecutionAgent")
    type: str = Field(default="ExecutionAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ZAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("ZAI_MODEL", "zai"))
    function_call_tool: Optional[MCPTool] = Field(default=None)

    @classmethod
    def builder(cls):
        return ExecutionAssistantBuilder(cls)

    def get_execution_function_specs(self) -> List[FunctionSpec]:
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return [
            spec for spec in self.function_call_tool.function_specs
            if spec.name in EXECUTION_TOOL_NAMES
        ]

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for ExecutionAssistant. "
                "Use ExecutionAssistant.builder().function_call_tool(...).build()"
            )

        # --- Topics ---
        agent_input_topic = InputTopic(name="agent_input_topic")
        agent_output_topic = OutputTopic(name="agent_output_topic")

        execution_action_topic = Topic(name="execution_action_topic")
        execution_tool_topic = Topic(name="execution_tool_topic")
        execution_output_topic = Topic(name="execution_output_topic")

        # --- Nodes ---

        # 1. Intent Node — classify read/write, extract parameters including ABI
        intent_node = (
            Node.builder()
            .name("execution_intent_node")
            .type("execution_intent_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("execution_intent_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(EXECUTION_INTENT_PROMPT)
                .chat_params({"response_format": ExecutionIntentResponse})
                .build()
            )
            .publish_to(execution_action_topic)
            .build()
        )

        # 2. Action Node — translate intent into MCP function call
        action_zai_tool = (
            ZaiTool.builder()
            .name("execution_action_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(EXECUTION_ACTION_PROMPT)
            .build()
        )
        execution_specs = self.get_execution_function_specs()
        action_zai_tool.add_function_specs(execution_specs)

        action_node = (
            Node.builder()
            .name("execution_action_node")
            .type("execution_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(execution_action_topic)
                .build()
            )
            .tool(action_zai_tool)
            .publish_to(execution_tool_topic)
            .build()
        )

        # 3. Tool Node — execute the MCP tool call
        tool_node = (
            Node.builder()
            .name("execution_tool_node")
            .type("execution_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(execution_tool_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(execution_output_topic)
            .build()
        )

        # 4. Output Node — format ExecutionResult
        output_node = (
            Node.builder()
            .name("execution_output_node")
            .type("execution_output_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(execution_output_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("execution_output_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(EXECUTION_OUTPUT_PROMPT)
                .chat_params({"response_format": ExecutionResult})
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )

        # --- Workflow ---
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("execution_workflow")
            .node(intent_node)
            .node(action_node)
            .node(tool_node)
            .node(output_node)
            .build()
        )

        return self


class ExecutionAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def function_call_tool(self, function_call_tool):
        self.kwargs["function_call_tool"] = function_call_tool
        return self
