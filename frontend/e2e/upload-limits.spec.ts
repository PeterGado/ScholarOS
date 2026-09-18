import { test, expect } from "@playwright/test";

// Real manual verification for the new upload limits: 20 research documents per project, 5
// writing-style samples, both enforced server-side and reflected proactively in the UI. Real
// backend, a fresh throwaway user/database. No AI provider call needed - the limit is checked
// before a document is ever enqueued for processing.

const USERNAME = process.env.PLAYWRIGHT_AUTH_USERNAME ?? "manual-verify-user";
const PASSWORD = process.env.PLAYWRIGHT_AUTH_PASSWORD ?? "ManualVerify-Pass-1";

test.setTimeout(120_000);

// Waits on the real upload response rather than intermediate UI text: the throwaway backend
// runs a real background executor that may process (and hide, per the "vanishes on success"
// design) earlier documents while this loop is still uploading more, so the visible count can
// legitimately lag a step behind - only the final aggregate state is worth asserting on.
async function uploadTextFile(page: import("@playwright/test").Page, name: string, buttonName: string) {
  await page.locator('input[type="file"]').setInputFiles({
    name,
    mimeType: "text/plain",
    buffer: Buffer.from(`Content of ${name}.`),
  });
  const uploadResponse = page.waitForResponse(
    (r) => r.url().includes("/documents") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: buttonName, exact: true }).click();
  const response = await uploadResponse;
  expect(response.status()).toBe(201);
}

test("research document upload is blocked at the 20-document limit", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 });
  await page.getByLabel("Project title").fill("Upload Limit Verification");
  await page.getByLabel("Topic").fill("Checking the document cap");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Add your documents (optional)")).toBeVisible();
  await page.getByRole("button", { name: "Skip and generate" }).click();
  await expect(page).toHaveURL(/\/chat/, { timeout: 20_000 });

  await page.getByRole("link", { name: "Research Documents" }).click();
  for (let i = 0; i < 20; i++) {
    await uploadTextFile(page, `doc-${i}.txt`, "Upload");
  }

  // The form is now proactively disabled - the count driving this came from a real server
  // response, not a hardcoded frontend assumption (server-side 409 enforcement itself is
  // covered directly by the backend's own e2e test).
  await expect(page.getByText("(20/20 used)")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Upload", exact: true })).toBeDisabled();
  await expect(page.getByText("You've reached the 20-document limit")).toBeVisible();
});

test("writing style sample upload is blocked at the 5-sample limit, and deleting one makes room", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill(USERNAME);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  // A more generous timeout than the other test's: this test runs right after 20 real
  // documents' worth of background AI processing was enqueued, which can leave the throwaway
  // backend busy long enough to slow down an unrelated login request too.
  await expect(page).toHaveURL(/\/chat/, { timeout: 45_000 });

  await page.getByRole("link", { name: "Writing Style" }).click();
  for (let i = 0; i < 5; i++) {
    await uploadTextFile(page, `sample-${i}.txt`, "Upload sample");
  }

  await expect(page.getByText("(5/5 used)")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Upload sample" })).toBeDisabled();
  await expect(page.getByText("You've reached the 5-sample limit")).toBeVisible();

  // Deleting one sample makes room for another.
  const deleteResponse = page.waitForResponse(
    (r) => r.url().includes("/documents/") && r.request().method() === "DELETE",
  );
  await page.getByRole("button", { name: "Delete" }).first().click();
  const response = await deleteResponse;
  expect(response.status()).toBe(204);
  await expect(page.getByText("(4/5 used)")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Upload sample" })).toBeEnabled();
});
