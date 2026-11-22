// Checks a flight without rendering it: every portal crossing, the time a picture takes, and a look at every world.
//
//   node check.mjs [--cpu] [--width 1280 --height 720] [--fps 30]   -> out/check/check.json + one picture per world
//
// crossings: the picture change across a portal (the frame before and the frame after) against the change between
//            ordinary neighbours right before and after it. A crossing is seamless when it does not stand out.
// frames:    the film is drawn once at --fps; frames slower than 14 ms are counted (a hitch that repeats at the
//            same place is a shader or a texture that is made while the film plays). Not with --cpu: the software
//            renderer is slow in every frame, and drawing the whole film with it takes as long as a render.
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { args, open, root, serve } from './browser.mjs';

const width = Number(args.width ?? 1280), height = Number(args.height ?? 720), fps = Number(args.fps ?? 30), cpu = !!args.cpu;
const outDir = resolve(root, 'out', 'check');
mkdirSync(outDir, { recursive: true });
const server = await serve();
let ctx;
try {
  ctx = await open(server.port, { width, height, cpu });
} catch (e) {
  console.error(`check stopped: ${e.message}`);
  server.stop();
  process.exit(3);
}
const { page } = ctx;
const report = await page.evaluate(async (fps, timed) => {
  const e = window.__engine, gl = e.renderer.getContext();
  const c = document.createElement('canvas');
  c.width = 320, c.height = 180;
  const g = c.getContext('2d', { willReadFrequently: true });
  const grab = (t) => {
    e.frame(t);
    g.drawImage(e.canvas, 0, 0, 320, 180);
    return g.getImageData(0, 0, 320, 180).data.slice();
  };
  const diff = (a, b) => {
    let s = 0;
    for (let i = 0; i < a.length; i += 4) s += Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
    return +(s / ((a.length / 4) * 3)).toFixed(1);
  };
  const h = 1 / 60;
  const worlds = e.worlds.map((w, i) => {
    const x = w.start + w.D, last = i === e.worlds.length - 1;
    const before = diff(grab(x - 3 * h), grab(x - h)), across = diff(grab(x - h), grab(x + h)), after = diff(grab(x + h), grab(x + 3 * h));
    return { id: w.mod.id, start: +w.start.toFixed(3), seconds: +w.D.toFixed(3), before, across, after, last, seam: !last && across > 1.6 * Math.max(before, after) + 2 };
  });
  if (!timed) return { total: +e.total.toFixed(3), worlds, frames: null };
  const px = new Uint8Array(4), slow = [];
  let n = 0, sum = 0, max = 0;
  for (let t = 0; t < e.total; t += 1 / fps) {
    const t0 = performance.now();
    const info = e.frame(t);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
    const ms = performance.now() - t0;
    n++, (sum += ms), (max = Math.max(max, ms));
    if (ms > 14) slow.push([+t.toFixed(2), info.world, Math.round(ms)]);
  }
  return { total: +e.total.toFixed(3), worlds, frames: { count: n, meanMs: +(sum / n).toFixed(2), maxMs: Math.round(max), slow } };
}, fps, !cpu);
// one picture from the middle of every world
for (const [i, w] of report.worlds.entries()) {
  await page.evaluate((t) => window.__renderFrame(t), w.start + w.seconds / 2);
  w.picture = `world_${String(i + 1).padStart(2, '0')}_${w.id}.jpg`;
  await page.screenshot({ type: 'jpeg', quality: 88, path: resolve(outDir, w.picture) });
}
report.renderer = ctx.renderer;
report.pageErrors = [...new Set(ctx.errors)];
writeFileSync(resolve(outDir, 'check.json'), JSON.stringify(report, null, 1));
await ctx.browser.close();
server.stop();
console.log(JSON.stringify(report));
process.exit(0);
