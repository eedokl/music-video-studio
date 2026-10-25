// Renders a studio project frame by frame in headless Chrome and encodes an MP4 with ffmpeg.
// The page is the very same preview the editor shows (render mode), so preview and export match.
//
//   node render.mjs --url "http://127.0.0.1:8000/?render=1&project=ID" --audio path/to/mix.wav --out out.mp4
//   options: --fps 30 --width 1920 --height 1080 --crf 22 --from 0 --to 30 --browser "C:\path\chrome.exe"

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import ffmpegPath from 'ffmpeg-static';
import { launch } from './chrome.mjs';

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
if (!args.url || !args.audio || !args.out) throw new Error('need --url, --audio and --out');
const fps = Number(args.fps ?? 30);
const crf = String(args.crf ?? 22);
const width = Number(args.width ?? 1920);
const height = Number(args.height ?? 1080);
const out = resolve(args.out);

mkdirSync(dirname(out), { recursive: true });

const browser = await launch(['--hide-scrollbars', `--window-size=${width},${height}`], args.browser);
const page = await browser.newPage();
await page.setViewport({ width, height, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('page error:', e.message));
page.on('console', (m) => m.type() === 'error' && console.error('console:', m.text()));
await page.goto(args.url, { waitUntil: 'networkidle0', timeout: 120000 });
await page.waitForFunction('window.__ready === true', { timeout: 180000 });

const duration = await page.evaluate(() => window.__duration);
const from = Number(args.from ?? 0);
const to = Math.min(Number(args.to ?? duration), duration);
const frames = Math.round((to - from) * fps);
console.log(`Rendering ${frames} frames (${from}s–${to}s) at ${width}x${height}@${fps} → ${out}`);

const ff = spawn(
  ffmpegPath,
  [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-ss', String(from), '-t', String(to - from), '-i', resolve(args.audio),
    '-map', '0:v', '-map', '1:a',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', crf, '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
    out,
  ],
  { stdio: ['pipe', 'inherit', 'inherit'] },
);
const ffDone = new Promise((res, rej) => ff.on('close', (c) => (c === 0 ? res() : rej(new Error(`ffmpeg exit ${c}`)))));
const write = (buf) => new Promise((res) => (ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res)));

const dt = 1 / fps;
for (let t = Math.max(0, from - 2); t < from; t += dt) await page.evaluate((t) => window.__renderFrame(t), t);
for (let i = 0; i < frames; i++) {
  await page.evaluate((t) => window.__renderFrame(t), from + i * dt);
  await write(await page.screenshot({ type: 'jpeg', quality: 92, optimizeForSpeed: true }));
  if (i % fps === 0 || i === frames - 1) console.log(`frame ${i + 1}/${frames}`);
}
ff.stdin.end();
await ffDone;
await browser.close();
console.log(`Done: ${out}`);
