// Bundle an imported video engine (projects/<id>/legacy/src) into legacy/app.js + app.css.
//   node tools/legacy-build.mjs projects/<id>
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const studio = resolve(import.meta.dirname, '..');
const frontend = resolve(studio, 'frontend');
const require = createRequire(resolve(frontend, 'package.json'));
const esbuild = require('esbuild');
const dir = resolve(process.argv[2]);

const res = await esbuild.build({
  entryPoints: [resolve(dir, 'legacy/src/studio_main.ts')],
  outfile: resolve(dir, 'legacy/app.js'),
  bundle: true,
  format: 'esm',
  target: 'es2022',
  loader: { '.json': 'json', '.png': 'file', '.jpg': 'file', '.svg': 'file', '.webp': 'file' },
  alias: { '@studio': resolve(frontend, 'src') },
  nodePaths: [resolve(frontend, 'node_modules')],
  define: { 'import.meta.env.BASE_URL': '"./"', 'import.meta.env.DEV': 'false' },
  logLevel: 'warning',
  metafile: true,
});
console.log(`built ${Object.keys(res.metafile.outputs).map((o) => o.split('/').pop()).join(', ')}`);
