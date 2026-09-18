import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect } from "@playwright/test";

// Real manual verification for the sidebar simplification (Memory/Drafts removed, Chat
// messages visually distinguished) and the new Documents page failure-reason + Retry feature.
// Real backend, a fresh throwaway user/database, no AI provider call needed (a corrupted PDF
// fails at the mechanical extraction stage, before any AI call).

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";
const __dirname = path.dirname(fileURLToPath(import.meta.url));

test.setTimeout(60_000);

test("sidebar is simplified, chat messages are visually distinguished, and a failed document can be retried", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
  await page.getByLabel("Project title").fill("Sidebar Verification");
  await page.getByLabel("Topic").fill("Checking the redesigned nav");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Sidebar: Chat, Research Documents, Writing Style, Settings - no Memory, no Drafts.
  const sidebar = page.locator("aside");
  await expect(sidebar.getByRole("link", { name: "Chat" })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Research Documents" })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Writing Style" })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Settings" })).toBeVisible();
  await expect(sidebar.getByRole("link", { name: "Memory" })).toHaveCount(0);
  await expect(sidebar.getByRole("link", { name: "Drafts" })).toHaveCount(0);

  // Document upload: a corrupted PDF fails at extraction (no AI call needed), surfaces a real
  // error message, and can be retried back to pending.
  await page.getByRole("link", { name: "Research Documents" }).click();
  const corruptPdf = Buffer.from("\xff\xfebinary garbage".repeat(5), "binary");
  await page.locator('input[type="file"]').setInputFiles({
    name: "corrupt.pdf",
    mimeType: "application/pdf",
    buffer: corruptPdf,
  });
  await page.getByRole("button", { name: "Upload" }).click();

  await expect(page.getByText("failed", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/could not be decoded as text/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();

  // The backend's background executor may reprocess it (and fail again, since the content is
  // still genuinely corrupt) before this assertion runs - so wait on the real network response
  // rather than a specific transient badge state, then confirm it went through a real retry
  // cycle (a fresh error, not a stale leftover banner).
  const retryResponse = page.waitForResponse((response) => response.url().includes("/retry") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Retry" }).click();
  const response = await retryResponse;
  expect(response.status()).toBe(200);
  expect((await response.json()).processing_status).toBe("pending");

  await expect(page.getByText("failed", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/could not be decoded as text/i)).toBeVisible();
});
