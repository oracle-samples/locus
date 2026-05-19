/** Protocols sidebar + detail view.
 *
 *  Mirrors the Skills tab: a sidebar list of the eight built-in router
 *  protocols, plus a detail panel that shows what each one *compiles
 *  to* at runtime — the inspectable shape that proves the bounded
 *  graph generation claim.
 */
import {
  getProtocol,
  listProtocolCategories,
  listProtocols,
  type CategoryInfo,
  type ProtocolDetail,
  type ProtocolSummary,
} from "../api";
import { $ } from "./dom";

let protocols: ProtocolSummary[] = [];
let categories: CategoryInfo[] = [];
let current: ProtocolDetail | null = null;

function sideProtocols(): HTMLElement {
  return $("#side-protocols");
}
function search(): HTMLInputElement {
  return $<HTMLInputElement>("#protocol-search");
}

export async function bootstrapProtocols(): Promise<void> {
  try {
    [protocols, categories] = await Promise.all([
      listProtocols(),
      listProtocolCategories().catch((err) => {
        console.warn("[wb/protocols] categories load failed", err);
        return [] as CategoryInfo[];
      }),
    ]);
    console.info(
      `[wb/protocols] loaded ${protocols.length} protocols in ${categories.length} categories`,
    );
    renderList("");
  } catch (err) {
    console.error("[wb/protocols] catalog load failed", err);
    sideProtocols().innerHTML = `<div style="color: var(--or-red-deep); font-size:0.8rem; padding: 0.5rem">${(err as Error).message}</div>`;
  }
  search().addEventListener("input", () => renderList(search().value));
}

