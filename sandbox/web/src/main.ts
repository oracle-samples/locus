import { listModels } from "./api";
import { defaultModelFor, defaultsFor, loadProvider, saveProvider } from "./settings";
import type { ProviderConfig, ProviderType } from "./types";
import { initWorkbench, refreshWorkbenchProvider } from "./workbench";

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------

const $ = <T extends HTMLElement = HTMLElement>(sel: string): T => {
  const el = document.querySelector<T>(sel);
  if (!el) throw new Error(`missing: ${sel}`);
  return el;
};

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
const headerMeta = $("#header-meta");
const providerWarning = $("#provider-warning");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let provider: ProviderConfig | null = loadProvider();

headerMeta.textContent = "Multi-Agent Reasoning Orchestrator SDK";

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
      oci_transport: cfgTransport.value as ProviderConfig["oci_transport"],
    };
    const result = await listModels(cfg as ProviderConfig);
    if (seq !== modelsRefreshSeq) return;
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

function syncSettingsRows() {
  const p = cfgProvider.value as ProviderType;
  const isOci = p.startsWith("oci");
  rowApiKey.style.display = isOci ? "none" : "flex";
  rowProfile.style.display = isOci ? "flex" : "none";
  rowRegion.style.display = isOci ? "flex" : "none";
  rowCompartment.style.display = isOci ? "flex" : "none";
  rowTransport.style.display = isOci ? "flex" : "none";
  const def = defaultsFor(p);
  if (!cfgModel.value) setModelOptions([def.model], def.model);
  if (isOci && !cfgProfile.value) cfgProfile.value = def.profile ?? "";
  if (isOci && !cfgRegion.value) cfgRegion.value = def.region ?? "";
  if (isOci && !cfgCompartment.value) cfgCompartment.value = def.compartment_id ?? "";
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
  providerWarning.style.display = "none";
  refreshWorkbenchProvider();
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

settingsBtn.addEventListener("click", openSettings);
settingsClose.addEventListener("click", closeSettings);
settingsCancel.addEventListener("click", closeSettings);
settingsSave.addEventListener("click", saveSettings);
cfgProvider.addEventListener("change", () => {
  const p = cfgProvider.value as ProviderType;
  setModelOptions([defaultModelFor(p)], defaultModelFor(p));
  syncSettingsRows();
  void refreshModels();
});
let refreshTimer: ReturnType<typeof setTimeout> | null = null;
const queueRefresh = () => {
  if (refreshTimer) clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => void refreshModels(), 400);
};
cfgProfile.addEventListener("input", queueRefresh);
cfgRegion.addEventListener("input", queueRefresh);
cfgCompartment.addEventListener("input", queueRefresh);
cfgApiKey.addEventListener("input", queueRefresh);
cfgTransport.addEventListener("change", queueRefresh);

// --- Theme toggle (light / dark) ---
const themeBtn = $<HTMLButtonElement>("#theme-btn");
const themeSun = $<HTMLElement>("#theme-icon-sun");
const themeMoon = $<HTMLElement>("#theme-icon-moon");
const THEME_KEY = "locus.sandbox.theme";

function applyTheme(t: "light" | "dark") {
  document.documentElement.setAttribute("data-theme", t);
  themeSun.style.display = t === "dark" ? "none" : "block";
  themeMoon.style.display = t === "dark" ? "block" : "none";
}

const savedTheme = localStorage.getItem(THEME_KEY) as "light" | "dark" | null;
const initialTheme: "light" | "dark" =
  savedTheme ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
applyTheme(initialTheme);
themeBtn.addEventListener("click", () => {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
});

// Workbench is the only mode now.
if (!provider) providerWarning.style.display = "block";
initWorkbench();
