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

from locus.models.registry import get_model, list_providers


# =============================================================================
# Part 1: Available providers
# =============================================================================


def example_providers():
    """List available model providers."""
    print("=== Available Providers ===\n")

    providers = list_providers()
    print(f"Registered providers: {providers}")

    print("\nUsage:")
    print('  model = get_model("openai:gpt-4o")')
    print('  model = get_model("oci:openai.gpt-5.5", profile="DEFAULT")  # → OCIOpenAIModel')
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

    # OCI GenAI — V1 transport (recommended for OpenAI/Meta/xAI/Mistral/Gemini)
    print("OCI GenAI — V1 (/openai/v1):")
    print("  from locus.models import OCIOpenAIModel")
    print('  model = OCIOpenAIModel(model="openai.gpt-5.5", profile="DEFAULT")')
    print()
    print("  # Workload identity on OCI VM / OKE / Functions:")
    print("  model = OCIOpenAIModel(")
    print('      model="openai.gpt-5.5",')
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


if __name__ == "__main__":
    example_providers()
    example_direct()
