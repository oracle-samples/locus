# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""Anthropic model provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from locus.core.events import ModelChunkEvent
from locus.core.messages import Message, Role, ToolCall
from locus.models.base import ModelConfig, ModelResponse


if TYPE_CHECKING:
    import anthropic


class AnthropicConfig(ModelConfig):
    """Configuration for Anthropic models."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    api_key: str | None = Field(default=None, description="Anthropic API key")
    base_url: str | None = Field(default=None, description="Custom API base URL")


class AnthropicModel(BaseModel):
    """Anthropic model provider.

    Supports Claude 4.6, 4.5, 3.5 models with streaming and tool calling.

    Example:
        >>> model = AnthropicModel(model="claude-sonnet-4-20250514")
        >>> response = await model.complete([Message.user("Hello!")])
    """

    config: AnthropicConfig
    _client: anthropic.AsyncAnthropic | None = None

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> None:
        config = AnthropicConfig(
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        super().__init__(config=config)

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert Locus messages to Anthropic format.

        Returns (system_prompt, messages) since Anthropic takes system separately.
        """
        system_prompt: str | None = None
        anthropic_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_prompt = msg.content
                continue

            if msg.role == Role.ASSISTANT:
                content: list[dict[str, Any]] = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                anthropic_messages.append(
                    {"role": "assistant", "content": content or msg.content or ""}
                )

            elif msg.role == Role.TOOL:
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "",
                                "content": str(msg.content or ""),
                            }
                        ],
                    }
                )

            elif msg.role == Role.USER:
                anthropic_messages.append({"role": "user", "content": msg.content or ""})

        return system_prompt, anthropic_messages

    def _convert_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Convert OpenAI-format tools to Anthropic format."""
        if not tools:
            return None

        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return anthropic_tools

    _STRUCTURED_TOOL_NAME = "respond_with_schema"

    def _structured_output_tool(self, response_format: dict[str, Any]) -> dict[str, Any]:
        """Translate an OpenAI-style ``response_format`` into an Anthropic tool.

        Anthropic does not support a ``response_format`` parameter; the
        idiomatic way to enforce a JSON schema is to declare a single tool
        whose ``input_schema`` is the desired schema and force the model to
        call it via ``tool_choice``. We name the tool ``respond_with_schema``
        and re-use the underlying schema name as the tool description so the
        model picks up any high-level docstring.
        """
        json_schema = response_format.get("json_schema", {}) or {}
        schema = json_schema.get("schema") or {}
        description = (
            json_schema.get("description")
            or f"Return your final answer as a {json_schema.get('name', 'JSON')} object."
        )
        return {
            "name": self._STRUCTURED_TOOL_NAME,
            "description": description,
            "input_schema": schema or {"type": "object", "properties": {}},
        }

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Complete a chat request.

        Recognises an OpenAI-style ``response_format={"type": "json_schema", ...}``
        kwarg and translates it into Anthropic's tool-use mechanism: a synthetic
        ``respond_with_schema`` tool is appended to the call and ``tool_choice``
        is pinned to it. The tool arguments are then surfaced as the message
        content (canonical JSON) so callers can parse them with
        :func:`locus.core.structured.parse_structured` exactly as they would
        with native ``response_format`` providers.
        """
        import json as _json

        system_prompt, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools) or []

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        if system_prompt:
            params["system"] = system_prompt

        # Structured-output mode: emulate ``response_format`` via tool-use.
        response_format = kwargs.get("response_format")
        structured_mode = (
            isinstance(response_format, dict) and response_format.get("type") == "json_schema"
        )
        if structured_mode:
            assert isinstance(response_format, dict)  # narrowed by structured_mode
            anthropic_tools.append(self._structured_output_tool(response_format))
            params["tool_choice"] = {
                "type": "tool",
                "name": self._STRUCTURED_TOOL_NAME,
            }

        if anthropic_tools:
            params["tools"] = anthropic_tools

        response = await self.client.messages.create(**params)

        # Parse response
        content: str | None = None
        tool_calls: list[ToolCall] = []
        structured_payload: dict[str, Any] | None = None

        for block in response.content:
            if block.type == "text":
                content = (content or "") + block.text
            elif block.type == "tool_use":
                if structured_mode and block.name == self._STRUCTURED_TOOL_NAME:
                    structured_payload = block.input if isinstance(block.input, dict) else {}
                    continue
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        # In structured mode, surface the tool's arguments as the message
        # content so downstream ``parse_structured`` can validate it.
        if structured_mode and structured_payload is not None:
            content = _json.dumps(structured_payload)

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            }

        return ModelResponse(
            message=Message.assistant(content=content, tool_calls=tool_calls),
            usage=usage,
            stop_reason=response.stop_reason,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ModelChunkEvent]:
        """Stream a chat response."""
        system_prompt, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        if system_prompt:
            params["system"] = system_prompt
        if anthropic_tools:
            params["tools"] = anthropic_tools

        async with self.client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield ModelChunkEvent(content=text)

        yield ModelChunkEvent(done=True)
