import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for Ledger Lens Phase-1 smoke tests.
 *
 * These tests run against the LIVE integrated app served by FastAPI at
 * http://localhost:8001/app/ (static Next.js export + backend charting slice).
 * The dev/CI operator must have the server running:
 *   cd frontend && pnpm build && cd .. && uv run python -m src
 * then:
 *   cd frontend && npx playwright test tests/e2e/ --reporter=line
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'line',
  timeout: 60_000,
  expect: { timeout: 45_000 },
  use: {
    baseURL: process.env.LEDGER_LENS_BASE_URL ?? 'http://localhost:8001/app/',
    trace: 'on-first-retry',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
