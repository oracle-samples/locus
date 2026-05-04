import type { ProviderConfig, ProviderType } from "./types";

const KEY = "locus.sandbox.provider";

export function loadProvider(): ProviderConfig | null {
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ProviderConfig;
  } catch {
    return null;
  }
}

export function saveProvider(cfg: ProviderConfig): void {
  localStorage.setItem(KEY, JSON.stringify(cfg));
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
        profile: "BOAT-OC1",
        region: "us-chicago-1",
        compartment_id:
          "ocid1.compartment.oc1..aaaaaaaandceai675euuovyyazlymnglde2xknsq35rni43zzmwdhxxu4v7q",
        oci_transport: "auto",
      };
    case "oci-apikey":
      return {
        provider: "oci-apikey",
        model: "openai.gpt-5.5-2026-04-23",
        profile: "DEFAULT",
        region: "us-chicago-1",
        compartment_id: "",
        oci_transport: "auto",
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
      const tx = cfg.oci_transport && cfg.oci_transport !== "auto" ? ` · ${cfg.oci_transport}` : "";
      return `OCI session · ${cfg.profile} · ${cfg.model}${tx}`;
    }
    case "oci-apikey": {
      const tx = cfg.oci_transport && cfg.oci_transport !== "auto" ? ` · ${cfg.oci_transport}` : "";
      return `OCI api-key · ${cfg.profile} · ${cfg.model}${tx}`;
    }
  }
}
