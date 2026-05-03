import { listModels, listPatterns, runPattern, streamPattern } from "./api";
import { defaultModelFor, defaultsFor, describeProvider, loadProvider, saveProvider } from "./settings";
import type { Pattern, ProviderConfig, ProviderType, RunEvent } from "./types";
import { initWorkbench, refreshWorkbenchProvider } from "./workbench";

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = <T extends HTMLElement = HTMLElement>(sel: string): T => {
  const el = document.querySelector<T>(sel);
  if (!el) throw new Error(`missing: ${sel}`);
  return el;
};

const sidePatterns = $("#side-patterns");
const playground = $("#playground");
const providerWarning = $("#provider-warning");
const providerPill = $("#provider-pill");
const settingsBtn = $<HTMLButtonElement>("#settings-btn");
const settingsModal = $("#settings-modal");
const settingsClose = $<HTMLButtonElement>("#settings-close");
const settingsCancel = $<HTMLButtonElement>("#settings-cancel");
const settingsSave = $<HTMLButtonElement>("#settings-save");
const cfgProvider = $<HTMLSelectElement>("#cfg-provider");
const cfgApiKey = $<HTMLInputElement>("#cfg-apikey");
const cfgModel = $<HTMLSelectElement>("#cfg-model");
const cfgModelStatus = $("#cfg-model-status");
const cfgProfile = $<HTMLInputElement>("#cfg-profile");
const cfgRegion = $<HTMLInputElement>("#cfg-region");
const cfgCompartment = $<HTMLInputElement>("#cfg-compartment");
const cfgTransport = $<HTMLSelectElement>("#cfg-transport");
const rowApiKey = $("#row-apikey");
const rowProfile = $("#row-profile");
const rowRegion = $("#row-region");
const rowCompartment = $("#row-compartment");
const rowTransport = $("#row-transport");
const promptArea = $<HTMLTextAreaElement>("#prompt");
const sendBtn = $<HTMLButtonElement>("#send-btn");
const clearBtn = $<HTMLButtonElement>("#clear-btn");
const streamToggle = $<HTMLInputElement>("#stream-toggle");
const streamToggleRow = $("#stream-toggle-row");
const responseEl = $("#response");
const responsePill = $("#response-pill");
const patternTitle = $("#pattern-title");
const patternSub = $("#pattern-sub");
const pageTitle = $("#page-title");
const pageLede = $("#page-lede");
const crumbs = $("#crumbs");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let patterns: Pattern[] = [];
let selected: Pattern | null = null;
let provider: ProviderConfig | null = loadProvider();

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function renderProviderPill() {
  if (provider) {
    providerPill.className = "pill pill--up";
    providerPill.innerHTML = `<span class="pill__dot"></span>${describeProvider(provider)}`;
    providerPill.style.display = "inline-flex";
    providerWarning.style.display = "none";
    if (selected) playground.style.display = "block";
  } else {
    providerPill.style.display = "none";
    providerWarning.style.display = "block";
    playground.style.display = "none";
  }
}

function renderPatterns() {
  sidePatterns.innerHTML = "";
  patterns.forEach((p) => {
    const item = document.createElement("div");
    item.className = `side__item${selected?.id === p.id ? " side__item--active" : ""}`;
    item.dataset.testid = `pattern-${p.id}`;
    item.innerHTML = `
      <span class="side__dot ${provider ? "side__dot--up" : ""}"></span>
      <span style="font-size: 0.85rem">${p.title}</span>
    `;
    item.addEventListener("click", () => selectPattern(p));
    sidePatterns.appendChild(item);
  });
}

function selectPattern(p: Pattern) {
  selected = p;
  pageTitle.textContent = p.title;
  pageLede.textContent = p.summary;
  crumbs.textContent = `Sandbox · Tutorial ${p.tutorial}`;
  patternTitle.textContent = p.title;
  patternSub.textContent = p.summary;
  promptArea.value = defaultPromptFor(p.id);
  responseEl.innerHTML = `<div class="reply__empty">Hit <strong>Run</strong> to send the prompt to the agent.</div>`;
  responsePill.style.display = "none";
  // Show streaming toggle only for stream-capable patterns. Default it
  // to ON for streamable patterns so the user gets token-level streaming
  // out of the box without remembering to flip a checkbox.
  streamToggleRow.style.display = p.streamable ? "flex" : "none";
  streamToggle.checked = p.streamable;
  renderPatterns();
  renderProviderPill();
}

