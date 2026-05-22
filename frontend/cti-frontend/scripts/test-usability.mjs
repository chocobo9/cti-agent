import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

console.log('=== Test 1: Empty state ===');
const composerArea = page.locator('[data-testid="composer"] textarea');
const composerVisible = await composerArea.isVisible();
console.log(`Composer visible: ${composerVisible ? 'PASS' : 'FAIL'}`);

console.log('\n=== Test 2: Send query ===');
await composerArea.fill('谁控制 hamadryas.online？');
await composerArea.press('Control+Enter');
await page.waitForTimeout(300);

// Check user message appeared
const userMsg = page.locator('text=谁控制 hamadryas.online？');
const msgCount = await userMsg.count();
console.log(`User message rendered: ${msgCount > 0 ? 'PASS' : 'FAIL'}`);

// Check node queue appeared
const nodeQueue = page.locator('[data-testid="node-queue"]');
const queueExists = await nodeQueue.count() > 0;
console.log(`Node queue appeared: ${queueExists ? 'PASS' : 'FAIL'}`);

await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-usability-2-streaming.png' });

console.log('\n=== Test 3: Wait for mock to complete ===');
await page.waitForTimeout(4000);

const doneCard = page.locator('[data-testid="attribution-result-done"]');
const doneVisible = await doneCard.count() > 0;
console.log(`Done card visible: ${doneVisible ? 'PASS' : 'FAIL'}`);

// Check pinboard has real data now
const pinAttribution = page.locator('[data-testid="pin-card-attribution"]');
const pinAttrText = await pinAttribution.textContent();
const hasRealData = pinAttrText && pinAttrText.includes('0.85');
console.log(`Pinboard has real data: ${hasRealData ? 'PASS' : 'FAIL'}`);

await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-usability-3-complete.png' });

console.log('\n=== Test 4: Node expansion ===');
const nodeRow = page.locator('[data-testid="node-row-infrastructure"]');
if (await nodeRow.count() > 0) {
  await nodeRow.click();
  await page.waitForTimeout(300);
  const expanded = page.locator('[data-testid="node-row-infrastructure-expanded"]');
  console.log(`Node expansion works: ${await expanded.count() > 0 ? 'PASS' : 'FAIL'}`);
}

console.log('\n=== Test 5: Fullscreen modal ===');
const expandBtn = page.locator('[data-testid="pin-card-candidates"] button[title="Open fullscreen"]');
if (await expandBtn.count() > 0) {
  await expandBtn.click();
  await page.waitForTimeout(500);
  const modal = page.locator('[data-testid="fullscreen-modal"]');
  console.log(`Fullscreen modal opens: ${await modal.count() > 0 ? 'PASS' : 'FAIL'}`);

  const graph = page.locator('[data-testid="node-edge-graph"]');
  console.log(`NodeEdgeGraph present: ${await graph.count() > 0 ? 'PASS' : 'FAIL'}`);

  await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-usability-4-modal.png' });

  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  console.log(`ESC closes modal: ${await modal.count() === 0 ? 'PASS' : 'FAIL'}`);
}

console.log('\n=== Test 6: Segmented control (Raw JSON) ===');
const rawBtn = page.locator('button:has-text("Raw JSON")');
if (await rawBtn.count() > 0) {
  await rawBtn.click();
  await page.waitForTimeout(300);
  const rawPanel = page.locator('[data-testid="raw-json-panel"]');
  console.log(`Raw JSON panel visible: ${await rawPanel.count() > 0 ? 'PASS' : 'FAIL'}`);
  await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-usability-5-rawjson.png' });
}

console.log('\n=== All tests complete ===');
await browser.close();
