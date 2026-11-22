// Renders the flight frame by frame in a headless browser and encodes an MP4 with the song (x264).
//
//   node render.mjs                         -> out/flight.mp4 (1920x1080, 30 fps, whole song)
//   node render.mjs --from 150 --to 156     -> a piece (out/flight_150-156.mp4)
//   options: --out name.mp4 --fps 30 --width 1920 --height 1080 --crf 18 --workers 4 --seg 8
//            --cpu    draw with the browser's software renderer: the graphics card stays free (slower)
//            --fresh  render every segment again
//
// The film is cut into segments of --seg seconds; every worker is a browser of its own and takes the next free
// segment (a frame depends only on its time, so the order does not matter). Finished segments stay in
// out/segments/<size>_<fps>/ and are reused: an interrupted render continues where it stopped. After a change to
// the film pass --fresh (flight.py does it when a source file is newer than the segments).
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { args, ffmpeg, open, root, serve } from './browser.mjs';

const fps = Number(args.fps ?? 30), width = Number(args.width ?? 1920), height = Number(args.height ?? 1080);
const crf = String(args.crf ?? 18), segLen = Number(args.seg ?? 8), workers = Number(args.workers ?? 4), cpu = !!args.cpu;

const server = await serve();
let first;
try {
  first = await open(server.port, { width, height, cpu });
} catch (e) {
  console.error(`render stopped: ${e.message}`);
  server.stop();
  process.exit(3);
}
const duration = await first.page.evaluate(() => window.__duration);
console.log(`renderer: ${first.renderer}`);

const from = Number(args.from ?? 0), to = Math.min(Number(args.to ?? duration), duration);
const whole = args.from === undefined && args.to === undefined;
const segDir = resolve(root, 'out', 'segments', `${width}x${height}_${fps}`);
if (args.fresh) rmSync(segDir, { recursive: true, force: true });
mkdirSync(segDir, { recursive: true });
for (const f of readdirSync(segDir)) if (f.endsWith('.part.mp4')) rmSync(resolve(segDir, f));
const name = (a, b) => resolve(segDir, `seg_${String(Math.round(a * 100)).padStart(6, '0')}_${String(Math.round(b * 100)).padStart(6, '0')}.mp4`);
const segments = [];
for (let a = Math.floor(from / segLen) * segLen; a < to; a += segLen) segments.push({ a: Math.max(a, from), b: Math.min(a + segLen, to), file: name(Math.max(a, from), Math.min(a + segLen, to)) });
const todo = segments.filter((s) => !existsSync(s.file));
const totalFrames = todo.reduce((n, s) => n + Math.round((s.b - s.a) * fps), 0);
console.log(`${segments.length} segments, ${todo.length} to render (${totalFrames} frames at ${width}x${height}@${fps}), ${Math.min(workers, Math.max(1, todo.length))} browsers${cpu ? ', CPU only' : ''}`);

let done = 0;
const t0 = Date.now();
const renderSegment = async (page, s) => {
  const n = Math.round((s.b - s.a) * fps);
  const tmp = s.file.replace(/\.mp4$/, '.part.mp4');
  const ff = spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p', '-r', String(fps), tmp], { stdio: ['pipe', 'inherit', 'inherit'] });
  const closed = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exit ${c}`)))));
  for (let i = 0; i < n; i++) {
    await page.evaluate((t) => window.__renderFrame(t), s.a + i / fps);
    const img = await page.screenshot({ type: 'jpeg', quality: 95, optimizeForSpeed: true });
    if (!ff.stdin.write(img)) await new Promise((r) => ff.stdin.once('drain', r));
    done++;
    if (done % (fps * 4) === 0 || done === totalFrames) {
      const per = (Date.now() - t0) / done, left = Math.round((per * (totalFrames - done)) / 1000);
      console.log(`${done}/${totalFrames} frames  ${(per / 1000).toFixed(2)} s per frame  about ${Math.floor(left / 3600)}h ${Math.floor((left % 3600) / 60)}m left`);
    }
  }
  ff.stdin.end();
  await closed;
  renameSync(tmp, s.file);
};
const queue = [...todo];
const work = async (ctx) => {
  const { browser, page } = ctx ?? (await open(server.port, { width, height, cpu }));
  for (let s = queue.shift(); s; s = queue.shift()) await renderSegment(page, s);
  await browser.close();
};
try {
  await Promise.all([work(first), ...Array.from({ length: Math.max(0, Math.min(workers, todo.length) - 1) }, () => work())]);
} catch (e) {
  console.error(`render stopped: ${e.message}`);
  server.stop();
  process.exit(1);
}
if (first.errors.length) console.error(`page errors while rendering:\n  ${[...new Set(first.errors)].join('\n  ')}`);

// join the segments and lay the song under them
const list = resolve(segDir, `list_${Math.round(from * 100)}_${Math.round(to * 100)}.txt`);
writeFileSync(list, segments.map((s) => `file '${s.file.replace(/\\/g, '/')}'`).join('\n'));
const out = resolve(root, 'out', typeof args.out === 'string' ? args.out : whole ? 'flight.mp4' : `flight_${from}-${to}.mp4`);
await new Promise((res, rej) =>
  spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-ss', String(from), '-t', String(to - from), '-i', resolve(root, 'public/song.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], { stdio: 'inherit' }).on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exit ${c}`)))),
);
console.log(`done in ${Math.round((Date.now() - t0) / 60000)} min: ${out}`);
server.stop();
process.exit(first.errors.length ? 4 : 0);
