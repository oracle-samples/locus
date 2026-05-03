import type { Pattern, ProviderConfig, RunResponse } from "./types";

export async function listPatterns(): Promise<Pattern[]> {
  const r = await fetch("/api/patterns");
  if (!r.ok) throw new Error(`patterns ${r.status}`);
  return (await r.json()) as Pattern[];
}

export async function runPattern(
  pattern: string,
  prompt: string,
  provider: ProviderConfig,
): Promise<RunResponse> {
  const r = await fetch(`/api/run/${encodeURIComponent(pattern)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, provider }),
  });
  const text = await r.text();
  if (!r.ok) {
    let detail = text;
    try {
      detail = (JSON.parse(text) as { detail?: string }).detail ?? text;
    } catch {
      /* fall through */
    }
    throw new Error(`${r.status}: ${detail}`);
  }
  return JSON.parse(text) as RunResponse;
}
