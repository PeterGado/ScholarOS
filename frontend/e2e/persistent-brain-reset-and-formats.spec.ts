import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

// Verification for: workspace reset (letting a user re-test onboarding), PDF upload
// processing, and conversation deletion from the sidebar. Real backend, a fresh throwaway
// user/database. Runs in CI (2026-10-09) against AI_PROVIDER=fake (app.ai.providers.fake) for
// the knowledge-extraction step - this spec only checks processing status, never extracted
// content, so a deterministic fake response satisfies it identically to a real one.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_PDF = path.join(__dirname, "fixtures", "sample.pdf");

test.setTimeout(120_000);

test("reset workspace, re-onboard, upload a real PDF, and delete a conversation", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  // Originally written assuming a workspace already existed from an earlier manual run against
  // the same long-lived database - not true of this spec's own fresh-per-run database (each
  // hermetic spec gets one), so onboard once first to create a real workspace to reset (found
  // while adding this spec to automated CI, where every run starts genuinely fresh).
  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByLabel("Project title").fill("First Onboarding Pass");
  await page.getByLabel("Topic").fill("Setting up a workspace to reset");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Now go to Settings and reset it, exactly the flow that unblocks "I can't check the new
  // onboarding".
  await expect(page).toHaveURL(/\/chat/);
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel(/Type RESET to confirm/).fill("RESET");
  await page.getByRole("button", { name: "Permanently reset my workspace" }).click();

  // Reset lands back in onboarding, fresh.
  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
  await page.getByLabel("Project title").fill("Second Onboarding Pass");
  await page.getByLabel("Topic").fill("Verifying the reset feature");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Real PDF upload actually processes (not stuck pending/failed).
  await page.getByRole("link", { name: "Research Documents" }).click();
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_PDF);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("Nothing pending")).toBeVisible({ timeout: 30_000 });

  // Conversation deletion from the sidebar.
  await page.getByRole("link", { name: "Chat" }).click();
  await page.locator("aside").getByRole("button", { name: "New chat" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });
  const activeConversationLink = page.locator("aside a[href^='/chat/'][aria-current='page']");
  await expect(activeConversationLink).toBeVisible();
  await expect(activeConversationLink).toHaveText(/Untitled conversation/);
  const deletedHref = await activeConversationLink.getAttribute("href");

  page.once("dialog", (dialog) => dialog.accept());
  await page
    .locator(`aside div:has(> a[href="${deletedHref}"])`)
    .getByRole("button", { name: "Delete conversation" })
    .click();
  await expect(page.locator(`aside a[href="${deletedHref}"]`)).toBeHidden();
});
