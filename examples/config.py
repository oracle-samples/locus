# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Shared configuration for Locus tutorials.

Tutorials are designed to work with any LLM provider. By default, they use
a mock model so you can explore Locus's features without API credentials.

To run with a real model, set environment variables before running tutorials.

Environment Variables:
    LOCUS_MODEL_PROVIDER   - Provider: "mock", "oci", "openai"
                            Default: "mock"
    LOCUS_MODEL_ID         - Model identifier (provider-specific)

    # OCI GenAI — every LOCUS_OCI_* variable below falls back to its
    # OCI_* equivalent (the OCI CLI standard) when unset. Closes #218.
    # So once you've run ``oci session authenticate --profile-name X``
    # and exported the resulting ``OCI_PROFILE``, every locus tutorial
    # picks the same profile up automatically.
    LOCUS_OCI_PROFILE      - OCI config profile name. Falls back to
                              OCI_PROFILE. Default: DEFAULT.
    LOCUS_OCI_AUTH_TYPE    - "api_key", "security_token",
                              "instance_principal", "resource_principal".
                              Falls back to OCI_AUTH_TYPE.
    LOCUS_OCI_REGION       - OCI region. Falls back to OCI_REGION.
                              Default: us-chicago-1.
    LOCUS_OCI_COMPARTMENT  - Compartment OCID. Falls back to
                              OCI_COMPARTMENT. Auto-derived from the
                              profile's tenancy when a profile is set;
                              required for instance/resource principal
                              modes.
    LOCUS_OCI_ENDPOINT     - Service endpoint URL. Falls back to
                              OCI_ENDPOINT. Only honored by the SDK
                              transport (OCIModel).
    LOCUS_OCI_TRANSPORT    - "v1" or "sdk" — force a specific transport.
                              Falls back to OCI_TRANSPORT. By default
                              the transport is picked automatically from
                              LOCUS_MODEL_ID: cohere.command-r-* → "sdk"
                              (OCIModel), everything else → "v1"
                              (OCIOpenAIModel).

    # OpenAI
    OPENAI_API_KEY         - OpenAI API key

Examples:
    # Run with mock (default - no credentials needed):
    python examples/tutorial_01_basic_agent.py

    # Run with OCI GenAI (V1 transport, OpenAI-compatible endpoint):
    export LOCUS_MODEL_PROVIDER=oci
    export LOCUS_MODEL_ID=openai.gpt-5.5-2026-04-23
    export LOCUS_OCI_PROFILE=MY_PROFILE
    python examples/tutorial_01_basic_agent.py

    # Run with OCI GenAI (SDK transport, required for Cohere R-series):
    export LOCUS_MODEL_PROVIDER=oci
    export LOCUS_MODEL_ID=cohere.command-r-plus-08-2024
    export LOCUS_OCI_PROFILE=MY_PROFILE
    export LOCUS_OCI_ENDPOINT=https://inference.generativeai.us-chicago-1.oci.oraclecloud.com
    python examples/tutorial_01_basic_agent.py

    # Run with OCI on an OCI VM / OKE node (workload identity):
    export LOCUS_MODEL_PROVIDER=oci
    export LOCUS_MODEL_ID=openai.gpt-5.5-2026-04-23
    export LOCUS_OCI_AUTH_TYPE=instance_principal
    export LOCUS_OCI_COMPARTMENT=ocid1.compartment.oc1...

    # Run with OpenAI:
    export LOCUS_MODEL_PROVIDER=openai
    export OPENAI_API_KEY=sk-...
    python examples/tutorial_01_basic_agent.py

