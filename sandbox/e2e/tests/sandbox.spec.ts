import { test, expect, type Page } from "@playwright/test";

const COMPARTMENT =
  process.env.OCI_COMPARTMENT ??
  "ocid1.compartment.oc1..aaaaaaaandceai675euuovyyazlymnglde2xknsq35rni43zzmwdhxxu4v7q";
const PROFILE = process.env.OCI_PROFILE ?? "BOAT-OC1";
const REGION = process.env.OCI_REGION ?? "us-chicago-1";

const OPENAI_KEY = process.env.OPENAI_API_KEY;
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

async function configureOCI(page: Page) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByTestId("settings-btn").click();
  await page.getByTestId("cfg-provider").selectOption("oci-session");
  await page.getByTestId("cfg-profile").fill(PROFILE);
  await page.getByTestId("cfg-region").fill(REGION);
  await page.getByTestId("cfg-compartment").fill(COMPARTMENT);
  // Wait for the model dropdown to populate from /api/models, then pick 5.5.
  await expect(async () => {
    const models = await page.getByTestId("cfg-model").locator("option").allTextContents();
    expect(models.some((m) => m.includes("openai.gpt-5.5"))).toBe(true);
  }).toPass({ timeout: 30_000 });
  await page.getByTestId("cfg-model").selectOption("openai.gpt-5.5");
  await page.getByTestId("settings-save").click();
}

async function configureOpenAI(page: Page) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByTestId("settings-btn").click();
  await page.getByTestId("cfg-provider").selectOption("openai");
  await page.getByTestId("cfg-apikey").fill(OPENAI_KEY ?? "");
  // Wait for the OpenAI model list to populate, then pick gpt-5.
  await expect(async () => {
    const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
    expect(opts.includes("gpt-5")).toBe(true);
  }).toPass({ timeout: 10_000 });
  await page.getByTestId("cfg-model").selectOption("gpt-5");
  await page.getByTestId("settings-save").click();
}

async function configureAnthropic(page: Page) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByTestId("settings-btn").click();
  await page.getByTestId("cfg-provider").selectOption("anthropic");
  await page.getByTestId("cfg-apikey").fill(ANTHROPIC_KEY ?? "");
  await expect(async () => {
    const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
    expect(opts.includes("claude-sonnet-4-6")).toBe(true);
  }).toPass({ timeout: 10_000 });
  await page.getByTestId("cfg-model").selectOption("claude-sonnet-4-6");
  await page.getByTestId("settings-save").click();
}

test.describe("locus sandbox · UI smoke", () => {
  test("loads pattern catalog from BFF", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".app__brand-mark")).toHaveText("locus");
    const items = page.locator("[data-testid^='pattern-']");
    await expect(items).toHaveCount(7);
  });

  test("provider settings round-trip via localStorage", async ({ page }) => {
    await configureOCI(page);
    await expect(page.locator("#provider-pill")).toContainText(PROFILE);
    await page.reload();
    await expect(page.locator("#provider-pill")).toContainText(PROFILE);
  });

  test("settings modal pre-fills + lists models for the selected connection", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByTestId("settings-btn").click();
    await expect(page.getByTestId("cfg-provider")).toHaveValue("oci-session");
    await expect(page.getByTestId("cfg-profile")).toHaveValue(PROFILE);
    await expect(page.getByTestId("cfg-compartment")).toHaveValue(COMPARTMENT);
    // Models populate from /api/models against the live OCI list — should
    // include both gpt-5 and gpt-5.5 families.
    await expect(async () => {
      const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
      expect(opts.length).toBeGreaterThan(20);
      expect(opts.some((m) => m.startsWith("openai.gpt-5.5"))).toBe(true);
    }).toPass({ timeout: 30_000 });
  });
});

test.describe("locus sandbox · OCI gpt-5.5", () => {
  test("runs agent + emits real ModelChunkEvent token stream", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOCI(page);
    await page.getByTestId("pattern-agent").click();
    await page.getByTestId("stream-toggle").check();
    await page.getByTestId("prompt").fill("Count from one to five, one per line.");
    await page.getByTestId("send-btn").click();
    // Live transcript element appears as ModelChunk arrives.
    const live = page.getByTestId("live-transcript");
    await expect(live).toBeVisible({ timeout: 60_000 });
    await expect(live).toContainText(/one/i, { timeout: 60_000 });
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 90_000 });
  });

  test("composition (sequential) runs end-to-end", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOCI(page);
    await page.getByTestId("pattern-composition").click();
    await page.getByTestId("prompt").fill("Renewable energy in 2026.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
    expect((await page.getByTestId("final-reply").textContent())?.length ?? 0).toBeGreaterThan(20);
  });

  test("agent_with_tools renders ToolStart events", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOCI(page);
    await page.getByTestId("pattern-agent_with_tools").click();
    await page.getByTestId("prompt").fill("17 + 25 = ? Reverse 'locus'.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
    const kinds = await page.getByTestId("event").locator(".event__kind").allTextContents();
    expect(kinds.some((k) => k.startsWith("Tool"))).toBe(true);
  });
});

