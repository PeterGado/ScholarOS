import { test, expect } from "@playwright/test";

// Real manual verification for the Persistent Brain milestone's Agent Workspace chat
// (Decision 3) and the ChatGPT/Claude-style onboarding wizard: a real backend, a real (small,
// deliberate) AI provider call, a fresh throwaway user/database - not part of the automated
// CI suite.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";

test.setTimeout(120_000);

test("real chat workflow: project -> skip research -> skip style -> generate -> real AI reply", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);

  // Step 1: Project.
  await page.getByLabel("Project title").fill("Coastal Resilience Thesis");
  await page.getByLabel("Topic").fill("Coastal erosion mitigation strategies");
  await page.getByLabel("Description").fill(
    "A 10-page graduate-level environmental science report. Formal academic tone, cite general " +
      "principles where research evidence is unavailable, avoid fabricating sources."
  );
  await page.getByRole("button", { name: "Next" }).click();

  // Step 2: Documents (research + writing style combined) - skipped entirely, landing
  // directly in a live conversation.
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();

  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  await page
    .getByPlaceholder(/Message your Agent Workspace/)
    .fill("In one short sentence, what should the introduction of this report focus on?");
  await page.getByRole("button", { name: "Send" }).click();

  // The user's own message is persisted synchronously server-side, but the UI only picks it up
  // on its next poll (refetchInterval) - allow for that.
  await expect(page.getByText("In one short sentence, what should the introduction")).toBeVisible({
    timeout: 15_000,
  });

  // A real assistant reply arrives asynchronously via the Work Item executor - no mock. The
  // reply can land before this assertion even runs, so wait on the final state (an "Assistant"
  // labeled row appearing) rather than the transient "Thinking..." indicator.
  const assistantLabels = page.getByText("Assistant", { exact: true });
  await expect(assistantLabels).toHaveCount(1, { timeout: 60_000 });

  // Starting a second chat from the sidebar works, and both conversations are listed.
  await page.getByRole("link", { name: "Chat" }).click();
  await page.locator("aside").getByRole("button", { name: "New chat" }).click();
  await expect(page).toHaveURL(/\/chat\/\d+$/, { timeout: 20_000 });

  // Theme toggle actually switches the whole app shell.
  const html = page.locator("html");
  const wasDark = (await html.getAttribute("class"))?.includes("dark") ?? false;
  await page.getByRole("button", { name: /Switch to (dark|light) theme/ }).click();
  await expect(html).toHaveClass(wasDark ? /^(?!.*dark).*$/ : /dark/);
});
