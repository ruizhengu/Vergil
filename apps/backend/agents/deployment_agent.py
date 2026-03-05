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
from models.deployment_agent_responses import DeploymentIntentResponse, DeploymentResult


def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")


backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOYMENT_INTENT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_intent.md"))
DEPLOYMENT_COMPILE_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_compile_action.md"))
DEPLOYMENT_PREPARE_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_prepare_action.md"))
DEPLOYMENT_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_output.md"))

# MCP tool names used by the deployment agent
COMPILE_TOOL_NAMES = {"compile_contract"}
PREPARE_TOOL_NAMES = {"prepare_deployment_transaction"}


class DeploymentAssistant(Assistant):
    name: str = Field(default="DeploymentAgent")
    type: str = Field(default="DeploymentAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ZAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("ZAI_MODEL", "zai"))
    function_call_tool: Optional[MCPTool] = Field(default=None)

    @classmethod
    def builder(cls):
        return DeploymentAssistantBuilder(cls)

    def get_compile_function_specs(self) -> List[FunctionSpec]:
        """Extract compile-related function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return [
            spec for spec in self.function_call_tool.function_specs
            if spec.name in COMPILE_TOOL_NAMES
        ]

    def get_prepare_function_specs(self) -> List[FunctionSpec]:
        """Extract prepare_deployment_transaction function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return [
            spec for spec in self.function_call_tool.function_specs
            if spec.name in PREPARE_TOOL_NAMES
        ]

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for DeploymentAssistant. "
                "Use DeploymentAssistant.builder().function_call_tool(...).build()"
            )

        # --- Topics ---
        agent_input_topic = InputTopic(name="agent_input_topic")
        agent_output_topic = OutputTopic(name="agent_output_topic")

        def _parse_intent(msg):
            """Parse intent content from either JSON string or Pydantic object."""
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

        # Intent routes: compile_and_deploy, deploy_compiled
        compile_deploy_topic = Topic(
            name="compile_deploy_topic",
            condition=lambda event: any(
                (parsed := _parse_intent(msg)) is not None
                and parsed.get("intent", "") == "compile_and_deploy"
                for msg in event.data
            ),
        )

        deploy_topic = Topic(
            name="deploy_topic",
            condition=lambda event: any(
                (parsed := _parse_intent(msg)) is not None
                and parsed.get("intent", "") == "deploy_compiled"
                for msg in event.data
            ),
        )

        compile_tool_output_topic = Topic(name="compile_tool_output_topic")
        compile_result_topic = Topic(name="compile_result_topic")
        prepare_tool_output_topic = Topic(name="prepare_tool_output_topic")
        prepare_result_topic = Topic(name="prepare_result_topic")

        # --- Nodes ---

        # 1. Intent Classification Node
        intent_node = (
            Node.builder()
            .name("deployment_intent_node")
            .type("deployment_intent_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("deployment_intent_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(DEPLOYMENT_INTENT_PROMPT)
                .chat_params({"response_format": DeploymentIntentResponse})
                .build()
            )
            .publish_to(compile_deploy_topic)
            .publish_to(deploy_topic)
            .build()
        )

        # 2. Compile Action Node — translates intent to compile_contract function call
        compile_action_zai_tool = (
            ZaiTool.builder()
            .name("deployment_compile_action_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(DEPLOYMENT_COMPILE_ACTION_PROMPT)
            .build()
        )
        compile_specs = self.get_compile_function_specs()
        compile_action_zai_tool.add_function_specs(compile_specs)

        compile_action_node = (
            Node.builder()
            .name("deployment_compile_action_node")
            .type("deployment_compile_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(compile_deploy_topic)
                .build()
            )
            .tool(compile_action_zai_tool)
            .publish_to(compile_tool_output_topic)
            .build()
        )

        # 3. Compile Tool Node — executes compile_contract MCP call
        compile_tool_node = (
            Node.builder()
            .name("deployment_compile_tool_node")
            .type("deployment_compile_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(compile_tool_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(compile_result_topic)
            .build()
        )

        # 4. Prepare Action Node — translates compilation result to prepare_deployment_transaction call
        prepare_action_zai_tool = (
            ZaiTool.builder()
            .name("deployment_prepare_action_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(DEPLOYMENT_PREPARE_ACTION_PROMPT)
            .build()
        )
        prepare_specs = self.get_prepare_function_specs()
        prepare_action_zai_tool.add_function_specs(prepare_specs)

        prepare_action_node = (
            Node.builder()
            .name("deployment_prepare_action_node")
            .type("deployment_prepare_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(deploy_topic)
                .or_()
                .subscribed_to(compile_result_topic)
                .build()
            )
            .tool(prepare_action_zai_tool)
            .publish_to(prepare_tool_output_topic)
            .build()
        )

        # 5. Prepare Tool Node — executes prepare_deployment_transaction MCP call
        prepare_tool_node = (
            Node.builder()
            .name("deployment_prepare_tool_node")
            .type("deployment_prepare_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(prepare_tool_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(prepare_result_topic)
            .build()
        )

        # 6. Output Node — formats DeploymentResult
        output_node = (
            Node.builder()
            .name("deployment_output_node")
            .type("deployment_output_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(prepare_result_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("deployment_output_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(DEPLOYMENT_OUTPUT_PROMPT)
                .chat_params({"response_format": DeploymentResult})
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )

        # --- Workflow ---
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("deployment_workflow")
            .node(intent_node)
            .node(compile_action_node)
            .node(compile_tool_node)
            .node(prepare_action_node)
            .node(prepare_tool_node)
            .node(output_node)
            .build()
        )

        return self


class DeploymentAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def function_call_tool(self, function_call_tool):
        self.kwargs["function_call_tool"] = function_call_tool
        return self
