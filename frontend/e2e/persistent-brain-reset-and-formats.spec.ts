import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

// Real manual verification for: workspace reset (letting a user re-test onboarding), real PDF
// upload processing, and conversation deletion from the sidebar. Real backend, real (small) AI
// provider calls, a fresh throwaway user/database.

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

  // This user already has a workspace from a prior run - go straight to Settings and reset it,
  // exactly the flow that unblocks "I can't check the new onboarding".
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
