import { test, expect } from "@playwright/test";

const COMPARTMENT =
  process.env.OCI_COMPARTMENT ??
  "ocid1.compartment.oc1..aaaaaaaandceai675euuovyyazlymnglde2xknsq35rni43zzmwdhxxu4v7q";
const PROFILE = process.env.OCI_PROFILE ?? "BOAT-OC1";
const REGION = process.env.OCI_REGION ?? "us-chicago-1";

async function configureOCISession(page: import("@playwright/test").Page) {
  await page.getByTestId("settings-btn").click();
  await page.getByTestId("cfg-provider").selectOption("oci-session");
  await page.getByTestId("cfg-model").fill("openai.gpt-5");
  await page.getByTestId("cfg-profile").fill(PROFILE);
  await page.getByTestId("cfg-region").fill(REGION);
  await page.getByTestId("cfg-compartment").fill(COMPARTMENT);
  await page.getByTestId("settings-save").click();
}

test.describe("locus sandbox", () => {
  test("loads pattern catalog from BFF", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".app__brand-mark")).toHaveText("locus");
    // 7 patterns from the runner.
    const items = page.locator("[data-testid^='pattern-']");
    await expect(items).toHaveCount(7);
    await expect(page.getByTestId("pattern-agent")).toBeVisible();
    await expect(page.getByTestId("pattern-orchestrator")).toBeVisible();
  });

  test("provider settings round-trip via localStorage", async ({ page }) => {
    await page.goto("/");
    await configureOCISession(page);
    // Provider pill should reflect the saved config.
    await expect(page.locator("#provider-pill")).toContainText(PROFILE);
    await page.reload();
    await expect(page.locator("#provider-pill")).toContainText(PROFILE);
  });

  test("runs the basic agent end-to-end against OCI GenAI", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");
    await configureOCISession(page);
    await page.getByTestId("pattern-agent").click();
    await page.getByTestId("prompt").fill("Say 'pong' and nothing else.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
    const reply = (await page.getByTestId("final-reply").textContent())?.trim() ?? "";
    expect(reply.length).toBeGreaterThan(0);
  });

  test("runs agent_with_tools and renders tool events", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto("/");
    await configureOCISession(page);
    await page.getByTestId("pattern-agent_with_tools").click();
    await page.getByTestId("prompt").fill("What is 17 + 25? Reverse 'locus'.");
    await page.getByTestId("send-btn").click();
    await expect(page.getByTestId("final-reply")).toBeVisible({ timeout: 120_000 });
    const events = page.getByTestId("event");
    expect(await events.count()).toBeGreaterThan(2);
    // At least one ToolStart event should appear.
    const allKinds = await events.locator(".event__kind").allTextContents();
    expect(allKinds.some((k) => k.startsWith("Tool"))).toBe(true);
  });
});