const openaiTest = OPENAI_KEY ? test : test.skip;
test.describe("locus sandbox · OpenAI", () => {
  openaiTest("runs basic agent against OpenAI", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOpenAI(page);
    await page.getByTestId("pattern-agent").click();
    await page.getByTestId("prompt").fill("Reply with the word pong.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
  });
});

test.describe("locus sandbox · OCI transports", () => {
  test("SDK transport works with cohere.command-r-plus", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByTestId("settings-btn").click();
    await page.getByTestId("cfg-provider").selectOption("oci-session");
    await page.getByTestId("cfg-profile").fill(PROFILE);
    await page.getByTestId("cfg-region").fill(REGION);
    await page.getByTestId("cfg-compartment").fill(COMPARTMENT);
    await page.getByTestId("cfg-transport").selectOption("sdk");
    // Wait for live model list, then pick the cohere R-plus.
    await expect(async () => {
      const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
      expect(opts.some((m) => m.startsWith("cohere.command-r-plus"))).toBe(true);
    }).toPass({ timeout: 30_000 });
    await page.getByTestId("cfg-model").selectOption("cohere.command-r-plus-08-2024");
    await page.getByTestId("settings-save").click();
    // Pill must reflect both the model and the explicit transport.
    await expect(page.locator("#provider-pill")).toContainText("cohere.command-r-plus-08-2024");
    await expect(page.locator("#provider-pill")).toContainText("sdk");
    await page.getByTestId("pattern-agent").click();
    await page.getByTestId("prompt").fill("Reply only with: pong.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 90_000 });
  });
});

test.describe("locus sandbox · Workbench", () => {
  test("workbench loads tutorials and runs edited source against OCI", async ({ page }) => {
    test.setTimeout(240_000);
    await configureOCI(page);
    await page.getByTestId("mode-workbench").click();
    // Sidebar populated.
    await expect(page.getByTestId("side-tutorials").locator(".side__item").first()).toBeVisible({
      timeout: 30_000,
    });
    const items = page.getByTestId("side-tutorials").locator(".side__item");
    expect(await items.count()).toBeGreaterThan(20);
    // Wait for the workbench to finish auto-loading tutorial 01 — the
    // testing hook is set after each setEditorContent call, so polling
    // for window.__wb tells us the editor's stable to write to.
    await expect.poll(async () => page.evaluate(() => Boolean((window as any).__wb)), { timeout: 10_000 }).toBe(true);
    // Wait until the editor doc isn't empty (auto-load completed).
    await expect.poll(
      async () => page.evaluate(() => ((window as any).__wb?.getSource?.() ?? "").length),
      { timeout: 15_000 },
    ).toBeGreaterThan(100);
    await page.evaluate(() => {
      const wb = (window as any).__wb as { setSource: (s: string) => void };
      // Replace the tutorial source with a one-liner so we don't have to
      // wait for the full tutorial to drive several real OCI calls.
      wb.setSource("print('locus-workbench-marker-7421')\n");
    });
    await page.getByTestId("wb-run-btn").click();
    // Output panel must contain our marker → proves edited source actually ran.
    await expect(page.getByTestId("wb-output")).toContainText("locus-workbench-marker-7421", {
      timeout: 60_000,
    });
    await expect(page.getByTestId("wb-output")).toContainText(/exited with code 0/i, { timeout: 60_000 });
  });
});

const anthropicTest = ANTHROPIC_KEY ? test : test.skip;
test.describe("locus sandbox · Anthropic", () => {
  anthropicTest("runs basic agent against Anthropic", async ({ page }) => {
    test.setTimeout(180_000);
    await configureAnthropic(page);
    await page.getByTestId("pattern-agent").click();
    await page.getByTestId("prompt").fill("Reply with the word pong.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
  });
});