function defaultPromptFor(id: string): string {
  switch (id) {
    case "agent":
      return "Explain quantum entanglement in two sentences for a high schooler.";
    case "agent_with_tools":
      return "What is 17 + 25? Also reverse the word 'locus'.";
    case "composition":
      return "Renewable energy in 2026.";
    case "orchestrator":
      return "Write a one-paragraph case for AI in healthcare, then have the editor tighten it.";
    case "stategraph_loop":
      return "Explain the difference between SQL and NoSQL in one paragraph.";
    case "map_reduce":
      return "Review this code: def fetch(u): return requests.get(u).text";
    case "structured_output":
      return "Pick a winner: Python vs JavaScript for backend in 2026. Decide.";
    default:
      return "";
  }
}

// ---------------------------------------------------------------------------
// Settings modal
// ---------------------------------------------------------------------------

function fillFromConfig(cfg: ProviderConfig) {
  cfgProvider.value = cfg.provider;
  cfgApiKey.value = cfg.api_key ?? "";
  cfgProfile.value = cfg.profile ?? "";
  cfgRegion.value = cfg.region ?? "us-chicago-1";
  cfgCompartment.value = cfg.compartment_id ?? "";
  cfgTransport.value = cfg.oci_transport ?? "auto";
  // Seed the model select with a single placeholder option containing the
  // requested default — the real list lands when refreshModels resolves.
  const want = cfg.model ?? defaultModelFor(cfg.provider);
  setModelOptions([want], want);
}

function setModelOptions(models: string[], selected?: string) {
  cfgModel.innerHTML = "";
  if (selected && !models.includes(selected)) models = [selected, ...models];
  for (const m of models) {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    cfgModel.appendChild(opt);
  }
  if (selected) cfgModel.value = selected;
}

let modelsRefreshSeq = 0;

async function refreshModels() {
  const seq = ++modelsRefreshSeq;
  const p = cfgProvider.value as ProviderType;
  cfgModelStatus.textContent = "fetching…";
  try {
    const cfg = {
      provider: p,
      model: cfgModel.value,
      api_key: cfgApiKey.value || undefined,
      profile: cfgProfile.value || undefined,
      region: cfgRegion.value || undefined,
      compartment_id: cfgCompartment.value || undefined,
    };
    const result = await listModels(cfg as ProviderConfig);
    if (seq !== modelsRefreshSeq) return; // stale
    if (result.error) {
      cfgModelStatus.textContent = result.error;
      return;
    }
    cfgModelStatus.textContent = `${result.models.length} available`;
    const want = cfgModel.value || defaultModelFor(p);
    setModelOptions(result.models, want);
  } catch (err) {
    if (seq !== modelsRefreshSeq) return;
    cfgModelStatus.textContent = `error: ${(err as Error).message}`;
  }
}

function openSettings() {
  fillFromConfig(provider ?? defaultsFor("oci-session"));
  syncSettingsRows();
  settingsModal.classList.add("modal--open");
  void refreshModels();
}

function closeSettings() {
  settingsModal.classList.remove("modal--open");
}

function syncSettingsRows() {
  const p = cfgProvider.value as ProviderType;
  const isOci = p.startsWith("oci");
  rowApiKey.style.display = isOci ? "none" : "flex";
  rowProfile.style.display = isOci ? "flex" : "none";
  rowRegion.style.display = isOci ? "flex" : "none";
  rowCompartment.style.display = isOci ? "flex" : "none";
  rowTransport.style.display = isOci ? "flex" : "none";
  // When switching provider type, refill empty OCI / model fields so the
  // user doesn't have to retype defaults that always make sense (e.g.
  // BOAT-OC1 + observai compartment + us-chicago-1).
  const def = defaultsFor(p);
  if (!cfgModel.value) setModelOptions([def.model], def.model);
  if (isOci && !cfgProfile.value) cfgProfile.value = def.profile ?? "";
  if (isOci && !cfgRegion.value) cfgRegion.value = def.region ?? "";
  if (isOci && !cfgCompartment.value) cfgCompartment.value = def.compartment_id ?? "";
}

