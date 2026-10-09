import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

// Verification for two real bugs found in production use: (1) .docx uploads got permanently
// stuck because the extractor only supported plain UTF-8 text, and (2) there was no way to
// clear a stuck/failed document. A real backend, a fresh throwaway user/database. Runs in CI
// (2026-10-09) against AI_PROVIDER=fake (app.ai.providers.fake) for the knowledge-extraction
// step - this spec only checks processing/failure status, never extracted content, so a
// deterministic fake response satisfies it identically to a real one.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_DOCX = path.join(__dirname, "fixtures", "sample.docx");

test.setTimeout(120_000);

test("a real .docx upload actually processes, and a stuck/failed document can be deleted", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByLabel("Project title").fill("Coastal Resilience Thesis");
  await page.getByLabel("Topic").fill("Coastal erosion mitigation strategies");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Upload a real .docx file from the Documents page.
  await page.getByRole("link", { name: "Research Documents" }).click();
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_DOCX);
  await page.getByRole("button", { name: "Upload" }).click();

  // It must reach "processed" - not get stuck at "pending" or "failed" - and, once processed,
  // disappear from this list entirely (moved into the searchable knowledge base instead). The
  // real processing can finish before this assertion even runs, so check the final state with
  // a generous timeout rather than trying to catch the transient in-progress state.
  await expect(page.getByText("Nothing pending")).toBeVisible({ timeout: 30_000 });

  // Upload a second, corrupted file so it lands in a deletable (failed) state. Must start
  // with the real .docx (zip) magic bytes: the backend now sniffs format at upload time
  // (app.core.document_formats) and rejects anything that doesn't even look like a supported
  // format synchronously, before it's ever queued - a plain garbage buffer (as this fixture
  // used to be) is rejected immediately with "Unsupported file format", never reaching a
  // "failed" badge at all (found while verifying this spec still matches current behavior).
  // These bytes pass that shallow sniff but aren't a valid zip, so the real failure now comes
  // from docx parsing during actual (async) extraction, same as originally intended.
  await page.locator('input[type="file"]').setInputFiles({
    name: "corrupted.docx",
    mimeType: "application/octet-stream",
    buffer: Buffer.from([0x50, 0x4b, 0x03, 0x04, 0xff, 0xfe, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05]),
  });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("failed")).toBeVisible({ timeout: 15_000 });

  // It can now be deleted, and disappears from the list. getByRole's name match is substring,
  // not exact, so "Delete" alone also matches the sidebar's "Delete conversation" button -
  // exact: true disambiguates (same fix as upload-limits.spec.ts).
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText("Nothing pending")).toBeVisible();
});
