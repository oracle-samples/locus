import { EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import { oneDark } from "@codemirror/theme-one-dark";

import { getTutorial, listTutorials, runTutorialSource, type Tutorial, type TutorialDetail } from "./api";
import { describeProvider, loadProvider } from "./settings";
import type { ProviderConfig } from "./types";

const $ = <T extends HTMLElement = HTMLElement>(sel: string): T => {
  const el = document.querySelector<T>(sel);
  if (!el) throw new Error(`missing: ${sel}`);
  return el;
};

const sideTutorials = $("#side-tutorials");
const search = $<HTMLInputElement>("#tutorial-search");
const wbTitle = $("#wb-title");
const wbSub = $("#wb-sub");
const wbProviderPill = $("#wb-provider-pill");
const wbStatus = $("#wb-status");
const wbRunBtn = $<HTMLButtonElement>("#wb-run-btn");
const wbStopBtn = $<HTMLButtonElement>("#wb-stop-btn");
const wbResetBtn = $<HTMLButtonElement>("#wb-reset-btn");
const wbOutput = $("#wb-output");
const wbOutputPill = $("#wb-output-pill");
const wbEditorMount = $("#wb-editor");

let editor: EditorView | null = null;
let tutorials: Tutorial[] = [];
let current: TutorialDetail | null = null;
let cancelRun: (() => void) | null = null;

function ensureEditor(initial = "") {
  if (editor) return editor;
  const state = EditorState.create({
    doc: initial,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      python(),
      oneDark,
      keymap.of([...defaultKeymap, ...historyKeymap]),
      // Match the output panel's surface so editor + output share the
      // same dark canvas (no jarring colour seam between them).
      EditorView.theme({
        "&": { fontSize: "13px", height: "100%", backgroundColor: "#1b1a18" },
        ".cm-scroller": { fontFamily: "JetBrains Mono, ui-monospace, Menlo, monospace" },
        ".cm-gutters": { backgroundColor: "#1b1a18", borderRight: "1px solid #2a2823" },
        ".cm-content": { caretColor: "#f0cc71" },
        ".cm-cursor, .cm-dropCursor": { borderLeftColor: "#f0cc71" },
        ".cm-activeLine": { backgroundColor: "rgba(240, 204, 113, 0.06)" },
        ".cm-activeLineGutter": { backgroundColor: "rgba(240, 204, 113, 0.06)" },
      }),
    ],
  });
  editor = new EditorView({ state, parent: wbEditorMount });
  return editor;
}

function setEditorContent(text: string) {
  const ed = ensureEditor(text);
  ed.dispatch({
    changes: { from: 0, to: ed.state.doc.length, insert: text },
    // Park the cursor at the very top, then scroll line 1 into view —
    // otherwise CodeMirror keeps whatever selection was around from the
    // previous tutorial and the user sees the bottom of the file.
    selection: { anchor: 0 },
    effects: EditorView.scrollIntoView(0, { y: "start" }),
  });
  // Hook for playwright / programmatic edits.
  (window as unknown as { __wb: { setSource: (t: string) => void; getSource: () => string } }).__wb = {
    setSource: setEditorContent,
    getSource: getEditorContent,
  };
}

function getEditorContent(): string {
  return editor?.state.doc.toString() ?? "";
}

function renderProviderPill() {
  const provider = loadProvider();
  if (provider) {
    wbProviderPill.className = "pill pill--up";
    wbProviderPill.innerHTML = `<span class="pill__dot"></span>${describeProvider(provider)}`;
    wbProviderPill.style.display = "inline-flex";
  } else {
    wbProviderPill.className = "pill pill--down";
    wbProviderPill.innerHTML = `<span class="pill__dot"></span>no provider`;
    wbProviderPill.style.display = "inline-flex";
  }
}

