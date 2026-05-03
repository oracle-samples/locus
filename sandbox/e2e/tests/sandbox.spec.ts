import { test, expect, type Page } from "@playwright/test";

const COMPARTMENT =
  process.env.OCI_COMPARTMENT ??
  "ocid1.compartment.oc1..aaaaaaaandceai675euuovyyazlymnglde2xknsq35rni43zzmwdhxxu4v7q";
const PROFILE = process.env.OCI_PROFILE ?? "BOAT-OC1";
const REGION = process.env.OCI_REGION ?? "us-chicago-1";

const OPENAI_KEY = process.env.OPENAI_API_KEY;
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY;

async function configureOCI(page: Page, opts: { transport?: "auto" | "v1" | "sdk"; model?: string } = {}) {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.getByTestId("settings-btn").click();
  await page.getByTestId("cfg-provider").selectOption("oci-session");
  await page.getByTestId("cfg-profile").fill(PROFILE);
  await page.getByTestId("cfg-region").fill(REGION);
  await page.getByTestId("cfg-compartment").fill(COMPARTMENT);
  if (opts.transport) await page.getByTestId("cfg-transport").selectOption(opts.transport);
  const model = opts.model ?? "openai.gpt-5.5";
  await expect(async () => {
    const m = await page.getByTestId("cfg-model").locator("option").allTextContents();
    expect(m.includes(model)).toBe(true);
  }).toPass({ timeout: 30_000 });
  await page.getByTestId("cfg-model").selectOption(model);
  await page.getByTestId("settings-save").click();
}

test.describe("locus sandbox · workbench", () => {
  test("loads tutorial catalog from BFF", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".app__brand-mark")).toHaveText("locus");
    await expect(page.getByTestId("side-tutorials").locator(".side__item").first()).toBeVisible({
      timeout: 30_000,
    });
    const items = page.getByTestId("side-tutorials").locator(".side__item");
    expect(await items.count()).toBeGreaterThan(20);
  });

  test("provider settings round-trip via localStorage", async ({ page }) => {
    await configureOCI(page);
    await page.reload();
    await page.getByTestId("settings-btn").click();
    await expect(page.getByTestId("cfg-profile")).toHaveValue(PROFILE);
    await expect(page.getByTestId("cfg-compartment")).toHaveValue(COMPARTMENT);
  });

  test("settings modal lists models for the live OCI connection", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByTestId("settings-btn").click();
    await expect.poll(
      async () => {
        const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
        return opts.some((m) => m.startsWith("openai.gpt-5.5"));
      },
      { timeout: 30_000 },
    ).toBe(true);
  });

  test("runs an edited tutorial subprocess against OCI gpt-5.5", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOCI(page);
    await expect.poll(async () => page.evaluate(() => Boolean((window as any).__wb)), { timeout: 10_000 }).toBe(true);
    await expect.poll(
      async () => page.evaluate(() => ((window as any).__wb?.getSource?.() ?? "").length),
      { timeout: 15_000 },
    ).toBeGreaterThan(100);
    await page.evaluate(() => {
      const wb = (window as any).__wb as { setSource: (s: string) => void };
      wb.setSource("print('locus-workbench-marker-7421')\n");
    });
    await page.getByTestId("wb-run-btn").click();
    await expect(page.getByTestId("wb-output")).toContainText("locus-workbench-marker-7421", {
      timeout: 60_000,
    });
    await expect(page.getByTestId("wb-output")).toContainText(/exited with code 0/i, { timeout: 60_000 });
  });

  test("streams ModelChunkEvents live for a tutorial that runs an Agent", async ({ page }) => {
    test.setTimeout(240_000);
    await configureOCI(page);
    await expect.poll(async () => page.evaluate(() => Boolean((window as any).__wb)), { timeout: 10_000 }).toBe(true);
    // Replace the editor with a tiny program that constructs and runs an
    // Agent — the bootstrap should patch model.complete to stream tokens.
    await page.evaluate(() => {
      const wb = (window as any).__wb as { setSource: (s: string) => void };
      wb.setSource(`from config import get_model
from locus.agent import Agent, AgentConfig
agent = Agent(config=AgentConfig(model=get_model(), system_prompt="Reply with 'pong' and nothing else.", max_iterations=2))
print(agent.run_sync("ping").message)
`);
    });
    await page.getByTestId("wb-run-btn").click();
    // Live chunk transcript appears as tokens stream in.
    await expect(page.getByTestId("live-chunk")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("wb-output")).toContainText(/exited with code 0/i, { timeout: 120_000 });
    // We expect at least one TerminateEvent rendered as a chip.
    const chips = await page.locator(".wb-output .event__kind").allTextContents();
    expect(chips.some((c) => c.toLowerCase().includes("terminate"))).toBe(true);
  });

  test("SDK transport works with cohere.command-r-plus", async ({ page }) => {
    test.setTimeout(180_000);
    await configureOCI(page, { transport: "sdk", model: "cohere.command-r-plus-08-2024" });
    await expect(page.locator("#wb-provider-pill")).toContainText("cohere.command-r-plus-08-2024");
    await expect(page.locator("#wb-provider-pill")).toContainText("sdk");
  });
});

const openaiTest = OPENAI_KEY ? test : test.skip;
test.describe("locus sandbox · OpenAI", () => {
  openaiTest("workbench runs against OpenAI gpt-5", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByTestId("settings-btn").click();
    await page.getByTestId("cfg-provider").selectOption("openai");
    await page.getByTestId("cfg-apikey").fill(OPENAI_KEY ?? "");
    await expect(async () => {
      const opts = await page.getByTestId("cfg-model").locator("option").allTextContents();
      expect(opts.includes("gpt-5")).toBe(true);
    }).toPass({ timeout: 10_000 });
    await page.getByTestId("cfg-model").selectOption("gpt-5");
    await page.getByTestId("settings-save").click();
    await expect.poll(async () => page.evaluate(() => Boolean((window as any).__wb)), { timeout: 10_000 }).toBe(true);
    await page.evaluate(() => {
      const wb = (window as any).__wb as { setSource: (s: string) => void };
      wb.setSource("print('openai-marker-9001')\n");
    });
    await page.getByTestId("wb-run-btn").click();
    await expect(page.getByTestId("wb-output")).toContainText("openai-marker-9001", { timeout: 60_000 });
  });
});

const anthropicTest = ANTHROPIC_KEY ? test : test.skip;
test.describe("locus sandbox · Anthropic", () => {
  anthropicTest("workbench runs against Anthropic claude-sonnet-4-6", async ({ page }) => {
    test.setTimeout(180_000);
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
    await expect.poll(async () => page.evaluate(() => Boolean((window as any).__wb)), { timeout: 10_000 }).toBe(true);
    await page.evaluate(() => {
      const wb = (window as any).__wb as { setSource: (s: string) => void };
      wb.setSource("print('anthropic-marker-3030')\n");
    });
    await page.getByTestId("wb-run-btn").click();
    await expect(page.getByTestId("wb-output")).toContainText("anthropic-marker-3030", { timeout: 60_000 });
  });
});
