// Render frames of a studio project's preview page at given times: node frames.mjs <projectId> <outPrefix> t1 t2 ...
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { launch } from './chrome.mjs';
const [pid, prefix, ...ts] = process.argv.slice(2);
mkdirSync(dirname(resolve(prefix)), { recursive: true });
const b = await launch();
const pg = await b.newPage();
await pg.setViewport({ width: 960, height: 540 });
pg.on('pageerror', (e) => console.error('page error', e.message));
await pg.goto(`http://127.0.0.1:8000/?render=1&project=${pid}`, { waitUntil: 'networkidle0' });
await pg.waitForFunction('window.__ready === true', { timeout: 60000 });
for (const [k, t] of ts.entries()) {
  const tt = Number(t);
  for (let w = Math.max(0, tt - 1.5); w < tt; w += 1 / 15) await pg.evaluate((x) => window.__renderFrame(x), w); // settle
  await pg.evaluate((x) => window.__renderFrame(x), tt);
  await pg.screenshot({ path: `${prefix}${String(k).padStart(2, '0')}.png` });
}
await b.close();
console.log('ok', ts.length);