function renderList(filter: string) {
  sideTutorials.innerHTML = "";
  const q = filter.trim().toLowerCase();
  for (const t of tutorials) {
    if (q && !`${t.number} ${t.title} ${t.id}`.toLowerCase().includes(q)) continue;
    const item = document.createElement("div");
    item.className = `side__item${current?.id === t.id ? " side__item--active" : ""}`;
    item.dataset.testid = `tutorial-${t.id}`;
    item.innerHTML = `
      <span style="font-family: var(--mono); font-size: 0.7rem; color: var(--or-text-mute); min-width: 1.6rem">${String(
        t.number,
      ).padStart(2, "0")}</span>
      <span style="font-size: 0.82rem">${t.title.replace(/^Tutorial \d+:\s*/i, "")}</span>
    `;
    item.addEventListener("click", () => void selectTutorial(t.id));
    sideTutorials.appendChild(item);
  }
}

async function selectTutorial(id: string) {
  try {
    current = await getTutorial(id);
  } catch (err) {
    wbStatus.textContent = `failed to load: ${(err as Error).message}`;
    return;
  }
  wbTitle.textContent = current.title;
  wbSub.textContent = current.summary || `${current.filename}`;
  setEditorContent(current.source);
  wbOutput.innerHTML = "";
  wbOutputPill.style.display = "none";
  wbStatus.textContent = `loaded ${current.filename}`;
  renderList(search.value);
}

const LE_PREFIX = "__LE__:";

function appendOutput(line: string, kind: "stdout" | "stderr" | "exit" | "error") {
  // Detect locus-event lines emitted by the workbench bootstrap.
  if (kind === "stdout" && line.startsWith(LE_PREFIX)) {
    try {
      const ev = JSON.parse(line.slice(LE_PREFIX.length)) as Record<string, unknown>;
      appendEvent(ev);
      return;
    } catch {
      /* fall through to plain print */
    }
  }
  const span = document.createElement("span");
  span.className = `ln ln--${kind}`;
  span.textContent = `${line}\n`;
  wbOutput.appendChild(span);
  wbOutput.scrollTop = wbOutput.scrollHeight;
}

let liveChunkEl: HTMLSpanElement | null = null;

function ensureLiveChunkEl(): HTMLSpanElement {
  if (liveChunkEl && liveChunkEl.isConnected) return liveChunkEl;
  liveChunkEl = document.createElement("span");
  liveChunkEl.className = "ln ln--chunk ln--chunk--live";
  liveChunkEl.dataset.testid = "live-chunk";
  wbOutput.appendChild(liveChunkEl);
  return liveChunkEl;
}

function closeLiveChunk() {
  if (liveChunkEl?.isConnected && liveChunkEl.textContent) {
    // Strip the "live" modifier (the blinking caret pseudo-element) and
    // add a trailing newline so the next chip/line lands on its own row.
    liveChunkEl.classList.remove("ln--chunk--live");
    liveChunkEl.appendChild(document.createTextNode("\n"));
  }
  liveChunkEl = null;
}

export function endLiveStream() {
  // Called from the run finalizer so the caret stops blinking even when
  // the agent loop never emits TerminateEvent (raw stdout, errors, etc.).
  if (liveChunkEl?.isConnected) {
    liveChunkEl.classList.remove("ln--chunk--live");
    liveChunkEl = null;
  }
}

function appendEvent(ev: Record<string, unknown>) {
  const kind = (ev.type as string) ?? "Event";
  if (kind === "ModelChunkEvent") {
    const piece = (ev.content as string | undefined) ?? "";
    if (!piece) return;
    const node = ensureLiveChunkEl();
    // Each chunk lands as its own span with a brief fade-in animation,
    // so the user sees the model spitting tokens in real time.
    const span = document.createElement("span");
    span.className = "chunk-piece";
    span.textContent = piece;
    node.appendChild(span);
    wbOutput.scrollTop = wbOutput.scrollHeight;
    return;
  }
  // Any non-chunk event terminates the current live transcript so the
  // tag chip lands on its own line below.
  closeLiveChunk();
  const text =
    (ev.tool_name as string) ??
    (ev.final_message as string) ??
    (ev.content as string) ??
    (ev.reasoning as string) ??
    (ev.message as string) ??
    "";
  const row = document.createElement("span");
  row.className = "ln ln--event";
  const tag = document.createElement("span");
  tag.className = `event__kind ${
    kind === "TerminateEvent"
      ? "event__kind--terminate"
      : kind.startsWith("Tool")
        ? "event__kind--tool"
        : ""
  }`;
  tag.textContent = kind.replace("Event", "");
  const body = document.createElement("span");
  body.className = "event__body";
  body.textContent = ` ${text}`;
  row.appendChild(tag);
  row.appendChild(body);
  row.appendChild(document.createTextNode("\n"));
  wbOutput.appendChild(row);
  wbOutput.scrollTop = wbOutput.scrollHeight;
}