See `docs/how-to/oci-models.md` for the full transport story.
"""

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from locus.core.events import ModelChunkEvent
from locus.core.messages import Message
from locus.models.base import ModelResponse


def _oci_env(name: str, default: str | None = None) -> str | None:
    """Read an OCI config setting from the env with a consistent fallback chain.

    Closes #218. Tutorials historically read ``LOCUS_OCI_*`` (the harness
    namespace) but the OCI CLI and most other tooling speak ``OCI_*``.
    Newcomers got bitten by having to maintain both. We now look up
    ``LOCUS_OCI_<name>`` first (keeps existing behaviour for users who
    already export the namespaced form), then fall back to the
    OCI-CLI-standard ``OCI_<name>``, then ``default``. This way a user
    who just typed ``oci session authenticate --profile-name DEFAULT``
    can run any tutorial without re-exporting variables.
    """
    return os.environ.get(f"LOCUS_OCI_{name}") or os.environ.get(f"OCI_{name}") or default


class MockModel(BaseModel):
    """
    Mock model for testing tutorials without API calls.

    Returns predetermined responses for common prompts.
    """

    max_tokens: int = 100
    temperature: float = 0.7

    # Simulated responses
    _responses: dict[str, str] = {
        "default": "This is a mock response for testing purposes.",
        "python": "Python is a high-level programming language known for readability.",
        "languages": "Python, JavaScript, and Rust are popular programming languages.",
        "math": "The answer is 42.",
        "2 + 2": "4",
        "5 * 5": "25",
        "square root": "12",
        "10%": "20",
    }

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Return a mock response based on the last message."""
        last_msg = messages[-1].content or "" if messages else ""
        response = self._get_response(last_msg.lower(), tools)
        return ModelResponse(
            message=Message.assistant(content=response),
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            stop_reason="end_turn",
        )

    def _get_response(self, prompt: str, tools: list[dict[str, Any]] | None) -> str:
        """Get appropriate response based on prompt content."""
        # Check for tool calls
        if tools and ("weather" in prompt or "calculate" in prompt):
            return self._get_tool_response(prompt, tools)

        # Match keywords to responses
        for keyword, response in self._responses.items():
            if keyword in prompt:
                return response
        return self._responses["default"]

    def _get_tool_response(self, prompt: str, tools: list[dict[str, Any]]) -> str:
        """Simulate tool usage response."""
        return "I'll use the available tools to help with that."

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ModelChunkEvent]:
        """Stream mock response in chunks."""
        response = await self.complete(messages, tools, **kwargs)
        content = response.content or ""

        # Yield in small chunks
        chunk_size = 10
        for i in range(0, len(content), chunk_size):
            yield ModelChunkEvent(content=content[i : i + chunk_size])
        yield ModelChunkEvent(done=True)


def check_structured_output_capable() -> None:
    """Exit cleanly with guidance if the current model cannot produce JSON.

    Guards against MockModel (plain text) and Cohere R-series (no constrained
    decoding support in OCI SDK transport).
    """
    provider = os.environ.get("LOCUS_MODEL_PROVIDER", "mock").lower()
    model_id = os.environ.get("LOCUS_MODEL_ID", "").lower()

    cohere_sdk = provider == "oci" and model_id.startswith("cohere.command-r")
    if provider != "mock" and not cohere_sdk:
        return

    reason = (
        "MockModel returns plain text and cannot demonstrate these features."
        if provider == "mock"
        else f"Cohere R-series ({model_id}) does not support constrained JSON decoding."
    )
    print(
        f"\n⚠  This tutorial requires structured-output (JSON schema) support.\n"
        f"   {reason}\n\n"
        "   Run with a model that supports constrained decoding:\n\n"
        "     export LOCUS_MODEL_PROVIDER=oci\n"
        "     export LOCUS_OCI_PROFILE=<your-profile>\n"
        "     export LOCUS_OCI_AUTH_TYPE=security_token   # or api_key\n"
        "     export LOCUS_OCI_REGION=us-chicago-1\n"
        "     export LOCUS_OCI_COMPARTMENT=<your-compartment-ocid>\n"
        "     export LOCUS_MODEL_ID=openai.gpt-5.5-2026-04-23\n"
        f"     python {Path(sys.argv[0]).name}\n"
    )
    sys.exit(0)


