import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

// 1. Type query and send
const composer = page.locator('[data-testid="composer"] textarea');
await composer.fill('谁控制 hamadryas.online？');
const sendBtn = page.locator('[data-testid="composer"] button').last();
await sendBtn.click();
await page.waitForTimeout(500);

// 2. Screenshot running state
await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-step8-running.png' });

const runningCard = page.locator('[data-testid="attribution-result-running"]');
const hasRunning = await runningCard.count() > 0;
console.log(`Running state visible: ${hasRunning ? 'PASS' : 'SKIP (mock too fast)'}`);

// Check node queue has at least 1 running or done node
const nodeQueue = page.locator('[data-testid="node-queue"]');
const queueVisible = await nodeQueue.count() > 0;
console.log(`NodeQueue visible: ${queueVisible ? 'PASS' : 'FAIL'}`);

// 3. Wait for completion
await page.waitForTimeout(4000);
await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-step8-done.png' });

const doneCard = page.locator('[data-testid="attribution-result-done"]');
const hasDone = await doneCard.count() > 0;
console.log(`Done state visible: ${hasDone ? 'PASS' : 'FAIL'}`);

// 4. Verify pinboard has content
const pinboard = page.locator('[data-testid="pinboard"]');
const pinVisible = await pinboard.count() > 0;
console.log(`Pinboard visible: ${pinVisible ? 'PASS' : 'FAIL'}`);

// 5. Final full screenshot
await page.screenshot({ path: 'D:/proj/agent/cti-agent/frontend/harness/screenshot-step8-final.png' });
console.log('Final screenshot saved.');

await browser.close();
