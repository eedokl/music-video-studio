// UI interaction test: drag a word in the timeline, check autosave, undo with Ctrl+Z.
import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import puppeteer from 'puppeteer-core';
const base = resolve(process.env.TEMP ?? '/tmp', 'mvchrome/chrome-headless-shell');
const exe = readdirSync(base).map((v) => resolve(base, v, 'chrome-headless-shell-win64/chrome-headless-shell.exe')).find(existsSync);
const browser = await puppeteer.launch({ executablePath: exe, headless: 'shell', args: ['--use-angle=d3d11', '--enable-gpu'] });
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900 });
page.on('pageerror', (e) => console.error('page error:', e.message));
const wordT = async () => (await (await fetch('http://localhost:8000/api/projects/comfort-zone-v4')).json()).lyrics.lines.find((l) => l.id === 'l50').words[3].t;
const before = await wordT();
await page.goto('http://localhost:8000/#/p/comfort-zone-v4', { waitUntil: 'networkidle0' });
await new Promise((r) => setTimeout(r, 3000));
await page.evaluate(() => window.__seek(199.5));
await new Promise((r) => setTimeout(r, 800));
const box = await (await page.$('.timeline canvas')).boundingBox();
const y = box.y + 100; // words row
await page.mouse.move(box.x + 400, y);
await page.mouse.down();
for (let i = 1; i <= 10; i++) await page.mouse.move(box.x + 400 + i * 5, y);
await page.mouse.up();
await new Promise((r) => setTimeout(r, 1800)); // autosave after 0.7 s
const after = await wordT();
await page.keyboard.down('Control');
await page.keyboard.press('KeyZ');
await page.keyboard.up('Control');
await new Promise((r) => setTimeout(r, 1800));
const undone = await wordT();
const insp = await page.$eval('.insp h3', (e) => e.textContent);
console.log(JSON.stringify({ before, afterDrag: after, afterUndo: undone, inspector: insp }));
await browser.close();
