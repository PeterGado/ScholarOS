import { test, expect } from "@playwright/test";

// Real manual verification for Frontend Stage 8's chat-reply failure/retry UX: before this,
// a genuinely failed reply was indistinguishable from a slow one, with a fixed client-side
// timeout and no explanation or recovery path. Run against a real backend configured with a
// deliberately invalid AI_API_KEY, so every generation attempt genuinely fails through the
// real Gemini provider code path (a real ProviderRequestError, not a mock) - not part of the
// automated CI suite.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";

test.setTimeout(120_000);

test("a genuinely failed reply shows a real error and can be retried", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByLabel("Project title").fill("Reply Failure Verification");
  await page.getByLabel("Topic").fill("Checking the failed-reply UX");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  await page.getByPlaceholder(/Message your Agent Workspace/).fill("Say hello.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Say hello.")).toBeVisible({ timeout: 15_000 });

  // The invalid API key makes every real attempt fail immediately (an auth error, not a
  // timeout) - three real attempts against the real provider exhaust the bounded retry policy
  // well within this window.
  await expect(page.getByText("Reply failed")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("AI provider request failed.")).toBeVisible();
  const retryButton = page.getByRole("button", { name: "Retry", exact: true });
  await expect(retryButton).toBeVisible();

  // Sending is available again once the reply has terminally failed (not left disabled forever
  // by a stuck "waiting for reply" state) - the button is otherwise disabled on empty content
  // regardless of reply state, so type something first to isolate what this checks.
  await page.getByPlaceholder(/Message your Agent Workspace/).fill("A second message.");
  await expect(page.getByRole("button", { name: "Send" })).toBeEnabled();
  await page.getByPlaceholder(/Message your Agent Workspace/).fill("");

  // Retrying re-enters the same real failure path - proving the retry endpoint genuinely
  // re-queues the same Work Item rather than just resetting UI state.
  await retryButton.click();
  await expect(page.getByText("Thinking...")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Reply failed")).toBeVisible({ timeout: 60_000 });
});
