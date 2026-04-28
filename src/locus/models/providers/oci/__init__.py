# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/

"""OCI GenAI model provider.

OCI GenAI is a hosted platform that supports multiple model families:
- Cohere (Command R, Command R+, Command A)
- Meta (Llama)
- OpenAI (GPT)
- xAI (Grok)
- Mistral
- Google (Gemini)

Each model family may have different API formats and capabilities.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from locus.core.events import ModelChunkEvent
from locus.core.messages import Message
from locus.models.base import ModelConfig, ModelResponse
from locus.models.providers.oci.base import OCIModelProvider
from locus.models.providers.oci.client import OCIAuthType, OCIClient, OCIClientConfig
from locus.models.providers.oci.models import CohereProvider, GenericProvider
from locus.models.providers.oci.openai_compat import (
    DEFAULT_OCI_GENAI_REGION,
    OCIOpenAIConfig,
    OCIOpenAIModel,
    build_oci_openai_base_url,
)


class OCIConfig(ModelConfig):
    """Configuration for OCI GenAI models."""

    model: str = ""  # Not used directly, use model_id
    model_id: str = "cohere.command-r-plus"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9

    # OCI-specific settings
    compartment_id: str | None = Field(default=None, description="OCI compartment OCID")
    profile_name: str = Field(default="DEFAULT", description="OCI config profile name")
    config_file: str = Field(default="~/.oci/config", description="Path to OCI config file")
    auth_type: OCIAuthType = Field(default=OCIAuthType.API_KEY, description="Auth type")
    service_endpoint: str | None = Field(default=None, description="OCI GenAI service endpoint URL")

    # Model-specific settings
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: list[str] = Field(default_factory=list)


class OCIModel(BaseModel):
    """OCI GenAI model provider.

    Automatically selects the appropriate provider based on model_id:
    - cohere.command-r-* → CohereProvider
    - cohere.command-a-* → GenericProvider (A series uses generic format)
    - meta.*, openai.*, google.*, xai.*, mistral.* → GenericProvider

    Example:
        >>> model = OCIModel(
        ...     model_id="openai.gpt-5.1-chat-latest",
        ...     profile_name="DEFAULT",
        ...     auth_type="api_key",
        ... )
        >>> response = await model.complete([Message.user("Hello!")])
    """

    config: OCIConfig
    _client: OCIClient | None = None
    _provider: OCIModelProvider | None = None

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        model_id: str = "cohere.command-r-plus",
        compartment_id: str | None = None,
        profile_name: str = "DEFAULT",
        auth_type: str | OCIAuthType = OCIAuthType.API_KEY,
        config_file: str = "~/.oci/config",
        service_endpoint: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> None:
        """Initialize OCI GenAI model.

        Args:
            model_id: OCI model identifier (e.g., "openai.gpt-oss-20b", "cohere.command-r-plus")
            compartment_id: OCI compartment OCID (defaults to tenancy from profile)
            profile_name: OCI config profile name from ~/.oci/config
            auth_type: Authentication type (api_key, security_token, instance_principal)
            config_file: Path to OCI config file
            service_endpoint: Full OCI GenAI service endpoint URL
            max_tokens: Maximum tokens for response
            temperature: Model temperature (0.0-1.0)
            **kwargs: Additional model parameters
        """
        if isinstance(auth_type, str):
            auth_type = OCIAuthType(auth_type)

        config = OCIConfig(
            model_id=model_id,
            compartment_id=compartment_id,
            profile_name=profile_name,
            auth_type=auth_type,
            config_file=config_file,
            service_endpoint=service_endpoint,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        super().__init__(config=config)

    @property
    def client(self) -> OCIClient:
        """Get or create the OCI client."""
        if self._client is None:
            client_config = OCIClientConfig(
                profile_name=self.config.profile_name,
                config_file=self.config.config_file,
                auth_type=self.config.auth_type,
                compartment_id=self.config.compartment_id,
                service_endpoint=self.config.service_endpoint,
            )
            self._client = OCIClient(client_config)
        return self._client

    @property
    def provider(self) -> OCIModelProvider:
        """Get the appropriate provider for this model."""
        if self._provider is None:
            self._provider = self._get_provider()
        return self._provider

    def _get_provider(self) -> OCIModelProvider:
        """Determine and instantiate the correct provider based on model_id."""
        model_id = self.config.model_id.lower()

        # Cohere R series uses CohereProvider
        if model_id.startswith("cohere.command-r"):
            return CohereProvider()

        # Everything else uses GenericProvider
        # This includes: cohere.command-a-*, meta.*, openai.*, google.*, xai.*, mistral.*
        return GenericProvider()

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Complete a chat request.

        Args:
            messages: Conversation history
            tools: Tool schemas in OpenAI format
            **kwargs: Additional OCI-specific options

        Returns:
            Model response with message and metadata
        """
        from oci.generative_ai_inference import models

        # Convert messages and tools using the provider
        # Pass model_id for model-specific handling (e.g., Gemini parallel tool calls)
        converted_messages = self.provider.convert_messages(messages, self.config.model_id)
        converted_tools = self.provider.convert_tools(tools)

        # Build request kwargs - remove duplicates
        request_kwargs = {
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "temperature": kwargs.pop("temperature", self.config.temperature),
            **kwargs,
        }

        # Build the request. Pass model_id so the provider can pick the right
        # token-limit field (OpenAI wants max_completion_tokens, Meta wants
        # max_tokens, others accept either).
        request_kwargs["model_id"] = self.config.model_id
        if isinstance(converted_messages, dict):
            # Cohere returns a dict with special keys
            request_kwargs = {**converted_messages, **request_kwargs}
            chat_request = self.provider.build_request([], converted_tools, **request_kwargs)
        else:
            chat_request = self.provider.build_request(
                converted_messages,
                converted_tools,
                **request_kwargs,
            )

        # Create chat details
        chat_details = models.ChatDetails(
            compartment_id=self.client.compartment_id,
            serving_mode=self.client.get_serving_mode(self.config.model_id),
            chat_request=chat_request,
        )

        # Execute request with retry for empty responses.
        # OCI GenAI sometimes returns empty content, especially under
        # concurrent load. Retry up to 3 times with backoff.
        loop = asyncio.get_running_loop()
        max_retries = 3

        for attempt in range(max_retries):
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat(chat_details),
            )

            # Parse response
            content, tool_calls, stop_reason = self.provider.parse_response(response)
            usage = self.provider.parse_usage(response)

            # If we got content or tool calls, we're good
            if content or tool_calls:
                break

            # Backoff before retry (0.5s, 1.0s)
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))

        return ModelResponse(
            message=Message.assistant(content=content, tool_calls=tool_calls),
            usage=usage,
            stop_reason=stop_reason,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ModelChunkEvent]:
        """Stream a chat response.

        Note: OCI GenAI streaming is limited. This implementation
        falls back to non-streaming and yields the full response.
        """
        # OCI GenAI has limited streaming support
        # Fall back to complete and yield in chunks
        response = await self.complete(messages, tools, **kwargs)

        if response.content:
            # Yield content in chunks for better UX
            chunk_size = 50
            content = response.content
            for i in range(0, len(content), chunk_size):
                yield ModelChunkEvent(content=content[i : i + chunk_size])

        if response.tool_calls:
            yield ModelChunkEvent(tool_calls=response.tool_calls)

        yield ModelChunkEvent(done=True)


__all__ = [
    "DEFAULT_OCI_GENAI_REGION",
    "CohereProvider",
    "GenericProvider",
    "OCIAuthType",
    "OCIClient",
    "OCIClientConfig",
    "OCIConfig",
    "OCIModel",
    "OCIModelProvider",
    "OCIOpenAIConfig",
    "OCIOpenAIModel",
    "build_oci_openai_base_url",
]
