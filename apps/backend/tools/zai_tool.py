"""
ZaiTool - Z.AI implementation of grafi.tools.llms.llm.LLM
Based on the OpenAI tool implementation from grafi
Uses official Z.AI SDK
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Self

from pydantic import Field

from grafi.common.decorators.record_decorators import record_tool_invoke
from grafi.common.exceptions import LLMToolException
from grafi.common.models.invoke_context import InvokeContext
from grafi.common.models.message import Message
from grafi.common.models.message import Messages
from grafi.common.models.message import MsgsAGen
from grafi.tools.llms.llm import LLM
from grafi.tools.llms.llm import LLMBuilder


class ZaiTool(LLM):
    """
    ZaiTool - Z.AI implementation of grafi.tools.llms.llm.LLM

    This class provides methods to interact with Z.AI's API for natural language processing tasks.

    Attributes:
        api_key (str): The API key for authenticating with Z.AI.
        model (str): The name of the Z.AI model to use (default is 'glm-4.7').
    """

    name: str = Field(default="ZaiTool")
    type: str = Field(default="ZaiTool")
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ZAI_API_KEY")
    )
    model: str = Field(default="glm-4.7")

    chat_params: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def builder(cls) -> "ZaiToolBuilder":
        """
        Return a builder for ZaiTool.

        This method allows for the construction of a ZaiTool instance with specified parameters.
        """
        return ZaiToolBuilder(cls)

    def prepare_api_input(
        self, input_data: Messages
    ) -> tuple[List[Dict[str, Any]], None]:
        api_messages: List[Dict[str, Any]] = (
            [
                {
                    "role": "system",
                    "content": self.system_message,
                }
            ]
            if self.system_message
            else []
        )

        for m in input_data:
            msg_dict: Dict[str, Any] = {
                "role": m.role,
                "content": m.content or "",
            }
            if m.name:
                msg_dict["name"] = m.name
            if m.tool_call_id:
                msg_dict["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            api_messages.append(msg_dict)

        return api_messages, None

    @record_tool_invoke
    async def invoke(
        self,
        invoke_context: InvokeContext,
        input_data: Messages,
    ) -> MsgsAGen:
        messages, _ = self.prepare_api_input(input_data)

        try:
            from zai import ZaiClient
            
            if not self.api_key:
                self.api_key = os.getenv("ZAI_API_KEY")
            
            client = ZaiClient(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            
            try:
                if not response.choices:
                    yield [Message(role="assistant", content="")]
                    return
                
                choice = response.choices[0]
                if not choice:
                    yield [Message(role="assistant", content="")]
                    return
                    
                message = choice.message
                if not message:
                    yield [Message(role="assistant", content="")]
                    return
                
                content = message.content or ""
                
                tool_calls = None
                if message.tool_calls:
                    tool_calls = []
                    for tc in message.tool_calls:
                        if hasattr(tc, 'model_dump'):
                            tool_calls.append(tc.model_dump())
                        elif hasattr(tc, 'dict'):
                            tool_calls.append(tc.dict())
                        elif isinstance(tc, dict):
                            tool_calls.append(tc)
                        else:
                            tool_calls.append({
                                "id": getattr(tc, "id", f"call_{hash(str(tc)) % 1000000}"),
                                "type": "function",
                                "function": {
                                    "name": getattr(tc.function, "name", "") if hasattr(tc, "function") else "",
                                    "arguments": str(getattr(tc.function, "arguments", "{}")) if hasattr(tc, "function") else "{}"
                                }
                            })
            except Exception:
                yield [Message(role="assistant", content="")]
                return
            
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            msg_data = {"role": "assistant", "content": content}
            
            if tool_calls:
                msg_data["tool_calls"] = tool_calls
            
            try:
                parsed = json.loads(content)
                if "function" in parsed and parsed["function"]:
                    func_name = parsed["function"]
                    func_args = parsed.get("arguments", {})
                    
                    if not func_args:
                        func_args = {k: v for k, v in parsed.items() if k != "function"}
                    
                    if isinstance(func_args, dict):
                        func_args = json.dumps(func_args)
                    
                    tool_call_id = f"call_{hash(func_name) % 1000000}"
                    
                    msg_data["tool_calls"] = [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": func_name,
                                "arguments": func_args
                            }
                        }
                    ]
                    msg_data["content"] = None
            except json.JSONDecodeError:
                pass
            
            yield [Message(**msg_data)]
                
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise LLMToolException(
                tool_name=self.name,
                model=self.model,
                message=f"Z.AI async call failed: {exc}",
                invoke_context=invoke_context,
                cause=exc,
            ) from exc

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
        }

    @classmethod
    async def from_dict(cls, data: Dict[str, Any]) -> "ZaiTool":
        from openinference.semconv.trace import OpenInferenceSpanKindValues

        return (
            cls.builder()
            .name(data.get("name", "ZaiTool"))
            .type(data.get("type", "ZaiTool"))
            .oi_span_type(OpenInferenceSpanKindValues(data.get("oi_span_type", "TOOL")))
            .chat_params(data.get("chat_params", {}))
            .is_streaming(data.get("is_streaming", False))
            .system_message(data.get("system_message", ""))
            .api_key(os.getenv("ZAI_API_KEY"))
            .model(data.get("model", "glm-4.7"))
            .build()
        )


class ZaiToolBuilder(LLMBuilder[ZaiTool]):
    """
    Builder for ZaiTool.
    """

    def api_key(self, api_key: Optional[str]) -> Self:
        if api_key is None:
            api_key = os.getenv("ZAI_API_KEY")
        self.kwargs["api_key"] = api_key
        return self

    def _set_api_key(self, api_key: Optional[str]) -> Self:
        self.kwargs["api_key"] = api_key
        return self

    def model(self, model: str) -> Self:
        if model is None:
            model = os.getenv("ZAI_MODEL", "glm-4.7")
        self.kwargs["model"] = model
        return self
