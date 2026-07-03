import { test, expect } from '@playwright/test'
import path from 'node:path'

// Resolve the repo-root sample CSV produced by the backend slice.
// This spec file lives at: <repo>/frontend/tests/e2e/chart_pack.spec.ts
// (Playwright transpiles specs as CommonJS, so __dirname is available.)
const SAMPLE_CSV = path.resolve(__dirname, '../../../samples/transactions_sample.csv')

/**
 * Phase-1 live smoke test.
 *
 * Prereqs (operator): backend + built frontend must be running:
 *   cd frontend && pnpm build && cd .. && uv run python -m src
 * Then run from frontend/:
 *   npx playwright test tests/e2e/ --reporter=line
 *
 * Asserts the full primary journey against the REAL Gemini-backed pipeline:
 *   (1) the four detected column roles appear in the mapping panel,
 *   (2) three chart cards each render a real Plotly SVG/canvas node
 *       (not a spinner and not an error), and
 *   (3) the page is styled with the IB house-style palette.
 */
test('upload sample CSV → auto 3-chart pack renders', async ({ page }) => {
  await page.goto('./')

  // Page is styled (IB house style, not default/unstyled).
  await expect(page.getByRole('heading', { name: 'Ledger Lens', level: 1 })).toBeVisible()
  const header = page.locator('header').first()
  const headerBg = await header.evaluate((el) => getComputedStyle(el).backgroundColor)
  // Navy #1B2A41 == rgb(27, 42, 65). Assert a real (non-transparent) styled bg.
  expect(headerBg).toBe('rgb(27, 42, 65)')

  // Upload the sample CSV via the (hidden) file input.
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_CSV)

  // Dataset-loaded confirmation appears (upload succeeded).
  await expect(page.getByTestId('dataset-loaded')).toBeVisible({ timeout: 30_000 })

  // Wait for analysis to finish: the staged spinner disappears and the
  // mapping panel appears.
  const mapping = page.getByTestId('mapping-panel')
  await expect(mapping).toBeVisible({ timeout: 45_000 })

  // (1) Four detected roles, each showing a resolved column name.
  for (const role of ['date', 'amount', 'category', 'counterparty']) {
    const cell = page.getByTestId(`role-${role}`)
    await expect(cell).toBeVisible()
    const text = (await cell.innerText()).trim()
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toContain('— not detected')
  }

  // The progress spinner is gone.
  await expect(page.getByTestId('progress-spinner')).toHaveCount(0)
  // No error callout when charts came back.
  await expect(page.getByTestId('error-callout')).toHaveCount(0)

  // (2) Three chart cards, each with a rendered Plotly node (svg or canvas).
  const cards = page.getByTestId('chart-card')
  await expect(cards).toHaveCount(3)
  for (let i = 0; i < 3; i++) {
    const card = cards.nth(i)
    const plotNode = card.locator('.js-plotly-plot svg.main-svg, .js-plotly-plot canvas').first()
    await expect(plotNode).toBeVisible({ timeout: 20_000 })
  }
})
