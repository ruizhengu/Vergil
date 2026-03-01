import os
import sys
import json

from pathlib import Path
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from pydantic import Field

from grafi.assistants.assistant import Assistant
from grafi.assistants.assistant_base import AssistantBaseBuilder
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.topics.input_topic import InputTopic
from grafi.common.topics.output_topic import OutputTopic
from grafi.common.topics.subscription_builder import SubscriptionBuilder
from grafi.common.topics.topic import Topic
from grafi.nodes.node import Node
from grafi.tools.llms.impl.openai_tool import OpenAITool
from grafi.tools.function_calls.impl.mcp_tool import MCPTool
from grafi.workflows.impl.event_driven_workflow import EventDrivenWorkflow
from grafi.common.models.mcp_connections import StreamableHttpConnection
from grafi.common.containers.container import container
from grafi.tools.function_calls.function_call_tool import FunctionCallTool
from grafi.common.models.message import Message
from grafi.common.models.function_spec import FunctionSpec
from grafi.common.topics.in_workflow_input_topic import InWorkflowInputTopic
from grafi.common.topics.in_workflow_output_topic import InWorkflowOutputTopic
from tools.mock_tool import SimpleMockTool
from models.agent_responses import ReasoningResponse, DeploymentApprovalRequest, ApprovalResponse, FinalAgentResponse


backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

services_path = os.path.join(backend_path, '..', '..', 'services', 'mcp_server', 'src')
services_path = os.path.abspath(services_path)
sys.path.append(services_path)

def load_prompt(file_path: str) -> str:
    """Load a prompt from a Markdown file."""
    return Path(file_path).read_text(encoding="utf-8")

load_dotenv()

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTION_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "action.md"))
REASONING_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "reasoning.md"))
DEPLOYMENT_REQUEST_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_request.md"))
DEPLOYMENT_APPROVAL_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "deployment_approval.md"))
FINAL_OUTPUT_PROMPT = load_prompt(os.path.join(backend_dir, "prompts", "final_output.md"))

class TrueReActAssistant(Assistant):
    name: str = Field(default="TrueReActSmartContractAgent")
    type: str = Field(default="TrueReActAssistant")
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    model: str = Field(default=lambda: os.getenv('OPENAI_MODEL', 'gpt-4'))
    function_call_tool: Optional[MCPTool] = Field(default=None)

    @classmethod
    def builder(cls):
        return TrueReActAssistantBuilder(cls)

    def get_function_specs_from_mcp_tool(self) -> List[FunctionSpec]:
        """Extract function specs from the MCP tool."""
        if self.function_call_tool is None:
            raise ValueError("function_call_tool is required to extract function specs")
        return self.function_call_tool.function_specs

    def _construct_workflow(self):
        if self.function_call_tool is None:
            raise ValueError(
                "function_call_tool is required for TrueReActAssistant. "
                "Use TrueReActAssistant.builder().function_call_tool(...).build()"
            )

        agent_input_topic = InputTopic(name="agent_input_topic")

        agent_output_topic = OutputTopic(
            name="agent_output_topic",
        )

        reasoning_output_topic = Topic(
            name="reasoning_output_topic",
            condition=lambda msgs: any(
                print(f"DEBUG reasoning_output_topic: msg={msg}, content={getattr(msg, 'content', None)}, type={type(getattr(msg, 'content', None))}") or
                hasattr(msg, 'content') and
                isinstance(msg.content, str) and
                (parsed := json.loads(msg.content)) and
                not parsed.get('requires_tool_call', True) and
                not parsed.get('requires_deployment', True)
                for msg in msgs
            )
        )
  
        action_topic = Topic(
            name="action_topic",
            condition=lambda msgs: any(
                hasattr(msg, 'content') and
                isinstance(msg.content, str) and
                (parsed := json.loads(msg.content)) and 
                parsed.get('requires_tool_call', False) and
                not parsed.get('requires_deployment', False) 
                for msg in msgs
            )
        )

        action_output_topic = Topic(name="action_output_topic")

        tool_execution_output_topic = Topic(name="tool_execution_output_topic")

        deployment_approval_topic = InWorkflowInputTopic(
            name = "deployment_approval_topic"
        )

        prepare_deployment_output_topic = InWorkflowOutputTopic(
            name= "prepare_deployment_output_topic", 
            paired_in_workflow_input_topic_name ="prepare_deployment_output_topic"
        )
        
        broadcast_deployment_output_topic = Topic(
            name="broadcast_deployment_output_topic",
        )
        
        # New topics for MCP tool execution in deployment flow
        deployment_request_output_topic = Topic(name="deployment_request_output_topic")
        deployment_approval_output_topic = Topic(name="deployment_approval_output_topic")

        deployment_topic = Topic(
            name="deployment_topic",
            condition=lambda msgs: any(
                print("deployment needed") or
                hasattr(msg, 'content') and
                isinstance(msg.content, str) and
                (parsed := json.loads(msg.content)) and 
                parsed.get('requires_deployment', False)
                for msg in msgs
            )
        )
        
        reasoning_node = (
            Node.builder()
            .name("reasoning_node")
            .type("reasoning_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(agent_input_topic)
                .or_()
                .subscribed_to(tool_execution_output_topic)
                .or_()
                .subscribed_to(broadcast_deployment_output_topic) 
                .build()
            )
            .tool(
                OpenAITool.builder()
                .name("reasoning_llm")
                .api_key(self.api_key)
                .model(self.model)
                .system_message(REASONING_PROMPT)
                .chat_params({
                    "response_format": ReasoningResponse
                })
                .build()
            )
            .publish_to(reasoning_output_topic)
            .publish_to(deployment_topic)
            .publish_to(action_topic)
            .build()
        )

        # Action node - translates structured reasoning to function calls
        action_node_openai_tool = (
            OpenAITool.builder()
            .name("action_llm")
            .api_key(self.api_key)
            .model(self.model)
            .system_message(ACTION_PROMPT)
            .build()
        )
        
        # Add function specs to action node instead of reasoning node
        function_spec = self.get_function_specs_from_mcp_tool()
        action_node_openai_tool.add_function_specs(function_spec)

        action_node = (
            Node.builder()
            .name("action_node")
            .type("action_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(action_topic)
                .build()
            )
            .tool(action_node_openai_tool)
            .publish_to(action_output_topic)
            .build()
        )

        tool_execution_node = (
            Node.builder()
            .name("tool_execution_node")
            .type("tool_execution_node")
            .subscribe(
                SubscriptionBuilder()
                .subscribed_to(action_output_topic)
                .build()
            )
            .tool(self.function_call_tool)
            .publish_to(tool_execution_output_topic)
            .build()
        )

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
                .chat_params({
                    "response_format": FinalAgentResponse
                })
                .build()
            )
            .publish_to(agent_output_topic)
            .build()
        )
        
        # Human Approval Request Node - only triggers on deployment
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
                OpenAITool.builder()
                .name("deployment_request_llm")
                .api_key(self.api_key)
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
        
        self.workflow = (
            EventDrivenWorkflow.builder()
            .name("react_smart_contract_workflow")
            .node(reasoning_node)
            .node(action_node)
            .node(tool_execution_node)
            .node(output_node)
            .node(deployment_request_node)
            .node(deployment_approval_node)
            .node(prepare_deployment_node)
            .node(broadcast_deployment_node)
            .build()
        )

        return self

class TrueReActAssistantBuilder(AssistantBaseBuilder):
    def api_key(self, api_key: str):
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str):
        self.kwargs["model"] = model
        return self

    def function_call_tool(self, function_call_tool):
        self.kwargs["function_call_tool"] = function_call_tool
        return self
