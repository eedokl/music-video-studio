// Code cut (film-finish): the film as a page. drawFrame(ctx, k) is the only entry point; everything depends on the
// frame number k and on data (edit.json, song.json, clips.json, facts.json) - no clocks, no unseeded random.
// Layout is designed for 1280x720 and scaled to edit.size (16:9).
const W = 1280, H = 720;
let TOP = 34, BOT = 40;
const SUNG = '700 48px Bahnschrift, "Arial Narrow", Arial, sans-serif';
const HEAD = (px) => `700 ${px}px Bahnschrift, "Arial Narrow", Arial, sans-serif`;
const MONO = (px, w = 400) => `${w} ${px}px Consolas, "Courier New", monospace`;
const ROW = 52, LYR_X = 48, LYR_MAXW = 1000;

const ease = { linear: (u) => u, smooth: (u) => u * u * (3 - 2 * u), out: (u) => 1 - (1 - u) * (1 - u) };
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const rnd = (n) => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const pad = (n, w, c = '0') => String(n).padStart(w, c);
const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

export function makeDraw({ edit, song, facts, clips, plate }) {
  const S = (edit.size?.[0] ?? W) / W;                     // output scale
  const ch = edit.chrome || {};                            // bars, meter, clock, label, frames, ticker_speed
  if (ch.bars === false) { TOP = 0; BOT = 0; }
  const CLAY = '#D97757';
  const NEUTRAL = { grade: { contrast: 1, saturate: 1, brightness: 1 }, accent: CLAY, pulse: 1 };
  const cache = new Map();
  function image(url) {
    if (!cache.has(url)) {
      const im = new Image();
      im.src = url;
      cache.set(url, im.decode().then(() => im));
      if (cache.size > 80) cache.delete(cache.keys().next().value);
    }
    return cache.get(url);
  }
  const off = new OffscreenCanvas(Math.round(W * S), Math.round(H * S));
  const octx = off.getContext('2d');
  const back = new OffscreenCanvas(Math.round(W * S), Math.round(H * S));   // pieces that pass behind people (masks/)
  const bctx = back.getContext('2d');
  const measure = new OffscreenCanvas(8, 8).getContext('2d');
  const parts = edit.shots.flatMap((s) => s.parts.map((p) => ({ ...p, shot: s })));
  const world = (name) => ({ ...NEUTRAL, ...((edit.worlds || {})[name] || {}) });

  // ---- lyric layout (once per line): greedy rows, pages of two rows -----------------------------------------
  measure.font = SUNG;
  const layout = song.lines.map((line) => {
    const rows = [[]];
    let x = 0;
    for (const w of line.words) {
      const txt = w.w.replace(/["„“]/g, '');
      const tw = measure.measureText(txt + ' ').width;
      if (x + tw > LYR_MAXW && rows[rows.length - 1].length) { rows.push([]); x = 0; }
      rows[rows.length - 1].push({ ...w, txt, x });
      x += tw;
    }
    const pages = [];
    for (let i = 0; i < rows.length; i += 2) pages.push(rows.slice(i, i + 2));
    return pages;
  });
  function lineAt(k) {
    for (let i = 0; i < song.lines.length; i++) {
      const l = song.lines[i], next = song.lines[i + 1];
      const end = Math.min(l.k1 + 12, next ? next.k0 - 2 : 1e9);
      if (k >= l.k0 - 2 && k < end) return i;
    }
    return -1;
  }

  // ---- sources ----------------------------------------------------------------------------------------------
  function takeIndex(part, k) {            // placement rule of the plugin (clips.frame_index): by song time, never stretched
    const c = clips[part.src];
    const t = song.t0 + k / edit.fps;
    return clamp(Math.floor((t - c.song_start) * c.fps + 1e-6) - (c.delay_frames || 0), 0, c.frames - 1);
  }
  const framing = new Map();
  function faceFraming(part) {             // rule: her face sits in the upper half, so the lyric block stays clear of her mouth
    if (framing.has(part)) return framing.get(part);
    let f = null;
    const c = clips[part.src];
    if (part.kind === 'take' && c?.faces && part.cam?.face !== false) {
      const boxes = [];
      for (let k = part.k0; k < part.k1; k += 2) { const b = c.faces[takeIndex(part, k)]; if (b) boxes.push(b); }
      if (boxes.length > 3) {
        const med = (j) => boxes.map((b) => b[j]).sort((a, b) => a - b)[Math.floor(boxes.length / 2)];
        f = { x: med(0) + med(2) / 2, y: med(1) + med(3) / 2, w: med(2), h: med(3) };
      }
    }
    framing.set(part, f);
    return f;
  }
  function drawSource(im, part, u) {
    const g = geometry(part, u, im.naturalWidth, im.naturalHeight);
    octx.drawImage(im, g.x, g.y, g.dw, g.dh);
    return g;
  }
  function geometry(part, u, iw, ih) {     // cover fit, zoom z; centre from cam.c or from the face rule
    const im = { naturalWidth: iw, naturalHeight: ih };
    const cam = part.cam || {};
    const e = ease[cam.ease || 'smooth'](u);
    const z0 = cam.z?.[0] ?? 1, z1 = cam.z?.[1] ?? z0;
    const z = z0 + (z1 - z0) * e;
    const s = Math.max(W / im.naturalWidth, H / im.naturalHeight) * z;
    const dw = im.naturalWidth * s, dh = im.naturalHeight * s;
    let x, y;
    const f = cam.c ? null : faceFraming(part);
    if (f) {
      x = W * (cam.fx ?? 0.5) - f.x * dw;
      y = H * (cam.fy ?? 0.37) - f.y * dh;
    } else {
      const c0 = cam.c ?? [0.5, 0.5], c1 = cam.c1 ?? c0;
      x = W / 2 - (c0[0] + (c1[0] - c0[0]) * e) * dw;
      y = H / 2 - (c0[1] + (c1[1] - c0[1]) * e) * dh;
    }
    x = clamp(x, W - dw, 0); y = clamp(y, H - dh, 0);
    return { x, y, dw, dh };
  }
  const topCache = new Map();
  function lyricTop(part, li, iw, ih) {    // decided once per part and line, so the words never jump inside a part
    const key = part.k0 + ':' + li;
    if (topCache.has(key)) return topCache.get(key);
    const c = clips[part.src], rows = layout[li][0].length;
    let hit = 0, n = 0;
    for (let k = part.k0; k < part.k1; k += 3) {
      const b = c?.faces?.[takeIndex(part, k)];
      if (!b) continue;
      const g = geometry(part, (k - part.k0) / Math.max(1, part.k1 - part.k0 - 1), iw, ih);
      const mouth = g.y + (b[1] + b[3] * 0.9) * g.dh, left = g.x + b[0] * g.dw;
      n++;
      if (mouth > H - BOT - 50 - rows * ROW && left < LYR_X + LYR_MAXW * 0.8) hit++;
    }
    const top = n > 0 && hit / n > 0.25;
    topCache.set(key, top);
    return top;
  }

  // ---- beat --------------------------------------------------------------------------------------------------
  function beatKick(k) {                   // 1 on a kick beat, decaying over 7 frames
    let v = 0;
    for (let i = 0; i < song.beats_k.length; i++) {
      const b = song.beats_k[i];
      if (b > k) break;
      if (k < b + 7 && song.kick[i] > 0.5) v = Math.max(v, (1 - (k - b) / 7) * Math.min(1, song.kick[i]));
    }
    return v;
  }

  // ---- code layer --------------------------------------------------------------------------------------------
  const tickerText = facts.map((f) => `${f.date}  ${f.text.toUpperCase()}`);
  measure.font = MONO(15);
  const tickerW = tickerText.map((s) => measure.measureText(s).width + 16 + 56);
  const tickerLen = tickerW.reduce((a, b) => a + b, 0);

  function clockText(k) {                  // film time runs from this Monday morning into 2031, faster and faster
    const c = ch.clock;
    const u = clamp(k / c.k_end, 0, 1);
    const a = Date.UTC(...c.from), b = Date.UTC(...c.to);
    const d = new Date(a + (b - a) * Math.pow(u, c.power || 3));
    return `${DAYS[d.getUTCDay()]} ${pad(d.getUTCDate(), 2)} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}  `
      + `${pad(d.getUTCHours(), 2)}:${pad(d.getUTCMinutes(), 2)}:${pad(d.getUTCSeconds(), 2)}`;
  }

  function chrome(ctx, k, shot, acc) {
    ctx.shadowColor = 'transparent';
    if (ch.bars === false) return;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, TOP);
    ctx.fillRect(0, H - BOT, W, BOT);
    ctx.textBaseline = 'middle';
    ctx.font = MONO(13);
    ctx.fillStyle = '#e8e8e8';
    const m = ch.meter;                                           // a bar that empties between two frames
    if (m) {
      const left = clamp(1 - (k - m.k0) / (m.k1 - m.k0), 0, 1);
      ctx.textAlign = 'left';
      ctx.fillText(m.title, 20, TOP / 2 + 1);
      const bx = 28 + ctx.measureText(m.title).width;
      ctx.strokeStyle = '#e8e8e8';
      ctx.lineWidth = 1;
      ctx.strokeRect(bx + 0.5, 11.5, 120, 11);
      ctx.fillStyle = left < 0.2 ? acc : '#e8e8e8';
      ctx.fillRect(bx + 2, 13, Math.round(117 * left), 8);
      ctx.fillText(pad(Math.round(left * 100), 3, ' ') + '%', bx + 130, TOP / 2 + 1);
    }
    if (ch.clock) {
      ctx.fillStyle = k >= ch.clock.k_end ? acc : '#e8e8e8';
      ctx.textAlign = 'center';
      ctx.font = MONO(14, 700);
      ctx.fillText(clockText(k), W / 2, TOP / 2 + 1);
    }
    if (ch.label) {
      ctx.font = MONO(13);
      ctx.textAlign = 'right';
      ctx.fillStyle = '#9a9a9a';
      ctx.fillText(ch.label, W - 20, TOP / 2 + 1);
    }
    // scene slug under the bar: scene name and frame number (the frame number is the review handle)
    const slug = [shot.scene, ch.frames === false ? null : `F ${pad(k, 5)}`].filter(Boolean).join('  ·  ');
    ctx.textAlign = 'left';
    ctx.font = MONO(12);
    const sw = ctx.measureText(slug).width + 14;
    if (slug) {
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(20, TOP + 10, sw, 18);
      ctx.fillStyle = '#e8e8e8';
      ctx.fillText(slug, 27, TOP + 20);
    }
    if (!tickerLen) return;
    // ticker: real, dated facts in order, constant speed, looping
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, H - BOT, W, BOT);
    ctx.clip();
    ctx.font = MONO(15);
    let x = W * 0.6 - ((k * (ch.ticker_speed || 3)) % tickerLen);
    for (let loop = 0; loop < 3 && x < W; loop++) {
      for (let i = 0; i < tickerText.length; i++) {
        if (x + tickerW[i] > 0 && x < W) {
          ctx.fillStyle = acc;
          ctx.fillRect(x, H - BOT / 2 - 3, 6, 6);
          ctx.fillStyle = '#e8e8e8';
          ctx.fillText(tickerText[i], x + 16, H - BOT / 2 + 1);
        }
        x += tickerW[i];
      }
    }
    ctx.restore();
  }

  function label(ctx, text, x, y, inv = true) {      // small mono label box, returns width
    ctx.font = MONO(12);
    ctx.textBaseline = 'alphabetic';
    ctx.textAlign = 'left';
    const tw = ctx.measureText(text).width + 10;
    ctx.fillStyle = inv ? '#ffffff' : 'rgba(0,0,0,0.6)';
    ctx.fillRect(x, y - 14, tw, 16);
    ctx.fillStyle = inv ? '#000' : '#fff';
    ctx.fillText(text, x + 5, y - 2);
    return tw;
  }

  function tracker(ctx, part, geo, srcIdx, text) {   // thin box following her face in takes
    const b = clips[part.src]?.faces?.[srcIdx];
    if (!b) return;
    const p = 0.18;
    const x = geo.x + (b[0] - b[2] * p) * geo.dw, y = geo.y + (b[1] - b[3] * p * 1.6) * geo.dh;
    const w = b[2] * (1 + 2 * p) * geo.dw, h = b[3] * (1 + 2.2 * p) * geo.dh;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.strokeRect(Math.round(x) + 0.5, Math.round(y) + 0.5, Math.round(w), Math.round(h));
    label(ctx, text, Math.round(x), Math.max(TOP + 50, Math.round(y) - 4));
  }

  function tag(ctx, part, k) {             // label on a b-roll picture: a corner bracket and what the machine sees
    const t = part.tag;
    if (!t) return;
    const [nx, ny] = t.at || [0.72, 0.3];
    const x = Math.round(nx * W), y = Math.round(ny * H), s = 26;
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const [sx, sy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      ctx.moveTo(x + sx * s + 0.5, y + sy * (s - 8) + 0.5);
      ctx.lineTo(x + sx * s + 0.5, y + sy * s + 0.5);
      ctx.lineTo(x + sx * (s - 8) + 0.5, y + sy * s + 0.5);
    }
    ctx.stroke();
    const n = Math.min(t.text.length, Math.floor((k - part.k0) * 2.5) + 1);
    label(ctx, t.text.slice(0, n), x + s + 6, y - s + 14);
  }

  function lyrics(ctx, k, acc, top) {      // one size, words appear on their onset, one accent word per line
    const li = lineAt(k);
    if (li < 0) return;
    const line = song.lines[li], pages = layout[li];
    if (edit.hide_lyrics?.includes(li)) return;
    let pg = 0;
    for (let i = 0; i < pages.length; i++) if (k >= pages[i][0][0].k0 - 2) pg = i;
    const rows = pages[pg];
    const accent = (edit.accents || {})[String(li)];
    ctx.font = SUNG;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.shadowColor = 'rgba(0,0,0,0.75)';
    ctx.shadowBlur = 10;
    const y0 = top ? TOP + 92 : H - BOT - 50 - (rows.length - 1) * ROW;
    rows.forEach((row, ri) => {
      for (const w of row) {
        if (k < w.k0 - 2) continue;
        ctx.lineWidth = 5;
        ctx.lineJoin = 'round';
        ctx.strokeStyle = 'rgba(0,0,0,0.6)';
        ctx.strokeText(w.txt, LYR_X + w.x, y0 + ri * ROW);
        ctx.fillStyle = accent && w.txt.toLowerCase().replace(/[^a-zäöüß]/g, '') === accent ? acc : '#ffffff';
        ctx.fillText(w.txt, LYR_X + w.x, y0 + ri * ROW);
      }
    });
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    return line;
  }

  function panel(ctx, x, y, w, h, title) {
    ctx.fillStyle = 'rgba(0,0,0,0.62)';
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = 'rgba(255,255,255,0.75)';
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 0.5, y + 0.5, w, h);
    if (title) {
      ctx.font = MONO(12);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.fillStyle = '#d0d0d0';
      ctx.fillText(title, x + 12, y + 21);
    }
  }

  const overlay = {
    shout(ctx, o, k, acc) {                // whole-frame outline word
      const u = (k - o.k0) / (o.k1 - o.k0);
      ctx.save();
      ctx.font = HEAD(o.size || 330);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineWidth = 3;
      ctx.strokeStyle = o.accent ? acc : `rgba(255,255,255,${0.9 - 0.5 * u})`;
      ctx.translate(W / 2, H / 2 + (o.dy || 10));
      ctx.scale(1 + 0.06 * u, 1 + 0.06 * u);
      ctx.strokeText(o.text, 0, 0);
      ctx.restore();
    },
    flash(ctx, o, k) {
      ctx.fillStyle = `rgba(255,255,255,${(o.a || 0.45) * (1 - (k - o.k0) / (o.k1 - o.k0))})`;
      ctx.fillRect(0, 0, W, H);
    },
    title(ctx, o, k, acc) {                // title card: lines, one accent line
      const a = clamp((k - o.k0) / 6, 0, 1) * clamp((o.k1 - k) / 6, 0, 1);
      ctx.save();
      ctx.globalAlpha = a;
      ctx.textAlign = o.align || 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.shadowColor = 'rgba(0,0,0,0.7)';
      ctx.shadowBlur = 12;
      const x = o.align === 'center' ? W / 2 : (o.x ?? 48);
      o.lines.forEach((t, i) => {
        const size = t.size || o.size || 84;
        ctx.font = t.mono ? MONO(size, 700) : HEAD(size);
        ctx.fillStyle = t.accent ? acc : '#fff';
        if (k >= (t.k ?? o.k0)) ctx.fillText(t.text, x, (o.y ?? 330) + (t.dy ?? i * (o.size || 84) * 1.05));
      });
      ctx.restore();
    },
    list(ctx, o, k, acc) {                 // numbered list, each item appears on its word onset
      const x = o.x ?? 800, y = o.y ?? 150, w = o.w ?? 420, h = 44 + o.items.length * 40;
      panel(ctx, x, y, w, h, o.title);
      o.items.forEach((it, i) => {
        if (k < it.k) return;
        const fresh = k - it.k < 6;
        ctx.font = MONO(24, 700);
        ctx.fillStyle = fresh || it.accent ? acc : '#fff';
        const txt = o.numbers === false ? it.text : `${i + 1}  ${it.text}`;
        const su = it.strike === undefined ? 0 : clamp((k - it.strike) / 5, 0, 1);   // struck through from frame `strike`
        if (su > 0 && !fresh) ctx.fillStyle = 'rgba(255,255,255,0.55)';
        ctx.fillText(txt, x + 14, y + 58 + i * 40);
        if (su > 0) {
          ctx.fillStyle = acc;
          ctx.fillRect(x + 14, y + 49 + i * 40, ctx.measureText(txt).width * su, 3);
        }
      });
    },
    board(ctx, o, k, acc) {                // departure board, rows flip in one after another
      const x = o.x ?? 660, y = o.y ?? 110, w = o.w ?? 560, h = 50 + o.rows.length * 34;
      panel(ctx, x, y, w, h, o.title);
      o.rows.forEach((r, i) => {
        const kk = o.k0 + 4 + i * (o.step || 8);
        if (k < kk) return;
        const n = Math.floor((k - kk) * 3);
        ctx.font = MONO(20, 700);
        ctx.fillStyle = '#fff';
        ctx.fillText(r[0].slice(0, n), x + 14, y + 60 + i * 34);
        ctx.fillText(r[1].slice(0, Math.max(0, n - 4)), x + 96, y + 60 + i * 34);
        ctx.fillStyle = acc;
        ctx.textAlign = 'right';
        ctx.fillText(r[2].slice(0, Math.max(0, n - 12)), x + w - 14, y + 60 + i * 34);
        ctx.textAlign = 'left';
      });
    },
    typer(ctx, o, k, acc) {                // code that writes itself, a few characters per frame
      const x = o.x ?? 90, y = o.y ?? 110, w = o.w ?? 620, lh = 22, rows = o.rows || 14;
      panel(ctx, x, y, w, 40 + rows * lh, o.title);
      let n = Math.floor((k - o.k0) * (o.cps || 5));
      const lines = [];
      for (const ln of o.lines) { if (n <= 0) break; lines.push(ln.slice(0, n)); n -= ln.length + 4; }
      const show = lines.slice(-rows);
      ctx.font = MONO(15);
      show.forEach((ln, i) => {
        ctx.fillStyle = /^(#|\/\/)/.test(ln.trim()) ? '#9a9a9a' : /agent|token/.test(ln) ? acc : '#e8e8e8';
        ctx.fillText(ln, x + 14, y + 46 + i * lh);
      });
      if (show.length && Math.floor(k / 4) % 2) {
        const last = show[show.length - 1];
        ctx.fillStyle = '#fff';
        ctx.fillRect(x + 14 + ctx.measureText(last).width + 2, y + 46 + (show.length - 1) * lh - 13, 8, 15);
      }
    },
    counter(ctx, o, k, acc) {              // a number counting up, with a label
      const x = o.x ?? 960, y = o.y ?? 120, w = o.w ?? 260;
      panel(ctx, x, y, w, 84, o.title);
      const u = clamp((k - o.k0) / Math.max(1, o.k1 - o.k0 - 1), 0, 1);
      const v = o.from + (o.to - o.from) * Math.pow(u, o.power || 1);
      ctx.font = MONO(34, 700);
      ctx.fillStyle = o.accent ? acc : '#fff';
      ctx.fillText((o.prefix || '') + Math.round(v).toLocaleString('en-US') + (o.suffix || ''), x + 12, y + 66);
    },
    lower(ctx, o, k, acc) {                // news lower third
      const a = clamp((k - o.k0) / 5, 0, 1);
      const y = o.y ?? H - BOT - 150;
      ctx.fillStyle = acc;
      ctx.fillRect(48, y, 190 * a, 34);
      ctx.fillStyle = 'rgba(0,0,0,0.75)';
      ctx.fillRect(48 + 190 * a, y, (o.w || 520) * a, 34);
      if (a < 1) return;
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'left';
      ctx.font = HEAD(24);
      ctx.fillStyle = '#000';
      ctx.fillText(o.head, 60, y + 18);
      ctx.font = MONO(16);
      ctx.fillStyle = '#fff';
      ctx.fillText(o.text, 252, y + 18);
      ctx.textBaseline = 'alphabetic';
    },
    stamp(ctx, o, k, acc) {                // a stamp slammed onto the picture and held (hold it long enough to read)
      const u = ease.out(clamp((k - o.k0) / 4, 0, 1)), sc = 2.3 - 1.3 * u;
      const size = o.size || 54;
      ctx.save();
      ctx.font = HEAD(size);
      const w = ctx.measureText(o.text).width + 36, h = size * 1.25;
      ctx.translate((o.x ?? 760) + w / 2, (o.y ?? 230) + h / 2);
      ctx.rotate(((o.rot ?? -6) * Math.PI) / 180);
      ctx.scale(sc, sc);
      ctx.globalAlpha = clamp((o.k1 - k) / 6, 0, 1) * 0.95;
      const col = o.color || '#F04A2C';
      ctx.fillStyle = 'rgba(30,8,5,0.55)';
      ctx.fillRect(-w / 2, -h / 2, w, h);
      ctx.strokeStyle = col;
      ctx.lineWidth = 4;
      ctx.strokeRect(-w / 2, -h / 2, w, h);
      ctx.fillStyle = col;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(o.text, 0, 3);
      ctx.restore();
    },
    check(ctx, o, k, acc) {                // a check mark pops, then words appear on their frames
      const x = o.x ?? 120, y = o.y ?? 200, s = o.scale || 1, col = o.color || '#5FE08A';
      const u = clamp((k - o.k0) / 6, 0, 1), pop = u < 1 ? 0.6 + 0.55 * ease.out(u) - 0.15 * u : 1;
      const r = 34 * s * pop;
      ctx.save();
      ctx.fillStyle = 'rgba(0,0,0,0.6)';
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
      ctx.strokeStyle = col;
      ctx.lineWidth = 5 * s;
      ctx.lineJoin = ctx.lineCap = 'round';
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.stroke();
      ctx.lineWidth = 7 * s;
      ctx.beginPath();
      ctx.moveTo(x - 0.46 * r, y + 0.03 * r); ctx.lineTo(x - 0.13 * r, y + 0.36 * r); ctx.lineTo(x + 0.49 * r, y - 0.36 * r);
      ctx.stroke();
      ctx.font = HEAD(44 * s);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = 'rgba(0,0,0,0.8)';
      ctx.shadowBlur = 10;
      let tx = x + 50 * s;
      for (const w of o.words || []) {
        const a = clamp((k - w.k) / 4, 0, 1);
        if (a > 0) {
          ctx.globalAlpha = a;
          ctx.fillStyle = w.accent ? col : '#fff';
          ctx.fillText(w.text, tx, y + 2 + (1 - a) * 10);
        }
        tx += ctx.measureText(w.text + ' ').width;
      }
      if (o.sub && k >= o.k0 + 6) {
        ctx.globalAlpha = 1;
        ctx.font = MONO(15 * s, 700);
        ctx.fillStyle = acc;
        ctx.fillText(o.sub, x + 52 * s, y + 38 * s);
      }
      ctx.restore();
    },
    sight(ctx, o, k, acc) {                // a look: dots travel from `from` to `to`, then fade
      const [x0, y0] = o.from, [x1, y1] = o.to;
      const u = ease.out(clamp((k - o.k0) / (o.travel || 13), 0, 1));
      const fade = clamp((o.k1 - k) / 8, 0, 1), len = Math.hypot(x1 - x0, y1 - y0);
      ctx.save();
      ctx.fillStyle = o.color || '#62D6F5';
      for (let i = 0; i < 26; i++) {
        const v = i / 25;
        if (v > u) break;
        const r = 4 - 2 * v;
        ctx.globalAlpha = 0.9 * fade;
        ctx.beginPath();
        ctx.arc(x0 + (x1 - x0) * v, y0 + (y1 - y0) * v - (o.rise ?? 0.11) * len * Math.sin(v * Math.PI), r, 0, 7);
        ctx.fill();
      }
      ctx.restore();
    },
    rings(ctx, o, k, acc) {                // a key press, a touch: rings spread from a point
      const [x, y] = o.at;
      ctx.save();
      ctx.strokeStyle = o.color || '#62D6F5';
      ctx.lineWidth = 3;
      for (let j = 0; j < (o.n || 3); j++) {
        const u = (k - o.k0 - j * 2) / 14;
        if (u <= 0 || u >= 1) continue;
        const r = 14 + (o.r || 170) * ease.out(u);
        ctx.globalAlpha = (1 - u) * 0.9;
        ctx.beginPath(); ctx.ellipse(x, y, r, r * (o.flat ?? 0.45), 0, 0, 7); ctx.stroke();
      }
      ctx.restore();
    },
    cards(ctx, o, k, acc) {                // notes or cards fly off from a point (use "behind": true to pass behind people)
      const [x0, y0] = o.from, n = o.n || 10, size = o.size || 72, life = o.life || 28;
      ctx.save();
      for (let i = 0; i < n; i++) {
        const u = (k - o.k0 - i * (o.step || 2.5)) / life;
        if (u <= 0 || u >= 1) continue;
        const e = ease.out(u), side = (o.side ?? 1) * (o.fan ? (i % 2 ? 1 : -1) : 1);
        const x = x0 + 40 * (i % 4) + side * (330 + 60 * (i % 5)) * e;
        const y = y0 + 70 * (i % 3) - (170 + 26 * (i % 4)) * e + 105 * u * u;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate((0.4 + 2.5 * u) * (i % 2 ? 1 : -1) + i);
        ctx.globalAlpha = Math.pow(1 - u, 0.7);
        ctx.fillStyle = o.color || '#FAE896';
        ctx.fillRect(-size / 2, -size * (o.ratio || 1) / 2, size, size * (o.ratio || 1));
        ctx.strokeStyle = 'rgba(90,80,60,0.6)';
        ctx.lineWidth = 1;
        ctx.strokeRect(-size / 2, -size * (o.ratio || 1) / 2, size, size * (o.ratio || 1));
        ctx.restore();
      }
      ctx.restore();
    },
    flip(ctx, o, k, acc) {                 // a calendar sheet that turns over on frame `k`: from {label, text} to {label, text}
      const x = o.x ?? 990, y = o.y ?? 84, w = o.w ?? 186, h = o.h ?? 194;
      const f = clamp((k - o.k) / 6, 0, 1), sq = Math.max(Math.abs(Math.cos(f * Math.PI)), 0.04), side = f > 0.5 ? o.to : o.from;
      const hh = h * sq, top = y + (h - hh) / 2;
      ctx.save();
      ctx.globalAlpha = clamp((k - o.k0) / 6, 0, 1);
      ctx.fillStyle = '#F0EADC';
      ctx.fillRect(x, top, w, hh);
      ctx.fillStyle = f > 0.5 ? (o.color || '#62D6F5') : acc;
      ctx.fillRect(x, top, w, 42 * sq);
      if (sq > 0.5) {
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#141418';
        ctx.font = MONO(16, 700);
        ctx.fillText(side.label || '', x + w / 2, top + 22);
        ctx.font = HEAD(76);
        ctx.fillStyle = '#1e1c1a';
        ctx.fillText(side.text, x + w / 2, y + h / 2 + 24);
      }
      ctx.restore();
    },
    quote(ctx, o, k, acc) {                // a quotation card: lines, one marked phrase, the source (hold it >= 5 s)
      const a = clamp((k - o.k0) / 12, 0, 1) * clamp((o.k1 - k) / 12, 0, 1);
      const size = o.size || 42, lh = size * 1.45;
      ctx.save();
      ctx.fillStyle = `rgba(0,0,0,${(o.dim ?? 0.8) * a})`;
      ctx.fillRect(0, TOP, W, H - TOP - BOT);
      ctx.globalAlpha = a;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      ctx.font = `italic 400 ${size}px Georgia, "Times New Roman", serif`;
      const y0 = (o.y ?? H / 2) - ((o.lines.length - 1) * lh) / 2;
      o.lines.forEach((ln, i) => {
        const tw = ctx.measureText(ln).width, x = (W - tw) / 2, y = y0 + i * lh;
        const at = o.mark ? ln.indexOf(o.mark) : -1;
        if (at >= 0) {
          ctx.fillStyle = acc;
          ctx.globalAlpha = 0.55 * a;
          ctx.fillRect(x + ctx.measureText(ln.slice(0, at)).width - 4, y - size * 0.86, ctx.measureText(o.mark).width + 8, size * 1.16);
          ctx.globalAlpha = a;
        }
        ctx.fillStyle = '#E6E1D6';
        ctx.fillText(ln, x, y);
      });
      if (o.source) {
        ctx.font = MONO(17, 700);
        ctx.fillStyle = acc;
        ctx.textAlign = 'center';
        ctx.fillText(o.source, W / 2, y0 + o.lines.length * lh + 6);
      }
      ctx.restore();
    },
    credits(ctx, o, k, acc) {
      ctx.fillStyle = `rgba(0,0,0,${0.74 * clamp((k - o.k0) / 20, 0, 1)})`;
      ctx.fillRect(0, TOP, W, H - TOP - BOT);
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';
      o.lines.forEach((t, i) => {
        const kk = o.k0 + 10 + i * (o.step || 14);
        if (k < kk) return;
        ctx.globalAlpha = clamp((k - kk) / 8, 0, 1);
        ctx.font = t.head ? HEAD(t.size || 54) : MONO(t.size || 17);
        ctx.fillStyle = t.accent ? acc : t.dim ? '#a8a8a8' : '#fff';
        ctx.fillText(t.text, 96, t.y);
      });
      ctx.globalAlpha = 1;
    },
  };

  function dust(ctx, k, d, kick) {         // dust in the light: slow, a little brighter on the beat; only drawn behind people
    const n = d.n || 70, t = k / edit.fps;
    ctx.save();
    ctx.fillStyle = d.color || '#FFD6A0';
    for (let i = 0; i < n; i++) {
      const ph = rnd(i * 3 + 1) * 6.28, sp = 6 + rnd(i * 3 + 2) * 16, r = 1.3 + rnd(i * 3 + 3) * 2.7;
      const x = (rnd(i * 7 + 5) * W + sp * t + 9 * Math.sin(ph + t * 0.7)) % W;
      const y = rnd(i * 11 + 9) * H * 0.8 + 7 * Math.sin(ph * 2 + t * 0.5);
      ctx.globalAlpha = Math.min(1, (0.12 + 0.12 * Math.sin(ph + t * 1.3) ** 2) * (1 + 1.2 * kick) * (d.a || 1));
      ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    }
    ctx.restore();
  }

  function iris(ctx, k, o) {               // iris out: the circle closes to radius r, holds until k_hold, then shuts at k1
    const cx = (o.c?.[0] ?? 0.5) * W, cy = (o.c?.[1] ?? 0.5) * H, big = Math.hypot(W, H);
    const ks = o.k_small ?? o.k0 + Math.round((o.k1 - o.k0) * 0.55), kh = o.k_hold ?? ks + Math.round((o.k1 - o.k0) * 0.2);
    const r0 = o.r ?? 180;
    let r = 0;
    if (k < ks) r = big + (r0 - big) * ease.out(clamp((k - o.k0) / Math.max(1, ks - o.k0), 0, 1));
    else if (k < kh) r = r0;
    else if (k < o.k1) r = r0 * (1 - ((k - kh) / Math.max(1, o.k1 - kh)) ** 2);
    ctx.save();
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.rect(0, 0, W, H);
    if (r > 0.5) ctx.arc(cx, cy, r, 0, 7, true);
    ctx.fill();
    ctx.restore();
  }

  // ---- frame -------------------------------------------------------------------------------------------------
  return async function drawFrame(ctx, k) {
    const part = parts.find((p) => k >= p.k0 && k < p.k1);
    const shot = part.shot, wd = world(shot.world), acc = wd.accent;
    const u = (k - part.k0) / Math.max(1, part.k1 - part.k0 - 1);
    let srcIdx = 0, url = '/' + part.src;
    if (part.kind === 'take') {
      srcIdx = takeIndex(part, k);
      url = `/frames/${part.src}/${pad(srcIdx + 1, 4)}.jpg`;
    }
    const im = await image(url);

    ctx.setTransform(S, 0, 0, S, 0, 0);
    octx.setTransform(S, 0, 0, S, 0, 0);
    octx.filter = 'none';
    octx.fillStyle = '#000';
    octx.fillRect(0, 0, W, H);
    const geo = drawSource(im, part, u);

    // picture: per-world grade, beat pulse
    const kick = beatKick(k) * (wd.pulse ?? 1);
    const g = wd.grade;
    ctx.save();
    ctx.shadowColor = 'transparent';
    ctx.globalAlpha = 1;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    ctx.filter = `contrast(${g.contrast + 0.06 * kick}) saturate(${g.saturate}) brightness(${g.brightness + 0.10 * kick})`;
    const pz = 1 + 0.012 * kick;
    ctx.translate(W / 2, H / 2);
    ctx.scale(pz, pz);
    ctx.drawImage(off, -W / 2, -H / 2, W, H);
    ctx.restore();
    if (part.kind === 'still') {           // stills get light grain so they do not read as frozen
      ctx.save();
      ctx.globalAlpha = 0.05;
      for (let i = 0; i < 900; i++) {
        ctx.fillStyle = rnd(k * 977 + i) > 0.5 ? '#fff' : '#000';
        ctx.fillRect(rnd(k * 31 + i * 7) * W, rnd(k * 57 + i * 13) * H, 2, 2);
      }
      ctx.restore();
    }
    const live = (edit.overlays || []).filter((o) => k >= o.k0 && k < o.k1);
    // pieces behind people: dust and overlays with "behind": true are cut out by the take's mask (masks/<take>/NNNN.png,
    // alpha = near; made by ai-video near_masks.py). Without a mask dust is left out and "behind" overlays lie in front.
    const masked = part.kind === 'take' && clips[part.src]?.masks;
    const dst = wd.dust ?? edit.dust;
    const behind = live.filter((o) => o.behind && masked);
    if (!plate && ((dst && masked) || behind.length)) {
      bctx.setTransform(S, 0, 0, S, 0, 0);
      bctx.globalCompositeOperation = 'source-over';
      bctx.clearRect(0, 0, W, H);
      if (dst) dust(bctx, k, dst === true ? {} : dst, kick);
      for (const o of behind) overlay[o.type](bctx, o, k, acc);
      const mk = await image(`/masks/${part.src}/${pad(srcIdx + 1, 4)}.png`);
      bctx.globalCompositeOperation = 'destination-out';
      bctx.drawImage(mk, geo.x, geo.y, geo.dw, geo.dh);
      bctx.globalCompositeOperation = 'source-over';
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.scale(pz, pz);
      ctx.drawImage(back, -W / 2, -H / 2, W, H);
      ctx.restore();
    }
    for (const o of live) if (o.type === 'flash') overlay.flash(ctx, o, k);
    const fi = edit.fade_in || 0, fo = edit.fade_out || 0;
    const dark = k < fi ? 1 - k / fi : k >= edit.frames - fo ? (k - (edit.frames - fo)) / fo : 0;
    if (dark > 0) {
      ctx.fillStyle = `rgba(0,0,0,${dark})`;
      ctx.fillRect(0, 0, W, H);
    }
    if (plate) return;

    // lyric position: bottom left; top left when her mouth would sit under the words
    let top = false;
    if (part.kind === 'take') {
      const li = lineAt(k);
      if (li >= 0) top = lyricTop(part, li, im.naturalWidth, im.naturalHeight);
      if (part.lyric_top !== undefined) top = part.lyric_top;
      if (part.track !== false && (part.label || wd.tracker)) tracker(ctx, part, geo, srcIdx, part.label || wd.tracker);
    } else tag(ctx, part, k);
    const late = (o) => o.type === 'credits' || o.type === 'quote';
    for (const o of live) if (o.type !== 'flash' && !late(o) && !behind.includes(o)) overlay[o.type](ctx, o, k, acc);
    if (!live.some(late)) lyrics(ctx, k, acc, top);
    for (const o of live) if (late(o)) overlay[o.type](ctx, o, k, acc);
    if (edit.iris && k >= edit.iris.k0) iris(ctx, k, edit.iris);
    chrome(ctx, k, shot, acc);
  };
}
