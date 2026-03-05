import os
import json
import time

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
from models.contract_agent_responses import IntentClassificationResponse, ContractGenerationResult


def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")


backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTENT_CLASSIFICATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "intent_classification.md"))
GENERIC_ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "generic_action.md"))
CUSTOM_GENERATION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "custom_generation.md"))
GENERATE_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "generate_output.md"))

# Tool names relevant to contract generation (OpenZeppelin MCP tools)
GENERATION_TOOL_NAMES = {
    "solidity-erc20", "solidity-erc721", "solidity-erc1155",
    "solidity-stablecoin", "solidity-rwa", "solidity-account",
    "solidity-governor", "solidity-custom"
}


class GenerateContractAssistant(Assistant):
    name: str = Field(default="GenerateContractAgent")
    type: str = Field(default="GenerateContractAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ZAI_API_KEY"))
    model: str = Field(default_factory=lambda: os.getenv("ZAI_MODEL", "glm-4.7"))
    function_call_tool: Optional[MCPTool] = Field(default=None)
    oz_mcp_tool: Optional[MCPTool] = Field(default=None)

    @classmethod
    def builder(cls):
        return GenerateContractAssistantBuilder(cls)

    def get_generation_function_specs(self) -> List[FunctionSpec]:
        """Extract only contract generation function specs from the OZ MCP tool."""
        if self.oz_mcp_tool is None:
            raise ValueError("oz_mcp_tool is required to extract function specs")
        return [
            spec for spec in self.oz_mcp_tool.function_specs
            if spec.name in GENERATION_TOOL_NAMES
        ]

    def _construct_workflow(self):
        if self.oz_mcp_tool is None:
            raise ValueError(
                "oz_mcp_tool is required for GenerateContractAssistant. "
                "Use GenerateContractAssistant.builder().oz_mcp_tool(...).build()"
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

        # Intent classification routes to one of three paths
        generic_topic = Topic(
            name="generic_topic",
            condition=lambda event: any(
                (parsed := _parse_intent(msg)) is not None
                and parsed.get("intent", "") in ("generic_erc20", "generic_erc721", "generic_erc1155")
                for msg in event.data
            ),
        )

        custom_topic = Topic(
            name="custom_topic",
            condition=lambda event: any(
                (parsed := _parse_intent(msg)) is not None
                and parsed.get("intent", "") == "custom"
                for msg in event.data
            ),
        )

        conversational_topic = Topic(
            name="conversational_topic",
            condition=lambda event: any(
                (parsed := _parse_intent(msg)) is not None
                and parsed.get("intent", "") == "conversational"
                for msg in event.data
            ),
        )

        # After generic action node translates params to function call
        generic_tool_output_topic = Topic(name="generic_tool_output_topic")

        # Both generic tool results and custom LLM output converge here
        code_ready_topic = Topic(name="code_ready_topic")

        # --- Nodes ---

        # 1. Intent Classification Node
        intent_classification_node = (
            Node.builder()
            .name("intent_classification_node")
            .type("intent_classification_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("intent_classification_llm")
                
                .model(self.model)
                .system_message(INTENT_CLASSIFICATION_PROMPT)
                .build()
            )
            .publish_to(generic_topic)
            .publish_to(custom_topic)
            .publish_to(conversational_topic)
            .build()
        )

        # 2. Generic Action Node - translates params to MCP function calls
        generic_action_zai_tool = (
            ZaiTool.builder()
            .name("generic_action_llm")
            
            .model(self.model)
            .system_message(GENERIC_ACTION_PROMPT)
            .build()
        )
        generation_specs = self.get_generation_function_specs()
        print(f"[GenerateContractAgent] OZ generation specs count: {len(generation_specs)}")
        for spec in generation_specs:
            print(f"[GenerateContractAgent]   - {spec.name}")
        generic_action_zai_tool.add_function_specs(generation_specs)

        generic_action_node = (
            Node.builder()
            .name("generic_action_node")
            .type("generic_action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(generic_topic)
                .build()
            )
            .tool(generic_action_zai_tool)
            .publish_to(generic_tool_output_topic)
            .build()
        )

        # 3. Generic Tool Node - executes MCP tool calls
        generic_tool_node = (
            Node.builder()
            .name("generic_tool_node")
            .type("generic_tool_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(generic_tool_output_topic)
                .build()
            )
            .tool(self.oz_mcp_tool)
            .publish_to(code_ready_topic)
            .build()
        )

        # 4. Custom Generation Node - LLM generates raw Solidity
        custom_generation_node = (
            Node.builder()
            .name("custom_generation_node")
            .type("custom_generation_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(custom_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("custom_generation_llm")
                
                .model(self.model)
                .system_message(CUSTOM_GENERATION_PROMPT)
                .build()
            )
            .publish_to(code_ready_topic)
            .build()
        )

        # 5. Output Node - formats final ContractGenerationResult
        output_node = (
            Node.builder()
            .name("output_node")
            .type("output_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(code_ready_topic)
                .or_()
                .subscribed_to(conversational_topic)
                .build()
            )
            .tool(
                ZaiTool.builder()
                .name("output_llm")
                
                .model(self.model)
                .system_message(GENERATE_OUTPUT_PROMPT)
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )

        # --- Workflow ---
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("generate_contract_workflow")
            .node(intent_classification_node)
            .node(generic_action_node)
            .node(generic_tool_node)
            .node(custom_generation_node)
            .node(output_node)
            .build()
        )

        return self


class GenerateContractAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def oz_mcp_tool(self, oz_mcp_tool):
        self.kwargs["oz_mcp_tool"] = oz_mcp_tool
        return self
