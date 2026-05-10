# Copyright (c) 2025, 2026 Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v1.0 as shown at
# https://oss.oracle.com/licenses/upl/
"""
Tutorial 29: Model Providers — OCI, OpenAI, Anthropic, Ollama

This tutorial covers:
- OCI GenAI — two transports:
    * OCIOpenAIModel — OpenAI-compatible /openai/v1 endpoint, real SSE
      streaming, day-0 model support (OpenAI / Meta / xAI / Mistral /
      Gemini / non-R Cohere).
    * OCIModel — OCI SDK transport, required for Cohere R-series.
- OpenAI: GPT-4o, o1, o3, gpt-5.* direct API
- Anthropic: Claude models
- Ollama: Local LLMs (Llama, Mistral, Gemma)
- Model registry: get_model("provider:model_name") — auto-routes OCI
  ids to the right transport.

Prerequisites:
- API keys for the providers you want to use

Difficulty: Beginner
"""

import asyncio
import time

from config import get_model as get_configured_model

from locus.agent import Agent
from locus.models.registry import get_model, list_providers


def _llm_call(
    prompt: str, *, system: str = "Reply in one short sentence.", max_tokens: int = 80
) -> str:
    """Helper: real model call with timing/token banner — used by every Part."""
    agent = Agent(model=get_configured_model(max_tokens=max_tokens), system_prompt=system)
    t0 = time.perf_counter()
    res = agent.run_sync(prompt)
    dt = time.perf_counter() - t0
    print(
        f"  [model call: {dt:.2f}s · {res.metrics.prompt_tokens}→{res.metrics.completion_tokens} tokens]"
    )
    return res.message.strip()


# =============================================================================
# Part 1: Available providers
# =============================================================================


def example_providers():
    """List available model providers."""
    print("=== Available Providers ===\n")

    providers = list_providers()
    print(f"Registered providers: {providers}")
    print(
        f"AI rationale: {_llm_call('In one sentence, why do AI SDKs ship a model registry instead of hard-coding one provider?')}"
    )

    print("\nUsage:")
    print('  model = get_model("openai:gpt-4o")')
    print('  model = get_model("oci:openai.gpt-5", profile="DEFAULT")  # → OCIOpenAIModel')
    print(
        '  model = get_model("oci:cohere.command-r-plus", '
        'profile_name="DEFAULT", auth_type="api_key")  # → OCIModel'
    )
    print('  model = get_model("anthropic:claude-sonnet-4-20250514")')
    print('  model = get_model("ollama:llama3.3")')
    print()
    print("The 'oci:' prefix auto-routes by model family — 'cohere.command-r-*'")
    print("uses OCIModel (SDK transport), everything else uses OCIOpenAIModel")
    print("(/openai/v1). See docs/how-to/oci-models.md.")


# =============================================================================
# Part 2: Direct provider usage
# =============================================================================


def example_direct():
    """Use providers directly without the registry."""
    print("\n=== Direct Provider Usage ===\n")
    print(
        f"AI rationale: {_llm_call('In one sentence, when would you instantiate OCIOpenAIModel directly instead of via the registry?')}"
    )

    # OCI GenAI — V1 transport (recommended for OpenAI/Meta/xAI/Mistral/Gemini)
    print("OCI GenAI — V1 (/openai/v1):")
    print("  from locus.models import OCIOpenAIModel")
    print('  model = OCIOpenAIModel(model="openai.gpt-5", profile="DEFAULT")')
    print()
    print("  # Workload identity on OCI VM / OKE / Functions:")
    print("  model = OCIOpenAIModel(")
    print('      model="openai.gpt-5",')
    print('      auth_type="instance_principal",   # or "resource_principal"')
    print('      compartment_id="ocid1.compartment.oc1...",')
    print("  )")

    # OCI GenAI — SDK transport (required for Cohere R-series)
    print("\nOCI GenAI — SDK (/20231130/actions/v1, Cohere R-series only):")
    print("  from locus.models import OCIModel")
    print("  model = OCIModel(")
    print('      model_id="cohere.command-r-plus-08-2024",')
    print('      profile_name="DEFAULT",')
    print('      auth_type="api_key",')
    print("  )")

    # OpenAI (requires OPENAI_API_KEY)
    print("\nOpenAI (direct API, requires OPENAI_API_KEY):")
    print("  from locus.models import OpenAIModel")
    print('  model = OpenAIModel(model="gpt-4o")')

    # Anthropic (requires ANTHROPIC_API_KEY)
    print("\nAnthropic (requires ANTHROPIC_API_KEY):")
    print("  from locus.models.native.anthropic import AnthropicModel")
    print('  model = AnthropicModel(model="claude-sonnet-4-20250514")')

    # Ollama (requires local Ollama server)
    print("\nOllama (requires local Ollama server):")
    print("  from locus.models.native.ollama import OllamaModel")
    print('  model = OllamaModel(model="llama3.3")')


async def example_live_call() -> None:
    """Actually call whichever provider is configured in the environment."""
    print("\n=== Live Provider Call ===\n")
    model = get_configured_model(max_tokens=80)
    agent = Agent(
        model=model,
        system_prompt="Reply with one short sentence.",
    )
    import time as _t

    t0 = _t.perf_counter()
    result = agent.run_sync("Name two strengths of OCI Generative AI.")
    dt = _t.perf_counter() - t0
    print(f"  Model class: {type(model).__name__}")
    print(f"  Reply:       {result.message.strip()}")
    print(
        f"  [model call:   {dt:.2f}s · {result.metrics.prompt_tokens}→{result.metrics.completion_tokens} tokens]"
    )


if __name__ == "__main__":
    example_providers()
    example_direct()
    asyncio.run(example_live_call())
