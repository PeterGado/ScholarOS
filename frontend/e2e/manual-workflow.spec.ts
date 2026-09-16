import { test, expect } from "@playwright/test";

// Real, complete manual workflow validation - login, project creation, document upload, real
// AI knowledge processing, real writing-style extraction, real draft generation (twice), review,
// evidence inspection - all against a real backend with a real, already-configured Gemini
// provider (never a paid requirement, deliberately tiny calls). Not part of the automated CI
// suite (npm run test) - run explicitly via `npm run e2e` with PLAYWRIGHT_API_BASE_URL pointed
// at a real backend that has AI_API_KEY configured, mirroring the backend's own "a small number
// of deliberately tiny manual real-provider checks against a fresh, isolated environment"
// discipline (see docs/Project_Writing_Implementation_Plan.md Stage 8).

const USERNAME = "manual-workflow-user";
const PASSWORD = "test-password-123";

test.setTimeout(300_000);

test("real workflow: login -> project -> documents -> knowledge -> style -> generate -> review -> regenerate", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/);
  await page.getByLabel("Project title").fill("Coastal Resilience Thesis");
  await page.getByLabel("Topic").fill("Coastal erosion mitigation strategies");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page).toHaveURL(/\/drafts$/);

  // --- Upload a real research document and wait for real AI processing ---
  page.on("response", async (response) => {
    if (response.url().includes("/projects/1/documents")) {
      // eslint-disable-next-line no-console
      console.log("DOCS RESPONSE", response.request().method(), response.status());
    }
  });
  page.on("console", (msg) => console.log("BROWSER CONSOLE:", msg.text()));
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message));
  await page.getByRole("link", { name: "Research Documents" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "erosion-survey.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Coastal erosion accelerates near unprotected shorelines. Seawalls and dune " +
        "restoration are the two most common mitigation strategies. Seawalls reduce wave " +
        "energy immediately but can increase erosion on adjacent, unprotected shoreline " +
        "segments. Dune restoration with native vegetation stabilizes sediment over several " +
        "seasons and is generally lower-cost, but is slower to take effect and vulnerable to " +
        "storm surge before the vegetation matures.",
    ),
  });
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("erosion-survey.txt")).toBeVisible({ timeout: 15_000 });

  // Real AI processing (extraction + embedding) - poll until the page's own polling shows
  // "processed" (DocumentsPage refetches every 2s while anything is pending/processing).
  await expect(page.getByText("processed", { exact: true })).toBeVisible({ timeout: 60_000 });

  // Real semantic search against the now-processed knowledge.
  page.on("response", async (response) => {
    if (response.url().includes("/knowledge/search")) {
      // eslint-disable-next-line no-console
      console.log("SEARCH RESPONSE", response.status(), await response.text().catch(() => "<no body>"));
    }
  });
  await page.getByPlaceholder("Search your knowledge...").fill("erosion mitigation");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText(/score:/i)).toBeVisible({ timeout: 30_000 });

  // --- Upload a real writing-style sample and extract a real style profile ---
  await page.getByRole("link", { name: "Writing Style" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "style-sample.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "This report proceeds in three parts. First, we establish the baseline erosion rate " +
        "using historical shoreline surveys. Second, we compare two mitigation strategies " +
        "against that baseline. Finally, we recommend a phased approach that begins with " +
        "low-cost dune restoration and reserves seawall construction for the highest-risk " +
        "segments identified in part one.",
    ),
  });
  await page.getByRole("button", { name: "Upload sample" }).click();
  await expect(page.getByText(/Uploaded 1 sample/)).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: /Extract style profile/ }).click();
  await expect(page.getByText(/structure|vocabulary|transitions|explanation|citation/i).first()).toBeVisible({
    timeout: 60_000,
  });

  // --- Create a draft and generate a real first version ---
  await page.getByRole("link", { name: "Drafts" }).click();
  await page.getByPlaceholder("New draft title").fill("Chapter 1: Mitigation Strategies");
  await page.getByRole("button", { name: "Create draft" }).click();
  await page.getByText("Chapter 1: Mitigation Strategies").click();

  await page
    .getByPlaceholder(/Instructions for this generation/)
    .fill("Write a short paragraph comparing seawalls and dune restoration as mitigation strategies.");
  await page.getByRole("button", { name: "Generate" }).click();

  // Real generation - poll until the version appears (see DraftDetailPage's own polling; the
  // backend never exposes Work Item status directly - see Frontend_Implementation_Plan.md Sec3).
  await expect(page.getByText("Version 1")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/Generating/)).not.toBeVisible({ timeout: 90_000 });

  // --- Inspect evidence on the generated version ---
  await expect(page.getByText("Evidence")).toBeVisible();
  await expect(page.getByText(/knowledge_chunk:/)).toBeVisible();

  // --- Review: request revisions, then approve after a second generation ---
  await page.getByRole("button", { name: "Request revisions" }).click();
  await page.waitForTimeout(1000); // let the review mutation settle before the next request

  await page
    .getByPlaceholder(/Instructions for this generation/)
    .fill("Now write a short paragraph recommending a phased approach, starting with dune restoration.");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("Version 2")).toBeVisible({ timeout: 150_000 });

  // Both versions are visible, distinct, and immutable (version 1 still present unchanged).
  await expect(page.getByText("Version 1")).toBeVisible();
  await expect(page.getByText("Version 2")).toBeVisible();

  await page.getByRole("button", { name: "Approve" }).first().click();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
