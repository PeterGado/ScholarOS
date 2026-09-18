import { test, expect } from "@playwright/test";

// Real manual verification for Persistent Brain v2 (Reflection & Memory Control): the Memory
// page against a backend that already has real, AI-generated, provenance-linked Memory
// Records (seeded via a real approved-review generation before this spec runs) - and a live
// supersede/correction action through the UI.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";

test.setTimeout(60_000);

test("memory page shows real AI-generated memory with provenance and supports live correction", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.getByRole("link", { name: "Memory" }).click();
  await expect(page).toHaveURL(/\/memory$/);

  // Two real memory records were seeded by an approved review before this test ran. Their
  // exact record_type classification is the real model's own (non-deterministic) choice, so
  // this only asserts that real, badged, provenance-linked records are present - not which
  // specific types the model picked.
  const cards = page.locator('[data-slot="card"]');
  await expect(cards).toHaveCount(2);
  await expect(page.locator('[data-slot="badge"]')).toHaveCount(2);
  expect(await page.getByText("from an approved review").count()).toBeGreaterThanOrEqual(2);

  // Live correction: "Correct this" -> edit -> "Save correction" actually persists.
  await page.getByRole("button", { name: "Correct this" }).first().click();
  const textarea = page.locator("textarea");
  await textarea.fill("Corrected via the UI during manual verification.");
  await page.getByRole("button", { name: "Save correction" }).click();

  await expect(page.getByText("Corrected via the UI during manual verification.")).toBeVisible();
  // The record count stays the same (superseded record excluded from the current listing).
  await expect(cards).toHaveCount(2);
});
