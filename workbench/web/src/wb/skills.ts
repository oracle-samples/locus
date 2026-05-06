/** Skills sidebar + detail view.
 *
 *  The sidebar has two tabs: Tutorials (the existing workbench) and
 *  Skills (this module). Toggling activates the relevant pane in the
 *  sidebar and swaps the main view. There is no URL routing — the
 *  workbench is single-page on purpose.
 */
import { getSkill, listSkills, type SkillDetail, type SkillSummary } from "../api";
import { $ } from "./dom";

let skills: SkillSummary[] = [];
let current: SkillDetail | null = null;

function sideSkills(): HTMLElement {
  return $("#side-skills");
}
function search(): HTMLInputElement {
  return $<HTMLInputElement>("#skill-search");
}

export async function bootstrapSkills(): Promise<void> {
  try {
    skills = await listSkills();
    console.info(`[wb/skills] loaded ${skills.length} skills`);
    renderList("");
  } catch (err) {
    console.error("[wb/skills] catalog load failed", err);
    sideSkills().innerHTML = `<div style="color: var(--or-red-deep); font-size:0.8rem; padding: 0.5rem">${(err as Error).message}</div>`;
  }
  search().addEventListener("input", () => renderList(search().value));
}

async function selectSkill(id: string): Promise<void> {
  console.info("[wb/skills] select", id);
  try {
    current = await getSkill(id);
  } catch (err) {
    console.error("[wb/skills] failed to load", id, err);
    return;
  }
  renderDetail(current);
  renderList(search().value);
  document
    .querySelector<HTMLElement>(`[data-testid="skill-${current.id}"]`)
    ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderList(filter: string): void {
  sideSkills().innerHTML = "";
  const q = filter.trim().toLowerCase();
  for (const sk of skills) {
    if (q && !`${sk.name} ${sk.description} ${sk.domain}`.toLowerCase().includes(q)) {
      continue;
    }
    const item = document.createElement("div");
    item.className = `side__item${current?.id === sk.id ? " side__item--active" : ""}`;
    item.dataset.testid = `skill-${sk.id}`;
    const domainBadge = sk.domain
      ? `<span class="pill pill--down" style="font-size: 0.6rem; padding: 0 0.4rem">${sk.domain}</span>`
      : "";
    item.innerHTML = `
      <div style="flex: 1; min-width: 0">
        <div style="font-size: 0.82rem; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">${sk.name}</div>
        <div style="font-size: 0.7rem; color: var(--or-text-mute); overflow: hidden; text-overflow: ellipsis; white-space: nowrap">${sk.description}</div>
      </div>
      ${domainBadge}
    `;
    item.addEventListener("click", () => void selectSkill(sk.id));
    sideSkills().appendChild(item);
  }
}

function renderDetail(skill: SkillDetail): void {
  $("#skill-title").textContent = skill.name;
  $("#skill-sub").textContent = skill.description;
  $("#crumbs").textContent = `Workbench · Skill ${skill.name}`;

  const domainPill = $<HTMLElement>("#skill-domain-pill");
  if (skill.domain) {
    domainPill.textContent = `domain: ${skill.domain}`;
    domainPill.style.display = "inline-flex";
  } else {
    domainPill.style.display = "none";
  }

  const licensePill = $<HTMLElement>("#skill-license-pill");
  if (skill.license) {
    licensePill.textContent = skill.license;
    licensePill.style.display = "inline-flex";
  } else {
    licensePill.style.display = "none";
  }

  const meta = $("#skill-meta");
  const tools = skill.allowed_tools.length
    ? `allowed tools: ${skill.allowed_tools.map((t) => `<code>${t}</code>`).join(", ")}`
    : "allowed tools: <em>(none)</em>";
  meta.innerHTML = `${tools} · path: <code>${skill.path}</code>`;

  $("#skill-instructions").textContent = skill.instructions;

  const resources = $("#skill-resources");
  if (skill.resources.length) {
    const items = skill.resources.map((r) => `<li>${r}</li>`).join("");
    resources.innerHTML = `<strong>Resources</strong><ul>${items}</ul>`;
    resources.style.display = "block";
  } else {
    resources.style.display = "none";
  }
}

// `installSidebarTabs` now lives in ./protocols.ts so it can wire all
// three sidebar tabs (Tutorials / Skills / Protocols) in one place.
