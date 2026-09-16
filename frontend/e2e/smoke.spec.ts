import { test, expect } from "@playwright/test";

// Real end-to-end smoke test against a real, running backend (see playwright.config.ts and
// docs/Frontend_Implementation_Plan.md Sec5 Stage 9) - no mocked network calls. Requires the
// backend's single pre-provisioned user to be configured with username "e2e-test-user" /
// password "test-password-123" against a fresh database (see the Stage 1/2 completion report
// for how this was run manually). AI-provider-dependent steps (real generation) are
// deliberately out of scope here, mirroring the backend's own "fakes/real-backend for
// automated checks, a small manual real-provider pass separately" discipline.

const USERNAME = "e2e-test-user";
const PASSWORD = "test-password-123";

test("full login -> onboarding -> documents -> drafts flow against the real backend", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in to ScholarOS" })).toBeVisible();

  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  // First-run: no Agent workspace yet, WorkspaceGate redirects to onboarding.
  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByLabel("Project title").fill("Thesis");
  await page.getByLabel("Topic").fill("Coastal erosion");
  await page.getByRole("button", { name: "Create workspace" }).click();

  await expect(page).toHaveURL(/\/drafts$/);
  await expect(page.getByRole("heading", { name: "Drafts" })).toBeVisible();

  // Documents: upload a real file against the real backend, confirm it appears.
  await page.getByRole("link", { name: "Research Documents" }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await page.locator('input[type="file"]').setInputFiles({
    name: "sample.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Coastal erosion accelerates near unprotected shorelines."),
  });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("sample.txt")).toBeVisible({ timeout: 10_000 });

  // Drafts: create one, open it, confirm the empty-versions state renders.
  await page.getByRole("link", { name: "Drafts" }).click();
  await page.getByPlaceholder("New draft title").fill("Chapter 1");
  await page.getByRole("button", { name: "Create draft" }).click();
  await expect(page.getByText("Chapter 1")).toBeVisible();
  await page.getByText("Chapter 1").click();
  await expect(page.getByRole("heading", { name: "Chapter 1" })).toBeVisible();
  await expect(page.getByText("No versions yet")).toBeVisible();

  // Log out and confirm the app returns to the login screen.
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
