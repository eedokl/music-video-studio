// Screenshot a studio page at desktop size (UI checks): node shot.mjs URL out.png [waitMs] [jsBeforeShot]
import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { launch } from './chrome.mjs';
const [url, out, wait = '4000', js = ''] = process.argv.slice(2);
const browser = await launch(['--autoplay-policy=no-user-gesture-required']);
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900 });
page.on('pageerror', (e) => console.error('page error:', e.message));
page.on('console', (m) => (m.type() === 'error' || m.type() === 'warning') && console.error(`console ${m.type()}:`, m.text()));
await page.goto(url, { waitUntil: 'networkidle0', timeout: 60000 });
await new Promise((r) => setTimeout(r, Number(wait)));
if (js) {
  console.log('js →', JSON.stringify(await page.evaluate(js)));
  await new Promise((r) => setTimeout(r, 1500));
}
await page.screenshot({ path: out });
await browser.close();
console.log('saved', out);
