import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

const rail = await page.locator('[data-testid="rail"]').boundingBox();
console.log(`Rail width: ${rail?.width}px (expected: 56px) ${Math.abs((rail?.width || 0) - 56) < 2 ? 'PASS' : 'FAIL'}`);

const pinboard = await page.locator('[data-testid="pinboard"]').boundingBox();
console.log(`Pinboard width: ${pinboard?.width}px (expected: 420px) ${Math.abs((pinboard?.width || 0) - 420) < 2 ? 'PASS' : 'FAIL'}`);

const topbar = await page.locator('[data-testid="topbar"]').boundingBox();
console.log(`Topbar height: ${topbar?.height}px (expected: 48px) ${Math.abs((topbar?.height || 0) - 48) < 2 ? 'PASS' : 'FAIL'}`);

await page.screenshot({ path: 'screenshot-layout.png', fullPage: true });
await browser.close();
