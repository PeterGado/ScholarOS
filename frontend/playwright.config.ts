import { defineConfig, devices } from "@playwright/test";

/** Stage 9 (Full browser E2E validation) - drives the real app against a real backend.
 * The backend must already be running (see docs/Frontend_Implementation_Plan.md Sec5 Stage 9)
 * at PLAYWRIGHT_API_BASE_URL; this config only manages the frontend dev server by default.
 *
 * CI (2026-10-08) runs only the `hermetic` project - the specs whose own headers state they
 * need no live AI provider. The remaining specs require a real, billable model call, or
 * pre-seeded AI-generated state, and stay a deliberate manual-verification step; they are not
 * skipped inside CI, they are simply not in the project CI selects.
 */

/** Specs that need no *live* AI provider call, so they can run for real in CI: upload-limits
 * and ui-redesign-and-document-retry need no provider at all (the second drives a genuine
 * extraction failure, which happens before any AI call); the other five run against
 * AI_PROVIDER=fake (app.ai.providers.fake, backend-only, no network/API key) instead of a real
 * provider, since none of them actually assert on real AI response content - only on
 * structural/UI outcomes a deterministic fake response satisfies just as well. Keep this list
 * in sync with each spec's header.
 *
 * persistent-brain-memory.spec.ts stays manual-only: it depends on memory records seeded by an
 * earlier real conversation, a setup step this repo has no automated equivalent for yet. */
const HERMETIC_SPECS = [
  "**/upload-limits.spec.ts",
  "**/ui-redesign-and-document-retry.spec.ts",
  "**/chat-reply-failure.spec.ts",
  "**/persistent-brain-chat.spec.ts",
  "**/persistent-brain-documents.spec.ts",
  "**/persistent-brain-reset-and-formats.spec.ts",
  "**/writing-style-and-toast.spec.ts",
];

const frontendServer = {
  command: "npm run dev -- --port 5173 --host 127.0.0.1",
  url: "http://127.0.0.1:5173",
  reuseExistingServer: !process.env.CI,
  env: {
    VITE_API_BASE_URL: process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8123",
  },
};

/** Started only when PLAYWRIGHT_START_BACKEND=1 (CI). Locally the backend is expected to be
 * already running, exactly as it always was, so manual runs keep their current workflow and
 * only the CI environment opts into having Playwright own the backend process too.
 *
 * Credentials/DATABASE_URL/STORAGE_ROOT are inherited from the caller (`...process.env`) rather
 * than defaulted here: each hermetic spec needs its own genuinely fresh throwaway
 * user/database (its own header says so), and the caller is what gives it one per spec.
 */
const backendServer = {
  command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8123",
  cwd: "../backend",
  url: "http://127.0.0.1:8123/health",
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
  env: { ...process.env } as Record<string, string>,
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: process.env.PLAYWRIGHT_START_BACKEND === "1" ? [backendServer, frontendServer] : frontendServer,
  projects: [
    { name: "hermetic", testMatch: HERMETIC_SPECS, use: { ...devices["Desktop Chrome"] } },
    // Everything else - kept as one project so a manual `npm run e2e` still covers all eight
    // specs exactly once, with no overlap and no duplication against `hermetic`.
    { name: "manual", testIgnore: HERMETIC_SPECS, use: { ...devices["Desktop Chrome"] } },
  ],
});
