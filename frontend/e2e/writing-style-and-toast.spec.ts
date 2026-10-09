import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

// Verification for: writing-style samples no longer polluting the Research Documents page,
// the Writing Style page remembering uploads across a reload, style extraction, and the
// "finished processing" toast on the Research Documents page. Real backend, a fresh throwaway
// user/database. Runs in CI (2026-10-09) against AI_PROVIDER=fake (app.ai.providers.fake) -
// this spec only checks that extraction returns a non-empty, well-shaped characteristics list
// and that processing completes, never specific AI-generated content.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_DOCX = path.join(__dirname, "fixtures", "sample.docx");

test.setTimeout(90_000);

test("writing style samples stay off Research Documents, persist across reload, and extraction works", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
  await page.getByLabel("Project title").fill("Style Fix Verification");
  await page.getByLabel("Topic").fill("Checking the writing style fix");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Upload a writing style sample.
  await page.getByRole("link", { name: "Writing Style" }).click();
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_DOCX);
  await page.getByRole("button", { name: "Upload sample" }).click();
  await expect(page.getByText("sample.docx")).toBeVisible({ timeout: 10_000 });

  // It must never appear on Research Documents, stuck at pending. This spec never uploads
  // anything to Research Documents itself, so the empty state here is "No documents yet" (zero
  // documents total) rather than "Nothing pending" (which other specs see once they already
  // have at least one processed document) - found while verifying this still matches current
  // copy.
  await page.getByRole("link", { name: "Research Documents" }).click();
  await expect(page.getByText("No documents yet")).toBeVisible();
  await expect(page.getByText("sample.docx")).toHaveCount(0);

  // Reload the Writing Style page - the upload must still be listed (not lost local state).
  await page.getByRole("link", { name: "Writing Style" }).click();
  await page.reload();
  await expect(page.getByText("sample.docx")).toBeVisible({ timeout: 10_000 });

  // Real extraction against the real AI provider.
  const extractResponse = page.waitForResponse(
    (r) => r.url().includes("/style-profile/extract") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: /Extract style profile from 1 uploaded sample/ }).click();
  const response = await extractResponse;
  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.characteristics.length).toBeGreaterThan(0);
  await expect(page.getByText(body.characteristics[0].characteristic_type)).toBeVisible({
    timeout: 5_000,
  });
});

test("a document that finishes processing shows a confirmation toast", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/chat/, { timeout: 15_000 });

  await page.getByRole("link", { name: "Research Documents" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "toast-check.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Coastal erosion accelerates near unprotected shorelines."),
  });
  await page.getByRole("button", { name: "Upload" }).click();

  // getByRole("status") can resolve to two stacked toasts at once (the initial "uploaded,
  // queued" one plus this "finished processing" one, if processing finishes before the first
  // one's own auto-dismiss) - found while verifying this spec against a fast fake AI provider
  // in CI, a timing this spec's original real-provider latency likely never triggered. Scoping
  // to the specific text avoids the ambiguity regardless of how many toasts are visible.
  await expect(page.getByRole("status").filter({ hasText: /finished processing/i })).toBeVisible({
    timeout: 30_000,
  });
});