async function selectProtocol(id: string): Promise<void> {
  console.info("[wb/protocols] select", id);
  try {
    current = await getProtocol(id);
  } catch (err) {
    console.error("[wb/protocols] failed to load", id, err);
    return;
  }
  renderDetail(current);
  renderList(search().value);
  document
    .querySelector<HTMLElement>(`[data-testid="protocol-${current.id}"]`)
    ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderList(filter: string): void {
  const sidebar = sideProtocols();
  sidebar.innerHTML = "";
  const q = filter.trim().toLowerCase();
  const catById: Map<string, CategoryInfo> = new Map(categories.map((c) => [c.id, c]));
  let lastCategory: string | null = null;

  for (const p of protocols) {
    if (q && !`${p.name} ${p.description} ${p.handles.join(" ")}`.toLowerCase().includes(q)) {
      continue;
    }
    const catId = p.category ?? "other";
    if (catId !== lastCategory) {
      const meta = catById.get(catId);
      const header = document.createElement("div");
      header.className = "side__category";
      header.dataset.testid = `protocol-category-${catId}`;
      header.innerHTML = `
        <div class="side__category-name">${meta?.name ?? catId}</div>
        ${meta?.description ? `<div class="side__category-desc">${meta.description}</div>` : ""}
      `;
      sidebar.appendChild(header);
      lastCategory = catId;
    }
    const item = document.createElement("div");
    item.className = `side__item${current?.id === p.id ? " side__item--active" : ""}`;
    item.dataset.testid = `protocol-${p.id}`;
    const costBadge = `<span class="pill pill--down" style="font-size: 0.6rem; padding: 0 0.4rem">${p.cost}</span>`;
    item.innerHTML = `
      <div style="flex: 1; min-width: 0">
        <div style="font-size: 0.82rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">${p.name}</div>
        <div style="font-size: 0.7rem; color: var(--or-text-mute); overflow: hidden; text-overflow: ellipsis; white-space: nowrap">${p.description}</div>
      </div>
      ${costBadge}
    `;
    item.addEventListener("click", () => void selectProtocol(p.id));
    sidebar.appendChild(item);
  }
}

function chipRow(label: string, items: string[], primary: Set<string> = new Set()): string {
  if (!items.length) return "";
  const chips = items
    .map((t) => {
      const cls = primary.has(t) ? "tt-chip tt-chip--primary" : "tt-chip";
      return `<span class="${cls}">${t}</span>`;
    })
    .join("");
  return `<div class="tt-chip-row"><span class="tt-chip-row__label">${label}</span>${chips}</div>`;
}

function renderDetail(p: ProtocolDetail): void {
  $("#protocol-title").textContent = p.name;
  $("#protocol-sub").textContent = p.description;
  $("#crumbs").textContent = `Workbench · Protocol ${p.name}`;

  const cost = $<HTMLElement>("#protocol-cost-pill");
  cost.textContent = `cost: ${p.cost}`;
  cost.style.display = "inline-flex";
  const risk = $<HTMLElement>("#protocol-risk-pill");
  risk.textContent = `risk_max: ${p.risk_max}`;
  risk.style.display = "inline-flex";
  const latency = $<HTMLElement>("#protocol-latency-pill");
  latency.textContent = `latency: ${p.latency}`;
  latency.style.display = "inline-flex";

  $("#protocol-shape").textContent = p.runtime_shape;

  const flags: string[] = [];
  flags.push(p.supports_streaming ? "streams" : "no streaming");
  flags.push(p.supports_repair ? "repair-aware" : "no repair");
  $("#protocol-meta").textContent = `${flags.join(" · ")} · id: ${p.id}`;

  const primarySet = new Set(p.primary_for);
  $("#protocol-handles").innerHTML = chipRow("handles", p.handles, primarySet);
  $("#protocol-primary").innerHTML = chipRow("canonical for", p.primary_for, primarySet);
  $("#protocol-caps").innerHTML = p.requires_capabilities.length
    ? chipRow("requires", p.requires_capabilities)
    : "";
}

/** Wire all four sidebar tabs: Notebooks / Skills / Protocols / Patterns. */
export function installSidebarTabs(): void {
  const tutsTab = $("#side-tab-notebooks");
  const skillsTab = $("#side-tab-skills");
  const protocolsTab = $("#side-tab-protocols");
  const patternsTab = $("#side-tab-patterns");
  const tutsPane = $("#side-pane-notebooks");
  const skillsPane = $("#side-pane-skills");
  const protocolsPane = $("#side-pane-protocols");
  const patternsPane = $("#side-pane-patterns");
  const wbView = $("#workbench");
  const skillsView = $("#skills-view");
  const protocolsView = $("#protocols-view");
  const patternsView = $("#patterns-view");

  let skillsInit = false;
  let protocolsInit = false;
  let patternsInit = false;

  function activate(mode: "notebooks" | "skills" | "protocols" | "patterns"): void {
    const isSkills = mode === "skills";
    const isProtocols = mode === "protocols";
    const isTutorials = mode === "notebooks";
    const isPatterns = mode === "patterns";

    tutsTab.classList.toggle("side__tab--active", isTutorials);
    skillsTab.classList.toggle("side__tab--active", isSkills);
    protocolsTab.classList.toggle("side__tab--active", isProtocols);
    patternsTab.classList.toggle("side__tab--active", isPatterns);
    tutsTab.setAttribute("aria-selected", String(isTutorials));
    skillsTab.setAttribute("aria-selected", String(isSkills));
    protocolsTab.setAttribute("aria-selected", String(isProtocols));
    patternsTab.setAttribute("aria-selected", String(isPatterns));

    tutsPane.style.display = isTutorials ? "" : "none";
    skillsPane.style.display = isSkills ? "" : "none";
    protocolsPane.style.display = isProtocols ? "" : "none";
    patternsPane.style.display = isPatterns ? "" : "none";

    wbView.style.display = isTutorials ? "" : "none";
    skillsView.style.display = isSkills ? "" : "none";
    protocolsView.style.display = isProtocols ? "" : "none";
    patternsView.style.display = isPatterns ? "" : "none";

    if (isSkills && !skillsInit) {
      skillsInit = true;
      void import("./skills").then(({ bootstrapSkills }) => {
        void bootstrapSkills();
      });
    }
    if (isProtocols && !protocolsInit) {
      protocolsInit = true;
      void bootstrapProtocols();
    }
    if (isPatterns && !patternsInit) {
      patternsInit = true;
      void import("./patterns").then(({ bootstrapPatterns }) => {
        void bootstrapPatterns();
      });
    }
  }

  tutsTab.addEventListener("click", () => activate("notebooks"));
  skillsTab.addEventListener("click", () => activate("skills"));
  protocolsTab.addEventListener("click", () => activate("protocols"));
  patternsTab.addEventListener("click", () => activate("patterns"));
}
