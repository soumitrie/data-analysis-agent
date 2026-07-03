import { test, expect } from '@playwright/test'
import path from 'node:path'

// Resolve the repo-root sample CSV produced by the backend slice.
// This spec file lives at: <repo>/frontend/tests/e2e/ask.spec.ts
const SAMPLE_CSV = path.resolve(__dirname, '../../../samples/transactions_sample.csv')

/**
 * Phase-2 live E2E — Ask + Observe.
 *
 * Prereqs (operator): backend + built frontend must be running:
 *   cd frontend && pnpm build && cd .. && uv run python -m src
 * Then from frontend/:
 *   npx playwright test tests/e2e/ask.spec.ts --reporter=line
 *
 * Asserts against the REAL Gemini-backed pipeline:
 *   (1) an NL request adds a 4th chart card with a real Plotly node,
 *   (2) "Show data" expands an aggregated table with rows,
 *   (3) the Cost & tokens panel shows a real numeric token count.
 */
test('ask for a chart, show its data, and observe cost/tokens', async ({ page }) => {
  await page.goto('./')

  // Upload the sample CSV and wait for the auto 3-chart pack.
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_CSV)
  await expect(page.getByTestId('dataset-loaded')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('mapping-panel')).toBeVisible({ timeout: 45_000 })

  const cards = page.getByTestId('chart-card')
  await expect(cards).toHaveCount(3, { timeout: 45_000 })
  // Every auto-pack card has rendered a real Plotly node.
  for (let i = 0; i < 3; i++) {
    const plotNode = cards
      .nth(i)
      .locator('.js-plotly-plot svg.main-svg, .js-plotly-plot canvas')
      .first()
    await expect(plotNode).toBeVisible({ timeout: 20_000 })
  }

  // (3) Cost & tokens panel shows a real numeric token count after analyze.
  const costPanel = page.getByTestId('cost-panel')
  await expect(costPanel).toBeVisible()
  const totalTokens = page.getByTestId('cost-total-tokens')
  await expect(totalTokens).toBeVisible({ timeout: 30_000 })
  const tokenText = (await totalTokens.innerText()).trim()
  // A real count like "1,120" — digits present, not the placeholder "——".
  expect(tokenText).toMatch(/\d/)
  expect(tokenText).not.toContain('——')

  // (1) Ask for a new chart in plain English → a 4th card appears.
  const askInput = page.getByTestId('ask-input')
  await expect(askInput).toBeEnabled({ timeout: 45_000 })
  await askInput.fill('monthly total by category')
  await page.getByTestId('ask-submit').click()

  // The asked chart is appended to the pack (auto-pack of 3 → 4).
  await expect(cards).toHaveCount(4, { timeout: 60_000 })
  const askedCard = cards.nth(3)
  const askedPlot = askedCard
    .locator('.js-plotly-plot svg.main-svg, .js-plotly-plot canvas')
    .first()
  await expect(askedPlot).toBeVisible({ timeout: 20_000 })

  // (2) "Show data" on the asked chart → aggregated table with rows renders.
  await askedCard.getByTestId('show-data-toggle').click()
  const drawer = askedCard.getByTestId('data-table-drawer')
  await expect(drawer).toBeVisible()
  const dataTable = askedCard.getByTestId('data-table')
  await expect(dataTable).toBeVisible({ timeout: 30_000 })
  // At least one aggregated data row is present.
  await expect(dataTable.locator('tbody tr')).not.toHaveCount(0)
})
