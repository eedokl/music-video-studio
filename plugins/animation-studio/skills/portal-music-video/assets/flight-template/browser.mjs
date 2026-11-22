// Shared by render.mjs and check.mjs: the static server, the headless browser and the page in frame-exact mode.
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

export const root = dirname(fileURLToPath(import.meta.url));

/** --name value pairs; a flag without a value is true */
export const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith('--') ? [...acc, [a.slice(2), all[i + 1] === undefined || all[i + 1].startsWith('--') ? true : all[i + 1]]] : acc), []),
);

// machine config of the animation-studio plugin (no machine paths in this file)
const machine = (() => {
  try {
    return JSON.parse(readFileSync(process.env.ANIMATION_STUDIO_CONFIG ?? resolve(homedir(), '.animation-studio', 'config.json'), 'utf8'));
  } catch {
    return {};
  }
})();
export const browserPath = [args.browser, process.env.ANIMATION_STUDIO_CHROME, machine.chrome, machine.browser].find((p) => typeof p === 'string' && existsSync(p));
export const ffmpeg = [args.ffmpeg, process.env.FFMPEG, machine.ffmpeg].find((p) => typeof p === 'string' && existsSync(p)) ?? 'ffmpeg';

/** Starts serve.mjs on a free-ish port; returns { port, stop }. */
export async function serve(port = 5246 + Math.floor(Math.random() * 400)) {
  const child = spawn(process.execPath, [resolve(root, 'serve.mjs'), String(port)], { stdio: 'ignore' });
  process.on('exit', () => child.kill());
  await new Promise((r) => setTimeout(r, 700));
  return { port, stop: () => child.kill() };
}

// On the CPU the pictures are drawn by the browser's software renderer (SwiftShader), not by the graphics card.
const GL = (cpu) => (cpu
  ? ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-compositing', '--ignore-gpu-blocklist']
  : ['--enable-gpu', '--ignore-gpu-blocklist']);

/**
 * Opens the flight in frame-exact mode (window.__renderFrame(t), window.__duration, window.__worlds).
 * A page error while it loads rejects at once (a typo in a world must not wait for the timeout).
 * Returns { browser, page, renderer } - renderer = the name of what really draws.
 */
export async function open(port, { width = 1920, height = 1080, cpu = false } = {}) {
  if (!browserPath) throw new Error('no Chrome/Edge found: pass --browser <path>, set ANIMATION_STUDIO_CHROME or the plugin config "chrome" / "browser"');
  const browser = await puppeteer.launch({ executablePath: browserPath, headless: /headless-shell/i.test(browserPath) ? 'shell' : true, args: [...GL(cpu), '--hide-scrollbars', `--window-size=${width},${height}`], protocolTimeout: 900000 });
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  let loading = true;
  const errors = [];
  const failed = new Promise((_, rej) =>
    page.on('pageerror', (e) => {
      errors.push(e.message);
      if (loading) rej(new Error(`the page failed to load: ${e.message}`));
    }),
  );
  failed.catch(() => {});
  try {
    await Promise.race([page.goto(`http://127.0.0.1:${port}/?render=1`, { waitUntil: 'load', timeout: 600000 }), failed]);
    await Promise.race([page.waitForFunction('window.__ready === true', { timeout: 900000 }), failed]);
  } catch (e) {
    await browser.close();
    throw e;
  }
  loading = false;
  const renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
  });
  if (cpu && !/swiftshader|llvmpipe|software/i.test(renderer)) {
    await browser.close();
    throw new Error(`asked for the CPU, but the browser draws with "${renderer}"`);
  }
  return { browser, page, renderer, errors };
}
