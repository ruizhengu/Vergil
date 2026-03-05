"""MCPTool subclass that handles servers not supporting resources/prompts."""

from grafi.tools.function_calls.impl.mcp_tool import MCPTool, MCPToolBuilder
from fastmcp import Client
from mcp.types import Tool
from grafi.common.models.function_spec import FunctionSpec


class SafeMCPTool(MCPTool):
    """MCPTool that gracefully handles servers without resources/prompts support."""

    @classmethod
    def builder(cls) -> "SafeMCPToolBuilder":
        return SafeMCPToolBuilder(cls)

    async def _get_function_specs(self) -> None:
        if not self.mcp_config:
            raise ValueError("mcp_config are not set.")

        all_tools: list[Tool] = []

        async with Client(self.mcp_config) as client:
            all_tools.extend(await client.list_tools())
            try:
                self.resources = await client.list_resources()
            except Exception as e:
                print(f"[SafeMCPTool] list_resources not supported: {e}")
                self.resources = []
            try:
                self.prompts = await client.list_prompts()
            except Exception as e:
                print(f"[SafeMCPTool] list_prompts not supported: {e}")
                self.prompts = []

        for tool in all_tools:
            func_spec = {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            }
            self.function_specs.append(FunctionSpec.model_validate(func_spec))


class SafeMCPToolBuilder(MCPToolBuilder):
    def __init__(self, cls=SafeMCPTool):
        super().__init__(cls)
