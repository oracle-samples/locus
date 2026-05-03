import type { Pattern, ProviderConfig, RunEvent, RunResponse } from "./types";

export async function listPatterns(): Promise<Pattern[]> {
  const r = await fetch("/api/patterns");
  if (!r.ok) throw new Error(`patterns ${r.status}`);
  return (await r.json()) as Pattern[];
}

export async function listModels(provider: ProviderConfig): Promise<{ models: string[]; error?: string }> {
  const r = await fetch("/api/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider }),
  });
  if (!r.ok) throw new Error(`models ${r.status}`);
  const data = (await r.json()) as { models: string[]; error?: string };
  return data;
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

export async function streamPattern(
  pattern: string,
  prompt: string,
  provider: ProviderConfig,
  onEvent: (e: RunEvent) => void,
  onDone: (final: string) => void,
  onError: (msg: string) => void,
): Promise<() => void> {
  const ctrl = new AbortController();
  let final = "";
  try {
    const r = await fetch(`/api/run/${encodeURIComponent(pattern)}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, provider }),
      signal: ctrl.signal,
    });
    if (!r.ok || !r.body) {
      onError(`${r.status}: ${await r.text()}`);
      return () => ctrl.abort();
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    void (async () => {
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let nl: number;
          while ((nl = buf.indexOf("\n\n")) !== -1) {
            const block = buf.slice(0, nl);
            buf = buf.slice(nl + 2);
            for (const line of block.split("\n")) {
              if (!line.startsWith("data:")) continue;
              const payload = line.slice(5).trim();
              if (!payload) continue;
              try {
                const ev = JSON.parse(payload) as Record<string, unknown>;
                const kind = (ev.type as string) ?? "Other";
                const text =
                  (ev.tool_name as string) ??
                  (ev.final_message as string) ??
                  (ev.content as string) ??
                  (ev.reasoning as string) ??
                  (ev.message as string) ??
                  "";
                onEvent({ kind, text, extra: ev });
                if (kind === "TerminateEvent" && typeof ev.final_message === "string") {
                  final = ev.final_message;
                }
              } catch {
                /* keepalive */
              }
            }
          }
        }
        onDone(final);
      } catch (err) {
        if ((err as Error).name !== "AbortError") onError((err as Error).message);
      }
    })();
  } catch (err) {
    onError((err as Error).message);
  }
  return () => ctrl.abort();
}
