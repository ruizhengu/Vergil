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
    ) -> tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
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
            role = m.role or "user"
            content_str = m.content if isinstance(m.content, str) else (
                json.dumps(m.content) if m.content is not None else ""
            )

            # Z.AI is strict about message format — only include fields that are
            # non-None and relevant for the given role.
            if role == "system":
                # System messages in the middle get converted to user messages
                # (Z.AI only allows system as the first message)
                if api_messages and api_messages[-1]["role"] != "system":
                    msg_dict: Dict[str, Any] = {
                        "role": "user",
                        "content": f"[System context] {content_str}",
                    }
                else:
                    msg_dict = {
                        "role": "system",
                        "content": content_str,
                    }
            elif role == "tool":
                # Tool result messages require tool_call_id and content
                msg_dict = {
                    "role": "tool",
                    "content": content_str,
                }
                if m.tool_call_id:
                    msg_dict["tool_call_id"] = m.tool_call_id
                if m.name:
                    msg_dict["name"] = m.name
            elif role == "assistant" and m.tool_calls:
                # Assistant messages with tool_calls
                serialized_tool_calls = []
                for tc in m.tool_calls:
                    try:
                        if hasattr(tc, 'model_dump'):
                            tc_dict = tc.model_dump()
                        elif hasattr(tc, 'dict'):
                            tc_dict = tc.dict()
                        elif isinstance(tc, dict):
                            tc_dict = tc
                        else:
                            function_obj = getattr(tc, "function", None)
                            tc_dict = {
                                "id": getattr(tc, "id", f"call_{hash(str(tc)) % 1000000}"),
                                "type": "function",
                                "function": {
                                    "name": getattr(function_obj, "name", "") if function_obj else "",
                                    "arguments": getattr(function_obj, "arguments", "{}") if function_obj else "{}"
                                }
                            }
                        serialized_tool_calls.append(tc_dict)
                    except Exception as e:
                        print(f"DEBUG ZAI ERROR serializing tool_call item: {e}", flush=True)

                msg_dict = {
                    "role": "assistant",
                    "tool_calls": serialized_tool_calls,
                }
                if content_str:
                    msg_dict["content"] = content_str
            else:
                # Regular user/assistant messages — only role + content
                msg_dict = {
                    "role": role,
                    "content": content_str,
                }

            api_messages.append(msg_dict)

        # Z.AI requires the first non-system message to be a user message.
        # If the first message after system is assistant, wrap it as user.
        first_non_system_idx = 0
        for i, msg in enumerate(api_messages):
            if msg["role"] != "system":
                first_non_system_idx = i
                break
        if first_non_system_idx < len(api_messages):
            first_msg = api_messages[first_non_system_idx]
            if first_msg["role"] == "assistant":
                first_msg["role"] = "user"

        # Build tools list from function specs
        api_tools = None
        function_specs = self.get_function_specs()
        if function_specs:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters.model_dump(),
                    }
                }
                for spec in function_specs
            ]

        return api_messages, api_tools

    @record_tool_invoke
    async def invoke(
        self,
        invoke_context: InvokeContext,
        input_data: Messages,
    ) -> MsgsAGen:
        messages, api_tools = self.prepare_api_input(input_data)

        # DEBUG: Print messages being sent to Z.AI
        print(f"DEBUG ZAI REQUEST to {self.name} (model={self.model}), {len(messages)} messages", flush=True)
        for i, msg in enumerate(messages):
            role = msg.get("role", "?")
            content_preview = str(msg.get("content", ""))[:80]
            has_tc = "tool_calls" in msg
            has_tcid = "tool_call_id" in msg
            print(f"  msg[{i}] role={role} tc={has_tc} tcid={has_tcid} content={content_preview!r}", flush=True)
        if api_tools:
            print(f"DEBUG ZAI TOOLS: {[t['function']['name'] for t in api_tools]}", flush=True)

        try:
            from zai import ZaiClient

            if not self.api_key:
                self.api_key = os.getenv("ZAI_API_KEY")

            client = ZaiClient(api_key=self.api_key)

            # Build kwargs for the API call
            create_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
            }

            # Pass tools if function specs are available
            if api_tools:
                create_kwargs["tools"] = api_tools
                create_kwargs["tool_choice"] = "auto"

            # Pass chat_params (e.g. response_format, temperature, etc.)
            for key, value in self.chat_params.items():
                if key == "response_format" and value is not None:
                    # Convert Pydantic model class to JSON schema format for Z.AI
                    if isinstance(value, type) and hasattr(value, "model_json_schema"):
                        schema = value.model_json_schema()
                        create_kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": value.__name__,
                                "schema": schema,
                            }
                        }
                    else:
                        create_kwargs[key] = value
                else:
                    create_kwargs[key] = value

            response = client.chat.completions.create(**create_kwargs)

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
                            try:
                                function_obj = getattr(tc, "function", None)
                                tool_calls.append({
                                    "id": getattr(tc, "id", f"call_{hash(str(tc)) % 1000000}"),
                                    "type": "function",
                                    "function": {
                                        "name": getattr(function_obj, "name", "") if function_obj else "",
                                        "arguments": getattr(function_obj, "arguments", "{}") if function_obj else "{}"
                                    }
                                })
                            except Exception as e:
                                print(f"DEBUG ZAI ERROR serializing tool_call: {e}", flush=True)
            except Exception as e:
                print(f"DEBUG ZAI ERROR parsing response: {e}", flush=True)
                yield [Message(role="assistant", content="")]
                return

            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            msg_data: Dict[str, Any] = {"role": "assistant", "content": content}

            if tool_calls:
                msg_data["tool_calls"] = tool_calls
                # When model makes tool calls, content should be None per OpenAI convention
                if not content:
                    msg_data["content"] = None
                print(f"DEBUG ZAI TOOL_CALLS from response: {[(tc.get('function', {}).get('name', '?')) for tc in tool_calls]}", flush=True)

            # Fallback: if no native tool_calls but content looks like a JSON function call,
            # parse it into tool_calls format (for models that don't support tools natively)
            if not msg_data.get("tool_calls") and content:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "function" in parsed and parsed["function"]:
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
                        print(f"DEBUG ZAI: Parsed function call from JSON content: {func_name}", flush=True)
                except json.JSONDecodeError:
                    pass

            # Fallback: GLM sometimes responds with XML-style key/value format when
            # response_format (json_schema) is specified.
            # e.g. "format_to_deployment_result <arg_key>status</arg_key> <arg_value>ready_for_signing</arg_value>..."
            # Parse these into a plain JSON string so downstream code can detect them.
            if not msg_data.get("tool_calls") and content:
                import re as _re
                keys = _re.findall(r'<arg_key>(.*?)</arg_key>', content, _re.DOTALL)
                values = _re.findall(r'<arg_value>(.*?)</arg_value>', content, _re.DOTALL)
                if keys and len(keys) == len(values):
                    args_dict: Dict[str, Any] = {}
                    for k, v in zip(keys, values):
                        k = k.strip()
                        v = v.strip()
                        # Try to coerce numeric-looking or JSON values
                        try:
                            args_dict[k] = json.loads(v) if v not in ("null", "") else None
                        except json.JSONDecodeError:
                            args_dict[k] = v if v != "null" else None
                    reconstructed = json.dumps(args_dict)
                    msg_data["content"] = reconstructed
                    print(f"DEBUG ZAI: Reconstructed XML-style response_format output as JSON: {reconstructed[:120]}", flush=True)

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
