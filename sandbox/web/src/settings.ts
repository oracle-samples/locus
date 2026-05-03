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
      return "gpt-5";
    case "anthropic":
      return "claude-sonnet-4-6";
    case "oci-session":
    case "oci-apikey":
      return "openai.gpt-5";
  }
}

export function describeProvider(cfg: ProviderConfig): string {
  switch (cfg.provider) {
    case "openai":
      return `OpenAI · ${cfg.model}`;
    case "anthropic":
      return `Anthropic · ${cfg.model}`;
    case "oci-session":
      return `OCI session · ${cfg.profile} · ${cfg.model}`;
    case "oci-apikey":
      return `OCI api-key · ${cfg.profile} · ${cfg.model}`;
  }
}