function setRunning(running: boolean) {
  wbRunBtn.style.display = running ? "none" : "inline-flex";
  wbStopBtn.style.display = running ? "inline-flex" : "none";
}

async function runEdited() {
  const provider = loadProvider();
  if (!provider) {
    wbStatus.textContent = "set provider settings first.";
    return;
  }
  const source = getEditorContent();
  if (!source.trim()) {
    wbStatus.textContent = "editor is empty.";
    return;
  }
  wbOutput.innerHTML = "";
  liveChunkEl = null;
  wbOutputPill.style.display = "inline-flex";
  wbOutputPill.className = "pill pill--busy";
  wbOutputPill.innerHTML = `<span class="pill__dot"></span>running…`;
  setRunning(true);

  let stdoutLines = 0;
  let stderrLines = 0;
  cancelRun = runTutorialSource(
    source,
    provider as ProviderConfig,
    (e) => {
      if (e.type === "exit") {
        endLiveStream();
        appendOutput(`process exited with code ${e.code}`, "exit");
        wbOutputPill.className = e.code === 0 ? "pill pill--up" : "pill pill--down";
        wbOutputPill.innerHTML = `<span class="pill__dot"></span>exit ${e.code} · ${stdoutLines} stdout · ${stderrLines} stderr`;
        return;
      }
      if (e.type === "error") {
        endLiveStream();
        appendOutput(e.text, "error");
        wbOutputPill.className = "pill pill--down";
        wbOutputPill.innerHTML = `<span class="pill__dot"></span>error`;
        return;
      }
      appendOutput(e.text, e.type);
      if (e.type === "stdout") stdoutLines++;
      else stderrLines++;
    },
    () => {
      endLiveStream();
      setRunning(false);
      cancelRun = null;
    },
  );
}

function setupFullscreenToggles() {
  const root = document.querySelector<HTMLElement>("#workbench");
  const btn = document.querySelector<HTMLButtonElement>("#wb-fullscreen-btn");
  if (!root || !btn) return;

  const toggle = () => {
    const willOpen = !root.classList.contains("wb--full");
    root.classList.toggle("wb--full", willOpen);
    document.body.classList.toggle("body--full", willOpen);
    setTimeout(() => editor?.requestMeasure(), 0);
  };

  btn.addEventListener("click", toggle);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.classList.contains("wb--full")) {
      root.classList.remove("wb--full");
      document.body.classList.remove("body--full");
      setTimeout(() => editor?.requestMeasure(), 0);
    }
  });
}

export function initWorkbench() {
  ensureEditor("# pick a tutorial from the sidebar to load its source");
  renderProviderPill();
  void (async () => {
    try {
      tutorials = await listTutorials();
      renderList("");
      if (tutorials.length) {
        const first = tutorials.find((t) => t.id === "tutorial_01_basic_agent") ?? tutorials[0];
        await selectTutorial(first.id);
      }
    } catch (err) {
      wbStatus.textContent = `failed to list: ${(err as Error).message}`;
    }
  })();

  search.addEventListener("input", () => renderList(search.value));
  setupFullscreenToggles();
  wbRunBtn.addEventListener("click", () => void runEdited());
  wbStopBtn.addEventListener("click", () => {
    cancelRun?.();
    setRunning(false);
    appendOutput("stopped by user", "error");
  });
  wbResetBtn.addEventListener("click", () => {
    if (current) setEditorContent(current.source);
  });
}

export function refreshWorkbenchProvider() {
  renderProviderPill();
}
