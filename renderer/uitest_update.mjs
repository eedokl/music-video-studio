// UI test of the "Audio aktualisieren" dialog: submit with a file; the upload request is intercepted.
import { existsSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { launch } from './chrome.mjs';
const b = await launch();
const page = await b.newPage();
await page.setViewport({ width: 1600, height: 900 });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
let seen = null;
let seenLen = 0;
await page.setRequestInterception(true);
page.on('request', async (r) => {
  if (r.url().includes('/update-audio')) {
    const body = (r.postData() ?? (r.hasPostData() ? await r.fetchPostData() : '')) ?? '';
    seenLen = body.length;
    seen = { method: r.method(), hasSong: body.includes('name="song"'), hasLyrics: body.includes('name="lyrics"') && body.includes('RBAC') };
    r.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, matched: 44, new: 0, changed: 0, removed: 0 }) });
  } else r.continue();
});
await page.goto('http://localhost:8000/#/p/cloud-engineering-scenes-edition-lgtm', { waitUntil: 'networkidle0' });
await new Promise((r) => setTimeout(r, 2500));
await page.evaluate(() => [...document.querySelectorAll('.tabs button')].find((x) => x.textContent.includes('Eigenschaften')).click());
await new Promise((r) => setTimeout(r, 300));
await page.evaluate(() => [...document.querySelectorAll('button')].find((x) => x.textContent.includes('Audio aktualisieren')).click());
await new Promise((r) => setTimeout(r, 1200));
const f = resolve(process.env.TEMP, 'dummy_song.wav');
writeFileSync(f, Buffer.alloc(1024));
await (await page.$('.modal input[name="song"]')).uploadFile(f);
await page.evaluate(() => [...document.querySelectorAll('.modal button')].find((x) => x.textContent.includes('Aktualisieren')).click());
await new Promise((r) => setTimeout(r, 1500));
const errText = await page.evaluate(() => document.querySelector('.modal .err')?.textContent ?? null);
const modalOpen = await page.evaluate(() => !!document.querySelector('.modal'));
console.log(JSON.stringify({ request: seen, dialogError: errText, modalStillOpen: modalOpen, pageErrors: errors }));
await b.close();
