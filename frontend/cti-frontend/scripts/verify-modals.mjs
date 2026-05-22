import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

const cards = ['attribution', 'candidates', 'infrastructure', 'evidence'];

for (const card of cards) {
  const expandBtn = page.locator(`[data-testid="pin-card-${card}"] button[title="Open fullscreen"]`);
  const count = await expandBtn.count();
  if (count === 0) {
    console.log(`${card}: expand button NOT FOUND — FAIL`);
    continue;
  }

  await expandBtn.click();
  await page.waitForTimeout(500);

  const modal = page.locator('[data-testid="fullscreen-modal"]');
  const modalVisible = await modal.count() > 0;
  console.log(`${card}: modal open — ${modalVisible ? 'PASS' : 'FAIL'}`);

  if (modalVisible) {
    const backdrop = await modal.evaluate(el => getComputedStyle(el).backdropFilter);
    console.log(`${card}: backdrop-filter="${backdrop}" — ${backdrop !== 'none' ? 'PASS' : 'FAIL'}`);

    await page.screenshot({ path: `D:/proj/agent/cti-agent/frontend/harness/screenshot-step7-${card}-fs.png` });

    if (card === 'candidates') {
      const graph = page.locator('[data-testid="node-edge-graph"]');
      const graphExists = await graph.count() > 0;
      if (graphExists) {
        const circles = await graph.locator('circle').count();
        console.log(`${card}: NodeEdgeGraph has ${circles} circles — ${circles >= 3 ? 'PASS' : 'FAIL'}`);
      } else {
        console.log(`${card}: NodeEdgeGraph NOT FOUND — FAIL`);
      }
    }

    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    const modalGone = await modal.count() === 0;
    console.log(`${card}: ESC close — ${modalGone ? 'PASS' : 'FAIL'}`);
  }
}

await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-step7-main.png' });
await browser.close();
