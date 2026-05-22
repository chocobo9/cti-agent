import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

const checks = [
  { testid: 'confidence-badge-high_confidence', expected: 'rgb(220, 245, 230)', label: 'High confidence bg' },
  { testid: 'confidence-badge-medium_confidence', expected: 'rgb(255, 243, 214)', label: 'Medium confidence bg' },
  { testid: 'confidence-badge-low_confidence', expected: 'rgb(253, 226, 214)', label: 'Low confidence bg' },
  { testid: 'confidence-badge-insufficient', expected: 'rgb(236, 236, 234)', label: 'Insufficient bg' },
];

for (const { testid, expected, label } of checks) {
  const el = page.locator(`[data-testid="${testid}"]`);
  const count = await el.count();
  if (count === 0) {
    console.log(`${label}: NOT FOUND — SKIP`);
    continue;
  }
  const bg = await el.first().evaluate(node => getComputedStyle(node).backgroundColor);
  console.log(`${label}: ${bg} (expected: ${expected}) ${bg === expected ? 'PASS' : 'FAIL'}`);
}

const sourceBadges = [
  { testid: 'source-badge-graph', expected: 'rgb(237, 233, 252)', label: 'GRAPH badge bg' },
  { testid: 'source-badge-rag', expected: 'rgb(223, 236, 246)', label: 'RAG badge bg' },
  { testid: 'source-badge-llm', expected: 'rgb(236, 236, 234)', label: 'LLM badge bg' },
];

for (const { testid, expected, label } of sourceBadges) {
  const el = page.locator(`[data-testid="${testid}"]`);
  const count = await el.count();
  if (count === 0) {
    console.log(`${label}: NOT FOUND — SKIP`);
    continue;
  }
  const bg = await el.first().evaluate(node => getComputedStyle(node).backgroundColor);
  console.log(`${label}: ${bg} (expected: ${expected}) ${bg === expected ? 'PASS' : 'FAIL'}`);
}

await page.screenshot({ path: 'screenshot-tokens.png', fullPage: true });
await browser.close();
