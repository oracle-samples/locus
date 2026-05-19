/** Tutorial sidebar: catalog fetch, filter, render, prev/next nav. */
import {
  getTutorial,
  listTutorialCategories,
  listTutorials,
  type CategoryInfo,
  type Tutorial,
  type TutorialDetail,
} from "../api";
import { $ } from "./dom";
import { setEditorContent } from "./editor";
import { showEmptyState } from "./output";

let tutorials: Tutorial[] = [];
let categories: CategoryInfo[] = [];
let current: TutorialDetail | null = null;

export function getCurrent(): TutorialDetail | null {
  return current;
}

export function getTutorials(): Tutorial[] {
  return tutorials;
}

function sideTutorials(): HTMLElement {
  return $("#side-tutorials");
}
function search(): HTMLInputElement {
  return $<HTMLInputElement>("#tutorial-search");
}

export async function bootstrapTutorials(): Promise<void> {
  try {
    // Categories load is best-effort — if it fails the sidebar still
    // renders, just without section headers.
    [tutorials, categories] = await Promise.all([
      listTutorials(),
      listTutorialCategories().catch((err) => {
        console.warn("[wb/tutorials] categories load failed", err);
        return [] as CategoryInfo[];
      }),
    ]);
    console.info(
      `[wb/tutorials] loaded ${tutorials.length} tutorials in ${categories.length} categories`,
    );
    renderList("");
    if (tutorials.length) {
      const first = tutorials.find((t) => t.id === "tutorial_01_basic_agent") ?? tutorials[0];
      await selectTutorial(first.id);
    }
  } catch (err) {
    console.error("[wb/tutorials] catalog load failed", err);
    sideTutorials().innerHTML = `<div style="color: var(--or-red-deep); font-size:0.8rem; padding: 0.5rem">${(err as Error).message}</div>`;
  }
  search().addEventListener("input", () => renderList(search().value));
  installNavButtons();
}

export async function selectTutorial(id: string): Promise<void> {
  console.info("[wb/tutorials] select", id);
  try {
    current = await getTutorial(id);
  } catch (err) {
    console.error("[wb/tutorials] failed to load", id, err);
    return;
  }
  $("#wb-title").textContent = current.title;
  $("#wb-sub").textContent = current.summary || current.filename;
  setEditorContent(current.source);
  showEmptyState();
  $("#wb-output-pill").style.display = "none";
  $("#wb-status").textContent = `loaded ${current.filename}`;
  $("#crumbs").textContent = `Workbench · Notebook ${current.number}`;
  renderList(search().value);
  renderNavState();
  document
    .querySelector<HTMLElement>(`[data-testid="tutorial-${current.id}"]`)
    ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderList(filter: string): void {
  const sidebar = sideTutorials();
  sidebar.innerHTML = "";
  const q = filter.trim().toLowerCase();

  // Index categories by id for quick lookup; tutorials are pre-sorted
  // by the backend (category position, then category_order, then number)
  // so a single pass with a "previous category" sentinel produces
  // correctly ordered section headers.
  const catById: Map<string, CategoryInfo> = new Map(categories.map((c) => [c.id, c]));
  let lastCategory: string | null = null;

  for (const t of tutorials) {
    if (q && !`${t.number} ${t.title} ${t.id}`.toLowerCase().includes(q)) continue;

    const catId = t.category ?? "misc";
    if (catId !== lastCategory) {
      const meta = catById.get(catId);
      const header = document.createElement("div");
      header.className = "side__category";
      header.dataset.testid = `tutorial-category-${catId}`;
      header.innerHTML = `
        <div class="side__category-name">${meta?.name ?? catId}</div>
        ${meta?.description ? `<div class="side__category-desc">${meta.description}</div>` : ""}
      `;
      sidebar.appendChild(header);
      lastCategory = catId;
    }

    const item = document.createElement("div");
    item.className = `side__item${current?.id === t.id ? " side__item--active" : ""}`;
    item.dataset.testid = `tutorial-${t.id}`;
    const stdinBadge = t.needs_stdin
      ? `<span class="needs-stdin-badge" title="uses interrupt() — pops a modal for human input" data-testid="needs-stdin-badge">↩</span>`
      : "";
    item.innerHTML = `
      <span style="font-family: var(--mono); font-size: 0.7rem; color: var(--or-text-mute); min-width: 1.6rem">${String(t.number).padStart(2, "0")}</span>
      <span style="font-size: 0.82rem; flex: 1">${t.title.replace(/^Tutorial \d+:\s*/i, "")}</span>
      ${stdinBadge}
    `;
    item.addEventListener("click", () => void selectTutorial(t.id));
    sidebar.appendChild(item);
  }
}

function installNavButtons(): void {
  const prev = $<HTMLButtonElement>("#wb-prev-btn");
  const next = $<HTMLButtonElement>("#wb-next-btn");
  const step = (delta: number) => {
    if (!current) return;
    const cid = current.id;
    const idx = tutorials.findIndex((t) => t.id === cid);
    const target = tutorials[idx + delta];
    if (target) void selectTutorial(target.id);
  };
  prev.addEventListener("click", () => step(-1));
  next.addEventListener("click", () => step(+1));
}

export function renderNavState(): void {
  const prev = $<HTMLButtonElement>("#wb-prev-btn");
  const next = $<HTMLButtonElement>("#wb-next-btn");
  const cur = current;
  const idx = cur ? tutorials.findIndex((t) => t.id === cur.id) : -1;
  prev.disabled = idx <= 0;
  next.disabled = idx === -1 || idx >= tutorials.length - 1;
}
