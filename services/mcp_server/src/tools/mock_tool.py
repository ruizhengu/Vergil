from grafi.tools.function_calls.function_call_tool import FunctionCallTool
from grafi.common.models.message import Message

class SimpleMockTool(FunctionCallTool):
    def __init__(self):
        super().__init__()
        self.name = "SimpleMockTool"
        self.type = "MockTool"

    def invoke(self, invoke_context, input_data):
        """Synchronous mock response"""
        output = []
        for message in input_data:
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    output.append(Message(
                        role="tool",
                        content=f'{{"result": "Mock response for {tool_call.function.name}", "success": true}}',
                        tool_call_id=tool_call.id
                    ))
        return output if output else input_data