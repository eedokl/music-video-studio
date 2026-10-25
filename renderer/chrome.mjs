// Shared headless-Chrome launcher for all render scripts (Windows desktop and Linux/Docker).
//   Windows: Chrome for Testing headless shell in a SHORT path (MAX_PATH), installed with
//     npx @puppeteer/browsers install chrome-headless-shell@stable --path %TEMP%/mvchrome
//   Linux/Docker: STUDIO_CHROME points at the headless shell; WebGL runs on SwiftShader (CPU).
import { existsSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const win = process.platform === 'win32';

function localShell() {
  const base = resolve(process.env.TEMP ?? '/tmp', 'mvchrome/chrome-headless-shell');
  if (!existsSync(base)) return [];
  const sub = win ? 'chrome-headless-shell-win64/chrome-headless-shell.exe' : 'chrome-headless-shell-linux64/chrome-headless-shell';
  return readdirSync(base).map((v) => resolve(base, v, sub));
}

export function chromePath(explicit) {
  return [
    explicit,
    process.env.STUDIO_CHROME,
    ...localShell(),
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].find((p) => p && existsSync(p));
}

// GPU flags: Direct3D on Windows; elsewhere software WebGL (containers have no GPU).
const gpuArgs = win
  ? ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist']
  : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox', '--disable-dev-shm-usage'];

export async function launch(extraArgs = [], explicit) {
  const executablePath = chromePath(explicit);
  if (!executablePath) throw new Error('No Chrome found – install chrome-headless-shell (see renderer/chrome.mjs) or set STUDIO_CHROME');
  return puppeteer.launch({ executablePath, headless: 'shell', args: [...gpuArgs, ...extraArgs] });
}
