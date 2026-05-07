import type { ProviderConfig, ProviderType } from "./types";

// API keys are session-only (never written to localStorage).
// Non-sensitive OCI fields persist across reloads.
const OCI_PREFS_KEY = "locus.workbench.oci-prefs";

type OciPrefs = {
  provider?: string;
  profile?: string;
  compartment_id?: string;
  region?: string;
  oci_transport?: string;
  model?: string;
  model_b?: string;
  model_c?: string;
};

function saveOciPrefs(cfg: ProviderConfig): void {
  if (cfg.provider !== "oci-session" && cfg.provider !== "oci-apikey") return;
  localStorage.setItem(
    OCI_PREFS_KEY,
    JSON.stringify({
      provider: cfg.provider,
      profile: cfg.profile,
      compartment_id: cfg.compartment_id,
      region: cfg.region,
      oci_transport: cfg.oci_transport,
      model: cfg.model,
      model_b: cfg.model_b ?? "",
      model_c: cfg.model_c ?? "",
    } satisfies OciPrefs),
  );
}

let memoryProvider: ProviderConfig | null = null;

export function loadProvider(): ProviderConfig | null {
  if (memoryProvider) return memoryProvider;
  try {
    const raw = localStorage.getItem(OCI_PREFS_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as OciPrefs;
    if (p.provider !== "oci-session" && p.provider !== "oci-apikey") return null;
    return {
      provider: p.provider as ProviderConfig["provider"],
      profile: p.profile ?? "DEFAULT",
      compartment_id: p.compartment_id ?? "",
      region: p.region ?? "us-chicago-1",
      oci_transport: (p.oci_transport ?? "v1") as ProviderConfig["oci_transport"],
      model: p.model ?? "openai.gpt-5.5-2026-04-23",
      model_b: p.model_b ?? "",
      model_c: p.model_c ?? "",
    };
  } catch {
    return null;
  }
}

export function saveProvider(cfg: ProviderConfig): void {
  memoryProvider = cfg;
  saveOciPrefs(cfg);
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
