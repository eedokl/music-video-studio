// Multiplane server: serves scene files + the renderer pages and stores rendered frames.
// Usage: node server.mjs <scene-folder> <output-folder> <port>
//   /_mp/...         -> files of this folder (multiplane.html, comic25d.html, vendor/three)
//   /...             -> files of the scene folder
//   POST /save/x.png -> <output-folder>/x.png
//   POST /log        -> text on stdout (messages and errors of the page)
//   GET  /done       -> the server exits (rendering finished)
import http from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const [ROOT, OUT, PORT] = [path.resolve(process.argv[2]), path.resolve(process.argv[3]), Number(process.argv[4] || 8766)];
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.json': 'application/json' };
await mkdir(OUT, { recursive: true });

async function body(req) {
  const chunks = [];
  for await (const c of req) chunks.push(c);
  return Buffer.concat(chunks);
}

const server = http.createServer(async (req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  try {
    if (req.method === 'POST' && url.startsWith('/save/')) {
      const name = path.basename(url);
      if (!/^[\w.-]+\.png$/.test(name)) throw new Error('bad name');
      await writeFile(path.join(OUT, name), await body(req));
      res.writeHead(200); res.end('ok'); return;
    }
    if (req.method === 'POST' && url === '/log') {
      console.log('[page]', (await body(req)).toString());
      res.writeHead(200); res.end('ok'); return;
    }
    if (url === '/done') {
      res.writeHead(200); res.end('bye');
      console.log('done');
      setTimeout(() => process.exit(0), 200);
      return;
    }
    const base = url.startsWith('/_mp/') ? HERE : ROOT;
    const rel = url.startsWith('/_mp/') ? url.slice(5) : url.slice(1);
    const file = path.resolve(base, rel);
    if (!file.startsWith(base)) throw new Error('outside root');
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream' });
    res.end(data);
  } catch (e) {
    res.writeHead(404); res.end(String(e.message));
  }
});
server.listen(PORT, '127.0.0.1', () => console.log(`ready: http://127.0.0.1:${PORT}/`));
