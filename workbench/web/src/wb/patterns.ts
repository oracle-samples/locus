/** Patterns sidebar + run panel.
 *
 *  Lists the eight SDK patterns from /api/patterns. Clicking one loads
 *  a prompt-input panel; hitting Run calls POST /api/run/{id} and
 *  streams the reply into the output card.
 */
import { listPatterns, runPattern, streamPattern, type Pattern } from "../api";
import { loadProvider } from "../settings";
import { $ } from "./dom";

let patterns: Pattern[] = [];
let current: Pattern | null = null;
let running = false;
let cancelStream: (() => void) | null = null;

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

function sidePatterns(): HTMLElement {
  return $("#side-patterns");
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

export async function bootstrapPatterns(): Promise<void> {
  try {
    patterns = await listPatterns();
    console.info(`[wb/patterns] loaded ${patterns.length} patterns`);
    renderList();
    if (patterns.length) {
      await selectPattern(patterns[0].id);
    }
  } catch (err) {
    console.error("[wb/patterns] catalog load failed", err);
    sidePatterns().innerHTML = `<div style="color: var(--or-red-deep); font-size:0.8rem; padding: 0.5rem">${(err as Error).message}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Pattern selection
// ---------------------------------------------------------------------------

async function selectPattern(id: string): Promise<void> {
  const p = patterns.find((x) => x.id === id);
  if (!p) return;
  current = p;
  renderList();
  renderDetail(p);
  $("#crumbs").textContent = `Workbench · Pattern · ${p.title}`;
  document
    .querySelector<HTMLElement>(`[data-testid="pattern-${p.id}"]`)
    ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// ---------------------------------------------------------------------------
// Sidebar list
// ---------------------------------------------------------------------------

function renderList(): void {
  const sidebar = sidePatterns();
  sidebar.innerHTML = "";
  for (const p of patterns) {
    const item = document.createElement("div");
    item.className = `side__item${current?.id === p.id ? " side__item--active" : ""}`;
    item.dataset.testid = `pattern-${p.id}`;
    const streamBadge = p.streamable
      ? `<span class="pill" style="font-size:0.6rem;padding:0 0.4rem">stream</span>`
      : "";
    item.innerHTML = `
      <div style="flex:1;min-width:0">
        <div style="font-size:0.82rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.title}</div>
        <div style="font-size:0.7rem;color:var(--or-text-mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.summary}</div>
      </div>
      ${streamBadge}
    `;
    item.addEventListener("click", () => void selectPattern(p.id));
    sidebar.appendChild(item);
  }
}

// ---------------------------------------------------------------------------
// Main detail panel
// ---------------------------------------------------------------------------

function renderDetail(p: Pattern): void {
  const view = $("#patterns-view");

  // Title
  ($("#pattern-title") as HTMLElement).textContent = p.title;
  ($("#pattern-sub") as HTMLElement).textContent = p.summary;

  // Reset output
  clearOutput();

  // Suggested prompt placeholder
  const promptEl = $<HTMLTextAreaElement>("#pattern-prompt");
  promptEl.placeholder = _suggestedPrompt(p.id);

  // Streamable badge
  const badge = $("#pattern-stream-badge");
  badge.style.display = p.streamable ? "inline-flex" : "none";

  view.style.display = "";
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

function clearOutput(): void {
  const out = $("#pattern-output");
  out.textContent = "";
  out.style.display = "none";
  const err = $("#pattern-error");
  err.style.display = "none";
  err.textContent = "";
}

function setRunning(r: boolean): void {
  running = r;
  const runBtn = $<HTMLButtonElement>("#pattern-run-btn");
  const stopBtn = $<HTMLButtonElement>("#pattern-stop-btn");
  runBtn.style.display = r ? "none" : "";
  stopBtn.style.display = r ? "" : "none";
}

export function installPatternRunControls(): void {
  const runBtn = $<HTMLButtonElement>("#pattern-run-btn");
  const stopBtn = $<HTMLButtonElement>("#pattern-stop-btn");

  runBtn.addEventListener("click", () => void doRun());
  stopBtn.addEventListener("click", () => {
    cancelStream?.();
    cancelStream = null;
    setRunning(false);
  });
}

async function doRun(): Promise<void> {
  if (!current || running) return;

  const provider = loadProvider();
  if (!provider) {
    showError("No provider configured. Open Provider settings and save a key.");
    return;
  }

  const prompt = ($<HTMLTextAreaElement>("#pattern-prompt").value || "").trim()
    || $<HTMLTextAreaElement>("#pattern-prompt").placeholder;

  clearOutput();
  setRunning(true);

  const out = $("#pattern-output");
  out.style.display = "pre";
  out.textContent = "Running…";

  try {
    if (current.streamable) {
      // Stream token-by-token events
      let fullText = "";
      cancelStream = await streamPattern(
        current.id,
        prompt,
        provider,
        (ev) => {
          const chunk = ev.extra?.["content"] as string | undefined;
          if (chunk) {
            fullText += chunk;
            out.textContent = fullText;
          }
        },
        (finalReply) => {
          out.textContent = finalReply || fullText || "(no reply)";
          setRunning(false);
          cancelStream = null;
        },
        (msg) => {
          showError(msg);
          setRunning(false);
          cancelStream = null;
        },
      );
    } else {
      // One-shot (memory_manager, orchestrator, etc.)
      const result = await runPattern(current.id, prompt, provider);
      out.textContent = result.reply || "(no reply)";
      setRunning(false);
    }
  } catch (err) {
    showError((err as Error).message);
    setRunning(false);
  }
}

function showError(msg: string): void {
  const err = $("#pattern-error");
  err.textContent = msg;
  err.style.display = "block";
}

// ---------------------------------------------------------------------------
// Suggested prompts per pattern
// ---------------------------------------------------------------------------

function _suggestedPrompt(id: string): string {
  const PROMPTS: Record<string, string> = {
    memory_manager:
      "I'm a senior Python engineer. I prefer short answers and real DB connections — no mocks. What's the CAP theorem?",
    agent: "Explain the difference between TCP and UDP in two sentences.",
    agent_with_tools: "What is 42 multiplied by 7? Also reverse the word 'locus'.",
    composition: "Explain how large language models work.",
    orchestrator: "Write a short paragraph about multi-agent AI systems.",
    stategraph_loop: "Explain why immutability matters in functional programming.",
    map_reduce: "Review this function: def add(a, b): return a + b",
    structured_output: "Python vs JavaScript: which wins for backend work?",
  };
  return PROMPTS[id] ?? "Enter a prompt…";
}