function saveSettings() {
  const p = cfgProvider.value as ProviderType;
  const cfg: ProviderConfig = {
    provider: p,
    model: cfgModel.value || defaultModelFor(p),
  };
  if (p === "openai" || p === "anthropic") {
    cfg.api_key = cfgApiKey.value.trim();
    if (!cfg.api_key) {
      alert(`${p} provider needs an API key.`);
      return;
    }
  } else {
    cfg.profile = cfgProfile.value.trim() || "DEFAULT";
    cfg.region = cfgRegion.value.trim() || "us-chicago-1";
    cfg.compartment_id = cfgCompartment.value.trim();
    cfg.oci_transport = (cfgTransport.value as ProviderConfig["oci_transport"]) ?? "auto";
  }
  provider = cfg;
  saveProvider(cfg);
  closeSettings();
  renderProviderPill();
  renderPatterns();
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

async function runSelected() {
  if (!selected || !provider) return;
  responseEl.innerHTML = "";
  responsePill.style.display = "inline-flex";
  responsePill.className = "pill pill--busy";
  responsePill.innerHTML = `<span class="pill__dot"></span>running…`;
  sendBtn.disabled = true;
  sendBtn.textContent = "Running…";

  const useStream = selected.streamable && streamToggle.checked;

  if (useStream) {
    let count = 0;
    let liveEl: HTMLDivElement | null = null;
    const startLive = () => {
      if (liveEl) return liveEl;
      liveEl = document.createElement("div");
      liveEl.className = "reply__live";
      liveEl.dataset.testid = "live-transcript";
      responseEl.appendChild(liveEl);
      return liveEl;
    };
    await streamPattern(
      selected.id,
      promptArea.value,
      provider,
      (e: RunEvent) => {
        count++;
        responsePill.className = "pill pill--busy";
        responsePill.innerHTML = `<span class="pill__dot"></span>${count} events`;
        // Token-level chunks: append text to the live transcript instead of
        // dropping a new event card per word.
        if (e.kind === "ModelChunkEvent") {
          const node = startLive();
          const piece = (e.extra?.content as string | undefined) ?? "";
          if (piece) node.textContent = (node.textContent ?? "") + piece;
          return;
        }
        appendEvent(e);
      },
      (final) => {
        responsePill.className = "pill pill--up";
        responsePill.innerHTML = `<span class="pill__dot"></span>${count} events · done`;
        // Either we got a Terminate.final_message, or fall back to the live
        // transcript text we accumulated from chunks.
        const fallback = liveEl?.textContent?.trim() ?? "";
        if (final) appendFinal(final);
        else if (fallback) appendFinal(fallback);
        sendBtn.disabled = false;
        sendBtn.textContent = "Run";
      },
      (msg) => {
        responsePill.className = "pill pill--down";
        responsePill.innerHTML = `<span class="pill__dot"></span>error`;
        appendError(msg);
        sendBtn.disabled = false;
        sendBtn.textContent = "Run";
      },
    );
    return;
  }

  try {
    const result = await runPattern(selected.id, promptArea.value, provider);
    responsePill.className = "pill pill--up";
    const tag = result.model ? ` · via ${result.model}` : "";
    responsePill.innerHTML = `<span class="pill__dot"></span>${result.events.length} events${tag}`;
    result.events.forEach((e: RunEvent) => appendEvent(e));
    if (result.reply) appendFinal(result.reply);
  } catch (err) {
    responsePill.className = "pill pill--down";
    responsePill.innerHTML = `<span class="pill__dot"></span>error`;
    appendError((err as Error).message);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Run";
  }
}

function appendEvent(e: RunEvent) {
  const node = document.createElement("div");
  node.className = "event";
  node.dataset.testid = "event";
  const css =
    e.kind === "TerminateEvent"
      ? "event__kind--terminate"
      : e.kind.startsWith("Tool")
        ? "event__kind--tool"
        : "";
  node.innerHTML = `
    <span class="event__kind ${css}">${e.kind.replace("Event", "")}</span>
    <span class="event__body"></span>
  `;
  (node.querySelector(".event__body") as HTMLElement).textContent = e.text;
  responseEl.appendChild(node);
}

function appendFinal(text: string) {
  const node = document.createElement("div");
  node.className = "reply__final";
  node.dataset.testid = "final-reply";
  node.textContent = text;
  responseEl.appendChild(node);
}

function appendError(msg: string) {
  const node = document.createElement("div");
  node.className = "event";
  node.dataset.testid = "error";
  node.innerHTML = `<span class="event__kind event__kind--error">Error</span><span class="event__body"></span>`;
  (node.querySelector(".event__body") as HTMLElement).textContent = msg;
  responseEl.appendChild(node);
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

settingsBtn.addEventListener("click", openSettings);
settingsClose.addEventListener("click", closeSettings);
settingsCancel.addEventListener("click", closeSettings);
settingsSave.addEventListener("click", saveSettings);
cfgProvider.addEventListener("change", () => {
  // Reset the model select to that provider's default so we don't
  // accidentally send "openai.gpt-5.5" to the OpenAI provider just because
  // it was the previous OCI selection.
  const p = cfgProvider.value as ProviderType;
  setModelOptions([defaultModelFor(p)], defaultModelFor(p));
  syncSettingsRows();
  void refreshModels();
});
// Refresh the model list when the OCI connection details change so the
// dropdown reflects what's actually available in that profile/region/compartment.
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
const queueRefresh = () => {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => void refreshModels(), 400);
};
cfgProfile.addEventListener("input", queueRefresh);
cfgRegion.addEventListener("input", queueRefresh);
cfgCompartment.addEventListener("input", queueRefresh);
cfgApiKey.addEventListener("input", queueRefresh);
sendBtn.addEventListener("click", runSelected);
clearBtn.addEventListener("click", () => {
  responseEl.innerHTML = "";
  responsePill.style.display = "none";
});

void (async () => {
  try {
    patterns = await listPatterns();
    renderPatterns();
    if (patterns.length) selectPattern(patterns[0]);
  } catch (err) {
    sidePatterns.innerHTML = `<div style="color: var(--or-red-deep); font-size:0.8rem; padding: 0.5rem">${(err as Error).message}</div>`;
  }
  renderProviderPill();
})();

// Mode switch — Patterns vs Workbench. Workbench is initialised lazily so
// CodeMirror only loads when the user actually opens it.
const modePatterns = $<HTMLButtonElement>("#mode-patterns");
const modeWorkbench = $<HTMLButtonElement>("#mode-workbench");
const sidePatternsSection = $("#side-patterns-section");
const sideTutorialsSection = $("#side-tutorials-section");
const playgroundEl = $("#playground");
const workbenchEl = $("#workbench");
const providerWarningEl = $("#provider-warning");
let workbenchReady = false;

function setMode(mode: "patterns" | "workbench") {
  const isWb = mode === "workbench";
  modePatterns.classList.toggle("mode__btn--active", !isWb);
  modeWorkbench.classList.toggle("mode__btn--active", isWb);
  sidePatternsSection.style.display = isWb ? "none" : "block";
  sideTutorialsSection.style.display = isWb ? "block" : "none";
  if (isWb) {
    playgroundEl.style.display = "none";
    providerWarningEl.style.display = "none";
    workbenchEl.style.display = "block";
    pageTitle.textContent = "Workbench";
    pageLede.textContent = "Pick a tutorial, edit the source, run it as a Python subprocess against your configured provider.";
    crumbs.textContent = "Sandbox · Workbench";
    if (!workbenchReady) {
      initWorkbench();
      workbenchReady = true;
    } else {
      refreshWorkbenchProvider();
    }
  } else {
    workbenchEl.style.display = "none";
    if (selected) {
      playgroundEl.style.display = "block";
    }
    if (!provider) providerWarningEl.style.display = "block";
    pageTitle.textContent = selected?.title ?? "Pick a pattern";
    pageLede.textContent = selected?.summary ?? "";
    crumbs.textContent = selected ? `Sandbox · Tutorial ${selected.tutorial}` : "Sandbox";
  }
}

modePatterns.addEventListener("click", () => setMode("patterns"));
modeWorkbench.addEventListener("click", () => setMode("workbench"));
