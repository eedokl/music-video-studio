// Effect catalogue from the installed Shaders library -> <out>/catalog.json + <out>/shaders-catalog.md
// Usage: node make_catalog.mjs <shaders-dir (holds node_modules/shaders)> <out-dir>
// (or: shaders_render.py catalog --out <dir>, which finds the package for you)
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [dir, out] = [path.resolve(process.argv[2] || '.'), path.resolve(process.argv[3] || '.')];
const pkg = path.join(dir, 'node_modules', 'shaders');
const version = JSON.parse(readFileSync(path.join(pkg, 'package.json'), 'utf8')).version;
const { getAllShaders } = await import(pathToFileURL(path.join(pkg, 'dist', 'registry.js')).href);
mkdirSync(out, { recursive: true });

// Rating for classical 2D cartoon films (our choice; see references/shaders.md)
const FILM = {
  '***': ['Paper', 'FilmGrain', 'FilmStock', 'Vignette', 'Halation', 'IrisWipe', 'Godrays', 'Watercolor', 'Glow',
          'LightLeak', 'DropShadow', 'BokehBlur', 'TiltShift', 'Fog', 'VolumetricFog', 'Sparkle'],
  '**': ['Halftone', 'Engraving', 'Crosshatch', 'Posterize', 'GradientMap', 'Duotone', 'Tritone', 'Exposure',
         'BrightnessContrast', 'Saturation', 'Vibrance', 'Tint', 'Blur', 'ZoomBlur', 'LinearBlur', 'ProgressiveBlur',
         'ChromaticAberration', 'Scratches', 'PagePeel', 'RadialWipe', 'LinearWipe', 'BarnDoors', 'GradientWipe',
         'NoiseDissolve', 'DiamondWipe', 'Ripples', 'WaveDistortion', 'Water', 'Smoke', 'CloudField', 'StarField',
         'FloatingParticles', 'ParticleField', 'Chalkboard', 'InnerGlow', 'Outline', 'LensFlare', 'DisplacementMap'],
};
const rating = (n) => Object.entries(FILM).find(([, l]) => l.includes(n))?.[0] ?? '';

const rows = getAllShaders().map((s) => {
  const def = s.definition ?? s;
  const props = Object.entries(def.props ?? {}).map(([k, v]) => ({
    name: k, default: v.default, min: v.ui?.min, max: v.ui?.max, desc: v.description ?? '',
  }));
  const name = def.name ?? s.name;
  return { name, category: def.category ?? s.category ?? '', role: def.role ?? '',
           description: def.description ?? s.description ?? '', props, film: rating(name) };
});
writeFileSync(path.join(out, 'catalog.json'), JSON.stringify(rows, null, 1));

const fmt = (v) => (v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v));
const cell = (t) => String(t).replace(/\|/g, '/').replace(/\n/g, ' ');
let md = `# Shaders – effect catalogue\n\nGenerated from \`shaders\` ${version} (${rows.length} effects). ` +
  `*** = fits classical 2D cartoon films very well, ** = usable.\n` +
  `Role: *generator* makes a picture (pattern, colour, texture), *filter* changes what lies below it.\n\n`;
md += `## Best fits (***)\n\n| Effect | Category | What it does | Props (default) |\n|---|---|---|---|\n`;
for (const r of rows.filter((r) => r.film === '***')) {
  md += `| **${r.name}** | ${r.category} | ${cell(r.description)} | ${r.props.map((p) => `${p.name}=${fmt(p.default)}`).join(', ')} |\n`;
}
const byCat = {};
for (const r of rows) (byCat[r.category || 'Other'] ??= []).push(r);
md += `\n## All effects by category\n`;
for (const cat of Object.keys(byCat).sort()) {
  md += `\n### ${cat} (${byCat[cat].length})\n\n| | Effect | Role | What it does |\n|---|---|---|---|\n`;
  for (const r of byCat[cat].sort((a, b) => a.name.localeCompare(b.name))) {
    md += `| ${r.film} | ${r.name} | ${r.role} | ${cell(r.description)} |\n`;
  }
}
md += `\n## Props in detail (*** and **)\n`;
for (const r of rows.filter((r) => r.film)) {
  md += `\n**${r.name}** ${r.film} – ${r.description}\n\n`;
  for (const p of r.props) {
    const range = p.min !== undefined ? ` (${p.min}…${p.max})` : '';
    md += `- \`${p.name}\` = ${fmt(p.default)}${range}: ${cell(p.desc)}\n`;
  }
}
writeFileSync(path.join(out, 'shaders-catalog.md'), md);
console.log(`shaders ${version}: ${rows.length} effects in ${Object.keys(byCat).length} categories, ` +
  `***: ${rows.filter((r) => r.film === '***').length}, **: ${rows.filter((r) => r.film === '**').length} -> ${out}`);
