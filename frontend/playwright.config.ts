import { defineConfig, devices } from "@playwright/test";

/** Stage 9 (Full browser E2E validation) - drives the real app against a real backend.
 * The backend must already be running (see docs/Frontend_Implementation_Plan.md Sec5 Stage 9)
 * at PLAYWRIGHT_API_BASE_URL; this config only manages the frontend dev server. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --port 5173 --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_BASE_URL: process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8123",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
