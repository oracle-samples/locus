export type Pattern = {
  id: string;
  title: string;
  tutorial: number;
  summary: string;
  streamable: boolean;
};

export type ProviderType = "openai" | "anthropic" | "oci-session" | "oci-apikey";

export type ProviderConfig = {
  provider: ProviderType;
  model: string;
  api_key?: string;
  profile?: string;
  region?: string;
  compartment_id?: string;
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
