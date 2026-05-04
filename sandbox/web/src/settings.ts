import type { ProviderConfig, ProviderType } from "./types";

// Provider config (including any pasted API key) is intentionally
// session-only. We never persist it to localStorage / sessionStorage —
// closing the tab discards it. This is an opsec choice: a key sitting
// in localStorage on a shared machine is leakage waiting to happen.
let memoryProvider: ProviderConfig | null = null;

export function loadProvider(): ProviderConfig | null {
  return memoryProvider;
}

export function saveProvider(cfg: ProviderConfig): void {
  memoryProvider = cfg;
}

export function defaultModelFor(p: ProviderType): string {
  switch (p) {
    case "openai":
      return "gpt-5.5";
    case "anthropic":
      return "claude-sonnet-4-6";
    case "oci-session":
    case "oci-apikey":
      return "openai.gpt-5.5-2026-04-23";
  }
}

/** A full prefill for a freshly-selected provider. Per-provider sensible defaults
 *  for the OCI-shaped fields so the user only has to drop a key in for OpenAI /
 *  Anthropic, or just confirm Save for the standard OCI session path. */
export function defaultsFor(p: ProviderType): ProviderConfig {
  switch (p) {
    case "openai":
      return { provider: "openai", model: "gpt-5.5" };
    case "anthropic":
      return { provider: "anthropic", model: "claude-sonnet-4-6" };
    case "oci-session":
      return {
        provider: "oci-session",
        model: "openai.gpt-5.5-2026-04-23",
        profile: "DEFAULT",
        region: "us-chicago-1",
        compartment_id: "",
        oci_transport: "v1",
      };
    case "oci-apikey":
      return {
        provider: "oci-apikey",
        model: "openai.gpt-5.5-2026-04-23",
        profile: "DEFAULT",
        region: "us-chicago-1",
        compartment_id: "",
        oci_transport: "v1",
      };
  }
}

export function describeProvider(cfg: ProviderConfig): string {
  switch (cfg.provider) {
    case "openai":
      return `OpenAI · ${cfg.model}`;
    case "anthropic":
      return `Anthropic · ${cfg.model}`;
    case "oci-session": {
      const tx = cfg.oci_transport && cfg.oci_transport !== "v1" ? ` · ${cfg.oci_transport}` : "";
      return `OCI session · ${cfg.profile} · ${cfg.model}${tx}`;
    }
    case "oci-apikey": {
      const tx = cfg.oci_transport && cfg.oci_transport !== "v1" ? ` · ${cfg.oci_transport}` : "";
      return `OCI api-key · ${cfg.profile} · ${cfg.model}${tx}`;
    }
  }
}
