import type { Pattern, ProviderConfig, RunEvent, RunResponse } from "./types";

export async function listPatterns(): Promise<Pattern[]> {
  const r = await fetch("/api/patterns");
  if (!r.ok) throw new Error(`patterns ${r.status}`);
  return (await r.json()) as Pattern[];
}

export type Tutorial = {
  id: string;
  number: number;
  title: string;
  summary: string;
  filename: string;
  needs_stdin?: boolean;
};

export type TutorialDetail = Tutorial & { source: string };

export async function listTutorials(): Promise<Tutorial[]> {
  const r = await fetch("/api/tutorials");
  if (!r.ok) throw new Error(`tutorials ${r.status}`);
  return (await r.json()) as Tutorial[];
}

export async function getTutorial(id: string): Promise<TutorialDetail> {
  const r = await fetch(`/api/tutorials/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(`tutorial ${r.status}`);
  return (await r.json()) as TutorialDetail;
}

export type WorkbenchEvent =
  | { type: "stdout"; text: string }
  | { type: "stderr"; text: string }
  | { type: "exit"; code: number }
  | { type: "error"; text: string }
  | { type: "runStarted"; run_id: string };

export async function respondToInterrupt(runId: string, response: unknown): Promise<void> {
  const r = await fetch(`/api/tutorials/runs/${encodeURIComponent(runId)}/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`respond ${r.status}: ${t}`);
  }
}

export function runTutorialSource(
  source: string,
  provider: ProviderConfig,
  onEvent: (e: WorkbenchEvent) => void,
  onClose: () => void,
): () => void {
  const ctrl = new AbortController();
  void (async () => {
    try {
      const r = await fetch("/api/tutorials/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, provider, timeout_seconds: 180 }),
        signal: ctrl.signal,
      });
      if (!r.ok || !r.body) {
        onEvent({ type: "error", text: `${r.status}: ${await r.text()}` });
        onClose();
        return;
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl: number;
        while ((nl = buf.indexOf("\n\n")) !== -1) {
          const block = buf.slice(0, nl);
          buf = buf.slice(nl + 2);
          for (const line of block.split("\n")) {
            if (!line.startsWith("data:")) continue;
            try {
              onEvent(JSON.parse(line.slice(5).trim()) as WorkbenchEvent);
            } catch {
              /* keepalive */
            }
          }
        }
      }
      onClose();
    } catch (err) {
      if ((err as Error).name !== "AbortError") onEvent({ type: "error", text: (err as Error).message });
      onClose();
    }
  })();
  return () => ctrl.abort();
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
