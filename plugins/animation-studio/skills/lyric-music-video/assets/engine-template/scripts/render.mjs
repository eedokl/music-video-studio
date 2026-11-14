// Renders the music video frame by frame in headless Edge/Chrome and encodes an MP4 with ffmpeg.
//
//   npm run render                         -> out/music-video.mp4 (1080p30)
//   npm run render -- --from 20 --to 30    -> 10 s test clip
//   options: --crf 18 --fps 30 --width 1920 --height 1080 --out file.mp4 --browser "C:\path\to\chrome.exe"

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import ffmpegPath from 'ffmpeg-static';
import puppeteer from 'puppeteer-core';
import { createServer } from 'vite';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const fps = Number(args.fps ?? 30);
const crf = String(args.crf ?? 18); // 18 = full quality (large), 28 = about 4x smaller, looks the same
const width = Number(args.width ?? 1920);
const height = Number(args.height ?? 1080);
const out = resolve(root, args.out ?? 'out/music-video.mp4');

// machine config of the animation-studio plugin (no machine paths in this file)
const machine = (() => {
  const f = process.env.ANIMATION_STUDIO_CONFIG ?? resolve(homedir(), '.animation-studio', 'config.json');
  try {
    return JSON.parse(readFileSync(f, 'utf8'));
  } catch {
    return {};
  }
})();
// A Chrome for Testing build in a SHORT path works best on Windows:
//   npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome
const localShell = () =>
  [resolve(process.env.TEMP ?? '/tmp', 'mvchrome/chrome-headless-shell'), resolve(homedir(), '.cache/puppeteer/chrome-headless-shell')]
    .filter((base) => existsSync(base))
    .flatMap((base) => readdirSync(base).flatMap((v) =>
    ['chrome-headless-shell-win64/chrome-headless-shell.exe', 'chrome-headless-shell-linux64/chrome-headless-shell',
      'chrome-headless-shell-mac-x64/chrome-headless-shell', 'chrome-headless-shell-mac-arm64/chrome-headless-shell']
      .map((p) => resolve(base, v, p))));
const browserPath = [args.browser, process.env.CHROME, machine.chrome, ...localShell()].find((p) => p && existsSync(p));
const ffmpegBin = [process.env.FFMPEG, machine.ffmpeg].find((p) => p && existsSync(p)) ?? ffmpegPath;
if (!browserPath) throw new Error('No Chrome/Edge found: install chrome-headless-shell (see above), pass --browser <path> or set CHROME');

mkdirSync(dirname(out), { recursive: true });

const server = await createServer({ root, logLevel: 'warn', server: { port: 5199, strictPort: false } });
await server.listen();
const url = `${server.resolvedUrls.local[0]}?render=1${args.query ? `&${args.query}` : ""}`;

const browser = await puppeteer.launch({
  executablePath: browserPath,
  // 'shell' (old headless) only exists in chrome-headless-shell; a full Chrome/Edge exits at once with it
  headless: /headless-shell/i.test(browserPath) ? 'shell' : true,
  args: ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars', `--window-size=${width},${height}`],
});
const page = await browser.newPage();
await page.setViewport({ width, height, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('page error:', e.message));
await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });
await page.waitForFunction('window.__ready === true', { timeout: 180000 });

const gpu = await page.evaluate(() => {
  const gl = document.createElement('canvas').getContext('webgl2');
  const ext = gl?.getExtension('WEBGL_debug_renderer_info');
  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
});
const duration = await page.evaluate(() => window.__duration);
const from = Number(args.from ?? 0);
const to = Math.min(Number(args.to ?? duration), duration);
const frames = Math.round((to - from) * fps);
console.log(`GPU: ${gpu}\nRendering ${frames} frames (${from}s–${to}s) at ${width}x${height}@${fps} → ${out}`);

const ff = spawn(
  ffmpegBin,
  [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-ss', String(from), '-t', String(to - from), '-i', resolve(root, 'public/song.wav'),
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
// Warm up a few seconds before the start so smoothing and camera are settled.
for (let t = Math.max(0, from - 4); t < from; t += dt) await page.evaluate((t, dt) => window.__renderFrame(t, dt), t, dt);

const t0 = Date.now();
for (let i = 0; i < frames; i++) {
  await page.evaluate((t, dt) => window.__renderFrame(t, dt), from + i * dt, dt);
  const img = await page.screenshot({ type: 'jpeg', quality: 92, optimizeForSpeed: true });
  await write(img);
  if (i % (fps * 5) === 0 || i === frames - 1) {
    const per = (Date.now() - t0) / (i + 1);
    const eta = Math.round((per * (frames - i - 1)) / 1000);
    console.log(`frame ${i + 1}/${frames}  (${(from + i * dt).toFixed(1)}s)  ~${Math.floor(eta / 60)}m${eta % 60}s left`);
  }
}
ff.stdin.end();
await ffDone;
await browser.close();
await server.close();
console.log(`Done: ${out}`);