def get_model(**kwargs: Any) -> Any:
    """
    Get the configured model based on environment variables.

    Args:
        **kwargs: Override any model parameters (max_tokens, temperature, etc.)
                  Pass ``model_id="..."`` to use a specific model id without
                  changing ``LOCUS_MODEL_ID``.

    Returns:
        Configured model instance (MockModel, OCIModel, or OpenAIModel)
    """
    provider = os.environ.get("LOCUS_MODEL_PROVIDER", "mock").lower()

    if provider == "mock":
        kwargs.pop("model_id", None)  # MockModel ignores model_id
        return MockModel(**kwargs)
    elif provider == "oci":
        return _get_oci_model(**kwargs)
    elif provider == "openai":
        return _get_openai_model(**kwargs)
    elif provider == "anthropic":
        return _get_anthropic_model(**kwargs)
    else:
        raise ValueError(
            f"Unknown model provider: {provider}. Use 'mock', 'oci', 'openai', or 'anthropic'."
        )


def get_model_b(**kwargs: Any) -> Any:
    """Secondary model slot — typically a cheaper/faster variant for
    triage, routing, or color commentary in multi-agent tutorials.

    Reads ``LOCUS_MODEL_ID_B`` (set by the workbench's "Model B" slot).
    Falls back to ``LOCUS_MODEL_ID`` (= slot A) when unset, so tutorials
    that call ``get_model_b()`` still work in plain CLI runs where only
    one model is configured.
    """
    kwargs.setdefault(
        "model_id",
        os.environ.get("LOCUS_MODEL_ID_B") or os.environ.get("LOCUS_MODEL_ID", ""),
    )
    return get_model(**kwargs)


def get_model_c(**kwargs: Any) -> Any:
    """Tertiary model slot — same fall-through rules as :func:`get_model_b`,
    typically used for a judge / critic role distinct from both A and B."""
    kwargs.setdefault(
        "model_id",
        os.environ.get("LOCUS_MODEL_ID_C") or os.environ.get("LOCUS_MODEL_ID", ""),
    )
    return get_model(**kwargs)


def _pick_oci_transport(model_id: str) -> str:
    """Pick the right OCI transport for a model id.

    Cohere R-series models need the OCI SDK's proprietary chat shape and
    are routed through ``OCIModel``. Everything else (OpenAI / Meta / xAI
    / Mistral / Gemini, and non-R Cohere) goes through
    ``OCIOpenAIModel`` against ``/openai/v1/chat/completions``.

    ``LOCUS_OCI_TRANSPORT=v1|sdk`` overrides the automatic choice.
    """
    forced = _oci_env("TRANSPORT")
    if forced in ("v1", "sdk"):
        return forced
    lowered = model_id.lower()
    # DAC endpoint OCIDs and Cohere R-series both need the SDK
    # transport (DedicatedServingMode for the former, the proprietary
    # Cohere chat shape for the latter).
    if lowered.startswith(("ocid1.generativeaiendpoint.", "cohere.command-r")):
        return "sdk"
    return "v1"


def _get_oci_model(**kwargs: Any) -> Any:
    """Get an OCI GenAI model — picks V1 vs SDK transport per model family."""
    model_id = kwargs.pop("model_id", os.environ.get("LOCUS_MODEL_ID", "openai.gpt-5.5-2026-04-23"))
    transport = _pick_oci_transport(model_id)
    if transport == "v1":
        return _get_oci_v1_model(model_id, **kwargs)
    return _get_oci_sdk_model(model_id, **kwargs)


