export type Pattern = {
  id: string;
  title: string;
  tutorial: number;
  summary: string;
  streamable: boolean;
};

export type ProviderType = "openai" | "anthropic" | "oci-session" | "oci-apikey";

export type OciTransport = "auto" | "v1" | "sdk";

export type ProviderConfig = {
  provider: ProviderType;
  model: string;
  // Optional secondary models. Empty/undefined means "fall back to model".
  // Same provider + credentials as the primary slot.
  model_b?: string;
  model_c?: string;
  api_key?: string;
  profile?: string;
  region?: string;
  compartment_id?: string;
  oci_transport?: OciTransport;
};

export type RunEvent = {
  kind: string;
  text: string;
  extra?: Record<string, unknown>;
};

export type RunResponse = {
  reply: string;
  events: RunEvent[];
  model?: string;
  provider?: string;
};
