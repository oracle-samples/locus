"""Unit tests for native ``response_format`` pass-through on the agent loop.

When ``Agent(output_schema=Pydantic)`` is configured AND the provider
exposes ``supports_structured_output`` as True, the loop should pass
``response_format=`` to ``model.complete()`` directly — skipping the
prompted-JSON fallback.

When the provider returns False (Anthropic, Ollama, OCI's native SDK),
the loop falls back to the prompted-JSON path and ``response_format``
is NOT passed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from locus.core.messages import Message


pytest.importorskip("openai")
pytest.importorskip("anthropic")


class SamplePayload(BaseModel):
    name: str
    score: float


class _StubModel:
    """Minimal model stub that records the kwargs it received."""

    def __init__(self, supports: bool) -> None:
        self.supports_structured_output = supports
        self.complete = AsyncMock()
        self.stream = AsyncMock()
        self._captured_kwargs: dict[str, Any] = {}

    async def complete(self, **kwargs: Any) -> Any:  # type: ignore[override,no-redef]
        self._captured_kwargs = kwargs
        from locus.models.base import ModelResponse

        return ModelResponse(
            message=Message.assistant('{"name": "ok", "score": 0.9}'),
            usage={"input_tokens": 10, "output_tokens": 4},
        )


def test_supports_structured_output_capability_on_openai_model():
    """OpenAIModel reports True; structured output passes through natively."""
    from locus.models.native.openai import OpenAIModel

    model = OpenAIModel(model="gpt-4o", api_key="sk-test")
    assert model.supports_structured_output is True


def test_supports_structured_output_capability_on_anthropic_model():
    """AnthropicModel reports False; falls back to prompted JSON."""
    from locus.models.native.anthropic import AnthropicModel

    model = AnthropicModel(model="claude-sonnet-4-20250514", api_key="sk-test")
    assert model.supports_structured_output is False


def test_supports_structured_output_capability_on_ollama_model():
    """OllamaModel reports False."""
    from locus.models.native.ollama import OllamaModel

    model = OllamaModel(model="llama3.3")
    assert model.supports_structured_output is False


def test_supports_structured_output_capability_on_oci_native_model():
    """OCIModel (native SDK transport) reports False; use OCIOpenAIModel for native."""
    pytest.importorskip("oci")
    from locus.models.providers.oci import OCIModel

    # Model id chosen to route to the native SDK transport.
    try:
        model = OCIModel(model_id="cohere.command-r-08-2024", profile_name="DEFAULT")
    except Exception:
        pytest.skip("OCI client construction requires real config")
    assert model.supports_structured_output is False


def test_oci_openai_compat_inherits_capability():
    """OCIOpenAIModel inherits from OpenAIModel; reports True."""
    pytest.importorskip("oci")
    from locus.models.providers.oci.openai_compat import OCIOpenAIModel

    try:
        model = OCIOpenAIModel(model="openai.gpt-5", profile_name="DEFAULT")
    except Exception:
        pytest.skip("OCIOpenAIModel construction requires OCI config")
    assert model.supports_structured_output is True


def test_build_response_format_returns_openai_shape():
    """``build_response_format`` already returns the right shape — sanity check."""
    from locus.core.structured import build_response_format

    rf = build_response_format(SamplePayload, strict=True)
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "SamplePayload"
    assert rf["json_schema"]["strict"] is True
    assert "schema" in rf["json_schema"]
    # required fields propagated:
    schema = rf["json_schema"]["schema"]
    assert "name" in schema.get("required", [])
    assert "score" in schema.get("required", [])