def _get_oci_v1_model(model_id: str, **kwargs: Any) -> Any:
    """Build an OCIOpenAIModel against /openai/v1/chat/completions."""
    from locus.models import OCIOpenAIModel

    region = _oci_env("REGION", "us-chicago-1") or "us-chicago-1"
    compartment = _oci_env("COMPARTMENT")
    auth_type = _oci_env("AUTH_TYPE", "") or ""

    if auth_type in ("instance_principal", "resource_principal"):
        if not compartment:
            msg = f"LOCUS_OCI_COMPARTMENT is required when LOCUS_OCI_AUTH_TYPE={auth_type}"
            raise ValueError(msg)
        return OCIOpenAIModel(
            model=model_id,
            auth_type=auth_type,
            compartment_id=compartment,
            region=region,
            **kwargs,
        )

    # Default: profile-based auth. compartment auto-derived from the
    # profile's tenancy unless overridden.
    profile = _oci_env("PROFILE", "DEFAULT") or "DEFAULT"
    return OCIOpenAIModel(
        model=model_id,
        profile=profile,
        compartment_id=compartment,
        region=region,
        **kwargs,
    )


def _get_oci_sdk_model(model_id: str, **kwargs: Any) -> Any:
    """Build an OCIModel against /20231130/actions/v1/chat (SDK transport)."""
    from locus.models import OCIAuthType, OCIModel

    profile = _oci_env("PROFILE", "DEFAULT") or "DEFAULT"
    auth_type_str = _oci_env("AUTH_TYPE", "api_key") or "api_key"
    compartment = _oci_env("COMPARTMENT")
    endpoint = _oci_env("ENDPOINT")
    # The OCI profile's home region is often *not* the GenAI region
    # (e.g. MY_PROFILE's us-ashburn-1 vs GenAI in us-chicago-1). Derive
    # the endpoint from LOCUS_OCI_REGION / OCI_REGION when no explicit
    # endpoint is set so cross-tenancy / cross-region session tokens
    # still hit the right service.
    if not endpoint:
        region = _oci_env("REGION")
        if region:
            endpoint = f"https://inference.generativeai.{region}.oci.oraclecloud.com"

    auth_type_map = {
        "api_key": OCIAuthType.API_KEY,
        "security_token": OCIAuthType.SECURITY_TOKEN,
        "session_token": OCIAuthType.SECURITY_TOKEN,
        "instance_principal": OCIAuthType.INSTANCE_PRINCIPAL,
        "resource_principal": OCIAuthType.RESOURCE_PRINCIPAL,
    }
    auth_type = auth_type_map.get(auth_type_str, OCIAuthType.API_KEY)

    return OCIModel(
        model_id=model_id,
        profile_name=profile,
        auth_type=auth_type,
        compartment_id=compartment,
        service_endpoint=endpoint,
        **kwargs,
    )


def _get_openai_model(**kwargs: Any) -> Any:
    """Get OpenAI model."""
    from locus.models import OpenAIModel

    model_id = kwargs.pop("model_id", os.environ.get("LOCUS_MODEL_ID", "gpt-4o"))
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable required")

    return OpenAIModel(
        model=model_id,
        api_key=api_key,
        **kwargs,
    )


def _get_anthropic_model(**kwargs: Any) -> Any:
    """Get Anthropic model."""
    from locus.models.native.anthropic import AnthropicModel

    model_id = kwargs.pop("model_id", os.environ.get("LOCUS_MODEL_ID", "claude-sonnet-4-20250514"))
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable required")

    return AnthropicModel(
        model=model_id,
        api_key=api_key,
        **kwargs,
    )


def print_config():
    """Print current configuration for debugging."""
    provider = os.environ.get("LOCUS_MODEL_PROVIDER", "mock")
    model_id = os.environ.get("LOCUS_MODEL_ID", "(default)")

    print(f"Model Provider: {provider}")

    if provider == "mock":
        print("Using mock model (no API calls)")
    else:
        print(f"Model ID: {model_id}")

        if provider == "oci":
            profile = os.environ.get("LOCUS_OCI_PROFILE", "DEFAULT")
            auth_type = os.environ.get("LOCUS_OCI_AUTH_TYPE", "api_key")
            print(f"OCI Profile: {profile}")
            print(f"OCI Auth Type: {auth_type}")
