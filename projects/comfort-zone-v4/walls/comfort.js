var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// src/util.ts
var clamp = /* @__PURE__ */ __name((x, a = 0, b = 1) => Math.min(b, Math.max(a, x)), "clamp");
var prog = /* @__PURE__ */ __name((t, a, b) => clamp((t - a) / (b - a)), "prog");
var easeOut = /* @__PURE__ */ __name((x) => 1 - Math.pow(1 - clamp(x), 3), "easeOut");
var easeInOut = /* @__PURE__ */ __name((x) => {
  x = clamp(x);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}, "easeInOut");
var easeOutBack = /* @__PURE__ */ __name((x) => {
  x = clamp(x);
  const c1 = 1.9;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
}, "easeOutBack");
var hash = /* @__PURE__ */ __name((n) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}, "hash");

// walls_comfort.ts
var API;
function setApi(a) {
  API = a;
}
__name(setApi, "setApi");
var W = /* @__PURE__ */ __name((li, wi = 0) => API.W(li, wi), "W");
var GOLD = "#ffcc00";
var BLUE = "#0a3fbf";
var RED = "#e3001b";
var HEAVY = '"Anton", Impact, sans-serif';
var MONO = '"Space Mono", Consolas, monospace';
function txt(g, s, x, y, size, color, align = "center", font = HEAVY, alpha = 1) {
  if (alpha <= 0) return;
  g.save();
  g.globalAlpha = clamp(alpha);
  g.font = `${size}px ${font}`;
  g.textAlign = align;
  g.textBaseline = "middle";
  g.fillStyle = color;
  g.shadowColor = color;
  g.shadowBlur = size * 0.25;
  g.fillText(s, x, y);
  g.restore();
}
__name(txt, "txt");
function star(g, x, y, r, color, alpha = 1, rot = 0) {
  if (alpha <= 0 || r <= 0) return;
  g.save();
  g.globalAlpha = clamp(alpha);
  g.translate(x, y);
  g.rotate(rot);
  g.beginPath();
  for (let k = 0; k < 10; k++) {
    const rr = k % 2 ? r * 0.4 : r;
    const a = k / 10 * Math.PI * 2 - Math.PI / 2;
    g.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  g.closePath();
  g.fillStyle = color;
  g.shadowColor = color;
  g.shadowBlur = r * 0.8;
  g.fill();
  g.restore();
}
__name(star, "star");
function starRing(g, x, y, R, r, color, alpha = 1, rot = 0, count = 12) {
  for (let i = 0; i < count; i++) {
    const a = i / 12 * Math.PI * 2 - Math.PI / 2 + rot;
    star(g, x + Math.cos(a) * R, y + Math.sin(a) * R, r, color, alpha);
  }
}
__name(starRing, "starRing");
function bg(g, w, h, a, b) {
  const gr = g.createLinearGradient(0, 0, 0, h);
  gr.addColorStop(0, a);
  gr.addColorStop(1, b);
  g.fillStyle = gr;
  g.fillRect(0, 0, w, h);
}
__name(bg, "bg");
function radial(g, x, y, r, color, alpha) {
  g.save();
  g.globalAlpha = clamp(alpha);
  const gr = g.createRadialGradient(x, y, 0, x, y, r);
  gr.addColorStop(0, color);
  gr.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = gr;
  g.fillRect(x - r, y - r, r * 2, r * 2);
  g.restore();
}
__name(radial, "radial");
var typed = /* @__PURE__ */ __name((s, t, a, b) => s.slice(0, Math.round(clamp((t - a) / (b - a)) * s.length)), "typed");
var logo = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#020414", "#000");
  radial(g, w / 2, h / 2, 520, BLUE, 0.55 + 0.25 * c.pulse);
  starRing(g, w / 2, h / 2, 250, 22, GOLD, clamp(c.local / 2), c.t * 0.05);
  const k = easeOutBack(prog(c.local, 0.6, 1.4));
  txt(g, "COMFORT ZONE", w / 2, h / 2 - 10, 120 * k, "#fff");
  txt(g, "LIVE \xB7 BR\xDCSSEL \xB7 2031", w / 2, h / 2 + 90, 30, GOLD, "center", MONO, prog(c.local, 1.4, 2));
}, "logo");
var intro = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#01020a", "#000");
  const y = c.t * 120 % (h + 200) - 100;
  g.fillStyle = "rgba(10,63,191,0.35)";
  g.fillRect(0, y, w, 6);
  starRing(g, w / 2, h / 2, 250, 18, GOLD, 0.25 + 0.5 * clamp((c.t - 4) / 5), c.t * 0.04, Math.min(12, Math.floor(c.t * 1.4)));
  txt(g, "COMFORT ZONE", w / 2, h / 2, 110, "#fff", "center", HEAVY, clamp((c.t - 6) / 2.5));
}, "intro");
var clock = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#0d1430", "#020308");
  g.fillStyle = "#05060c";
  g.beginPath();
  g.moveTo(0, h);
  let x = 0;
  let i = 0;
  while (x < w) {
    const bw = 40 + hash(i) * 70;
    const bh = 90 + hash(i * 3) * 170;
    g.lineTo(x, h - bh);
    g.lineTo(x + bw, h - bh);
    x += bw;
    i++;
  }
  g.lineTo(w, h);
  g.fill();
  g.fillStyle = "#080a14";
  g.fillRect(w / 2 - 230, h - 300, 460, 300);
  g.fillRect(w / 2 - 70, h - 380, 140, 380);
  for (let k = 0; k < 60; k++) {
    const on = hash(k * 7) < clamp(c.local / 4);
    if (!on) continue;
    g.fillStyle = "rgba(255,214,120,0.85)";
    g.fillRect(w / 2 - 210 + k % 12 * 36, h - 270 + Math.floor(k / 12) * 48, 18, 22);
  }
  const flip = c.t > W(1) ? "08:00" : "07:59";
  txt(g, flip, w / 2, 190, 190, c.t > W(1) ? RED : "#fff");
  txt(g, "MONTAG \xB7 BR\xDCSSEL", w / 2, 320, 30, GOLD, "center", MONO);
}, "clock");
var deck = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#e6e2d8", "#c9c4b8");
  g.fillStyle = BLUE;
  g.fillRect(0, 0, w, 110);
  txt(g, "STRATEGIE 2031", 60, 58, 64, "#fff", "left");
  const items = ["Vision", "Roadmap", "Synergien", "Arbeitskreis"];
  items.forEach((it, i) => {
    const a = W(2, 0) + i * 0.45;
    g.globalAlpha = clamp((c.t - a) / 0.2);
    g.fillStyle = RED;
    g.fillRect(80, 180 + i * 90, 22, 22);
    g.globalAlpha = 1;
    txt(g, it, 130, 192 + i * 90, 54, "#111", "left", HEAVY, clamp((c.t - a) / 0.2));
  });
  const k = clamp((c.t - W(3, 0)) / 2.4);
  if (k > 0) {
    g.save();
    g.strokeStyle = RED;
    g.lineWidth = 12;
    g.shadowColor = RED;
    g.shadowBlur = 30;
    g.beginPath();
    for (let i = 0; i <= 80 * k; i++) {
      const u = i / 80;
      const px = 620 + u * 620;
      const py = 640 - (Math.exp(u * 4.6) - 1) * 6.4;
      if (i === 0) g.moveTo(px, py);
      else g.lineTo(px, py);
    }
    g.stroke();
    g.restore();
    txt(g, "FUTURE \u2191", 1060, 140, 60, RED, "center", HEAVY, clamp((k - 0.6) * 4));
  }
}, "deck");
var split = /* @__PURE__ */ __name((g, w, h, c) => {
  const sv = g.createLinearGradient(0, 0, 0, h);
  sv.addColorStop(0, "#ff8a2a");
  sv.addColorStop(1, "#5a1a3a");
  g.fillStyle = sv;
  g.fillRect(0, 0, w / 2, h);
  bg(g, w, h, "#000", "#000");
  g.fillStyle = sv;
  g.fillRect(0, 0, w / 2, h);
  g.fillStyle = "#0a1c5a";
  g.fillRect(w / 2, 0, w / 2, h);
  txt(g, "SILICON VALLEY", w / 4, 120, 56, "#fff");
  txt(g, "EUROPA", w * 3 / 4, 120, 56, GOLD);
  const k = easeOut(clamp((c.t - W(4, 3)) / 1.2));
  g.save();
  g.strokeStyle = "#fff";
  g.lineWidth = 10;
  g.beginPath();
  g.moveTo(60, 640);
  g.quadraticCurveTo(260, 620, 60 + 520 * k, 640 - 420 * k * k);
  g.stroke();
  g.restore();
  txt(g, "LET'S GO!", w / 4, 380, 110 * easeOutBack(clamp((c.t - W(4, 3)) / 0.35)), "#fff");
  g.fillStyle = "rgba(255,255,255,0.12)";
  for (let i = 0; i < 5; i++) g.fillRect(w / 2 + 90, 220 + i * 70, 460, 34);
  const st = clamp((c.t - W(5, 2)) / 0.15);
  if (st > 0) {
    g.save();
    g.translate(w * 3 / 4, 420);
    g.rotate(-0.18);
    const s = 2.2 - 1.2 * easeOut(st);
    g.scale(s, s);
    g.strokeStyle = RED;
    g.lineWidth = 8;
    g.strokeRect(-210, -60, 420, 120);
    txt(g, "IN PR\xDCFUNG", 0, 0, 74, RED);
    g.restore();
  }
}, "split");
var committees = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#101218", "#050608");
  const merge = easeInOut(clamp((c.t - W(6, 4)) / 1));
  for (let i = 0; i < 5; i++) {
    const a = W(6, 0) + i * 0.22;
    const x0 = 140 + i * 250;
    const x = x0 + (w / 2 - x0) * merge;
    const y = 250 + 120 * merge;
    const al = clamp((c.t - a) / 0.2) * (1 - merge * 0.85);
    g.globalAlpha = al;
    g.fillStyle = "#2b3140";
    g.fillRect(x - 100, y - 90, 200, 180);
    g.globalAlpha = 1;
    txt(g, `AUSSCHUSS ${i + 1}`, x, y, 30, "#cfd5e0", "center", MONO, al);
  }
  const rk = easeOutBack(clamp((c.t - W(6, 4) - 0.8) / 0.4));
  if (rk > 0) {
    g.fillStyle = "#e8e4da";
    g.fillRect(w / 2 - 130 * rk, 230, 260 * rk, 300);
    txt(g, "BERICHT", w / 2, 300, 50 * rk, "#111");
    txt(g, "1.240 Seiten", w / 2, 360, 24 * rk, "#555", "center", MONO);
  }
  const ck = clamp((c.t - W(7, 0)) / 0.3);
  if (ck > 0) {
    g.fillStyle = "rgba(227,0,27,0.9)";
    g.fillRect(0, h - 120, w, 120);
    const n = Math.floor((c.t - W(7, 0)) * 997) % 1e4;
    txt(g, `KONKURRENZ \xB7 24/7 \xB7 ${String(n).padStart(4, "0")} RELEASES`, w / 2, h - 60, 48, "#fff", "center", HEAVY, ck);
  }
}, "committees");
var windowSky = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#061031", "#1b2c5c");
  for (let i = 0; i < 120; i++) {
    const tw = 0.5 + 0.5 * Math.sin(c.t * 2 + i);
    g.fillStyle = `rgba(255,255,255,${(0.3 + 0.5 * tw * hash(i)).toFixed(2)})`;
    g.fillRect(hash(i * 3) * w, hash(i * 5) * h * 0.6, 3, 3);
  }
  g.fillStyle = "#03050c";
  g.fillRect(w / 2 - 330, h - 230, 660, 230);
  g.fillRect(w / 2 - 90, h - 330, 180, 330);
  g.strokeStyle = "#0b0b10";
  g.lineWidth = 46;
  g.strokeRect(40, 30, w - 80, h - 60);
  g.lineWidth = 22;
  g.beginPath();
  g.moveTo(w / 2, 30);
  g.lineTo(w / 2, h - 30);
  g.moveTo(40, h * 0.45);
  g.lineTo(w - 40, h * 0.45);
  g.stroke();
  const ck = clamp((c.t - W(11, 0)) / 0.3);
  if (ck > 0) {
    const days = Math.floor(Math.max(0, c.t - W(11, 0)) * 6);
    const d = new Date(2031, 0, 1 - days);
    g.fillStyle = `rgba(232,228,218,${ck})`;
    g.fillRect(w / 2 - 170, 150, 340, 300);
    g.fillStyle = `rgba(227,0,27,${ck})`;
    g.fillRect(w / 2 - 170, 150, 340, 70);
    txt(g, "GESTERN", w / 2, 185, 40, "#fff", "center", HEAVY, ck);
    txt(g, String(d.getDate()), w / 2, 320, 140, "#111", "center", HEAVY, ck);
    txt(g, `${d.getMonth() + 1}.${d.getFullYear()}`, w / 2, 410, 32, "#333", "center", MONO, ck);
  }
}, "windowSky");
var storm = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#05060c", "#121828");
  const bolt = c.hit > 0.35;
  if (bolt) {
    g.fillStyle = `rgba(200,210,255,${(c.hit * 0.5).toFixed(2)})`;
    g.fillRect(0, 0, w, h);
  }
  g.strokeStyle = "rgba(150,170,220,0.35)";
  g.lineWidth = 2;
  g.beginPath();
  for (let i = 0; i < 160; i++) {
    const x = (hash(i) * w + c.t * 300 * (0.6 + hash(i * 2))) % w;
    const y = (hash(i * 3) * h + c.t * 900) % h;
    g.moveTo(x, y);
    g.lineTo(x - 14, y + 40);
  }
  g.stroke();
  if (bolt) {
    g.save();
    g.strokeStyle = "#fff";
    g.lineWidth = 6;
    g.shadowColor = "#9fb6ff";
    g.shadowBlur = 40;
    g.beginPath();
    let x = 300 + hash(Math.floor(c.t * 3)) * 680;
    g.moveTo(x, 0);
    for (let y = 0; y < h; y += 60) {
      x += (hash(y + Math.floor(c.t * 3)) - 0.5) * 120;
      g.lineTo(x, y);
    }
    g.stroke();
    g.restore();
  }
  const shake = c.hit * 10;
  starRing(g, w / 2 + Math.sin(c.t * 50) * shake, h / 2, 230, 20, GOLD, 0.95, c.t * 0.2);
  txt(g, "OUT OF THE", w / 2, h / 2 - 50, 64, "#fff");
  txt(g, "COMFORT ZONE", w / 2, h / 2 + 30, 104 * (1 + 0.04 * c.pulse), GOLD);
}, "storm");
var year2031 = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#120004", "#000");
  radial(g, w / 2, h / 2, 600, RED, 0.35 + 0.3 * c.pulse);
  txt(g, "2031", w / 2, h / 2 - 30, 330 * (1 + 0.05 * c.pulse), "#fff");
  g.save();
  g.strokeStyle = RED;
  g.lineWidth = 8;
  g.shadowColor = RED;
  g.shadowBlur = 24;
  g.beginPath();
  const off = c.t * 400 % 400;
  for (let x = 0; x <= w; x += 8) {
    const p = (x + off) % 400;
    const y = p > 180 && p < 240 ? p < 200 ? -90 : p < 215 ? 70 : -20 : 0;
    if (x === 0) g.moveTo(x, h - 120 + y);
    else g.lineTo(x, h - 120 + y);
  }
  g.stroke();
  g.restore();
  txt(g, "ARE WE STILL ALIVE?", w / 2, 90, 46, GOLD, "center", HEAVY, 0.6 + 0.4 * c.pulse);
}, "year2031");
var hey = /* @__PURE__ */ __name((g, w, h, c) => {
  const on = Math.floor(c.beat) % 2 === 0;
  bg(g, w, h, on ? RED : "#000", on ? "#7a0010" : "#000");
  txt(g, "HEY!", w / 2, h / 2 - 20, 330 * (1 + 0.12 * c.pulse), on ? "#fff" : RED);
  txt(g, "WAKE UP", w / 2, h - 110, 70, on ? "#000" : "#fff", "center", HEAVY, 0.9);
}, "hey");
var eq = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#02030a", "#000");
  const n = 32;
  for (let i = 0; i < n; i++) {
    const v = 0.25 + 0.55 * Math.abs(Math.sin(c.t * (2 + hash(i) * 3) + i)) * (0.6 + 0.4 * c.pulse) + c.hit * 0.3;
    const bh = v * h * 0.8;
    const x = 40 + i * ((w - 80) / n);
    const gr = g.createLinearGradient(0, h, 0, h - bh);
    gr.addColorStop(0, BLUE);
    gr.addColorStop(1, i % 4 === 0 ? RED : GOLD);
    g.fillStyle = gr;
    g.fillRect(x, h - bh, (w - 80) / n - 8, bh);
  }
  txt(g, "COMFORT ZONE", w / 2, 110, 80, "#fff", "center", HEAVY, 0.9);
}, "eq");
var goldenGate = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#ff9a4a", "#4a1a3a");
  radial(g, w * 0.7, h * 0.62, 260, "#ffe08a", 0.9);
  g.fillStyle = "#2a0c18";
  g.fillRect(0, h - 140, w, 140);
  g.strokeStyle = "#c0362c";
  g.lineWidth = 16;
  for (const x of [380, 900]) {
    g.beginPath();
    g.moveTo(x, h - 140);
    g.lineTo(x, 160);
    g.stroke();
  }
  g.lineWidth = 6;
  g.beginPath();
  g.moveTo(0, 360);
  g.quadraticCurveTo(380 - 190, 520, 380, 160);
  g.quadraticCurveTo(640, 540, 900, 160);
  g.quadraticCurveTo(1090, 520, w, 360);
  g.stroke();
  g.fillStyle = "#c0362c";
  g.fillRect(0, h - 200, w, 18);
  const k = easeOut(clamp((c.t - W(19, 0)) / 0.4));
  if (k > 0) {
    const x0 = w - 560 * k;
    g.fillStyle = "rgba(5,8,14,0.92)";
    g.fillRect(x0, 60, 540, 440);
    const code = ["def europe():", "  plan = review(plan)", "  while not ready:", "    meeting += 1", "# AI: rewritten in 0.3 s", "ship()"];
    code.forEach((line, i) => {
      const a = W(19, 0) + 0.3 + i * 0.35;
      txt(g, typed(line, c.t, a, a + 0.3), x0 + 24, 110 + i * 60, 30, i === 4 ? "#7CFC9A" : "#cfe3ff", "left", MONO);
    });
  }
}, "goldenGate");
var agents = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#020812", "#000");
  const b0 = W(20, 0);
  const levels = Math.min(5, Math.floor(Math.max(0, c.t - b0) / 0.45) + 1);
  const crack = clamp((c.t - W(21, 0)) / 1.6);
  for (let lv = 0; lv < levels; lv++) {
    const n = 2 ** lv;
    for (let i = 0; i < n; i++) {
      const x = (i + 0.5) / n * w;
      const y = 80 + lv * 110;
      if (lv > 0) {
        const px = (Math.floor(i / 2) + 0.5) / (n / 2) * w;
        g.strokeStyle = "rgba(80,160,255,0.6)";
        g.lineWidth = 3;
        g.beginPath();
        g.moveTo(px, y - 110);
        g.lineTo(x, y);
        g.stroke();
      }
      g.fillStyle = lv === levels - 1 && c.pulse > 0.5 ? "#fff" : "#3d8bff";
      g.beginPath();
      g.arc(x, y, Math.max(5, 26 - lv * 5), 0, Math.PI * 2);
      g.fill();
    }
  }
  txt(g, "AGENT \xD7 AGENT", 40, h - 60, 44, "#3d8bff", "left", HEAVY, 1 - crack);
  if (crack > 0) {
    const sp = easeInOut(clamp((crack - 0.35) / 0.65)) * 160;
    for (const sd of [-1, 1]) {
      g.save();
      g.translate(w / 2 + sd * sp, 360 + sp * 0.4);
      g.rotate(sd * sp * 2e-3);
      g.fillStyle = "#8c8a84";
      g.beginPath();
      g.moveTo(0, -200);
      g.lineTo(sd * 220, -200);
      g.lineTo(sd * 220, 200);
      g.lineTo(0, 200);
      for (let y = 200; y > -200; y -= 40) g.lineTo(sd * (hash(y) * 18), y);
      g.closePath();
      g.fill();
      txt(g, sd < 0 ? "GEWISS" : "HEITEN", sd * 110, -60, 54, "#2a2a2a");
      txt(g, sd < 0 ? "SEIT" : "1957", sd * 110, 40, 38, "#3a3a3a", "center", MONO);
      g.restore();
    }
  }
}, "agents");
var bubble = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#0b0614", "#000");
  const popAt = W(22, 0) + 0.25;
  if (c.t < popAt) {
    const r = 80 + (c.t - (popAt - 3)) * 90;
    g.save();
    g.strokeStyle = "rgba(255,120,220,0.9)";
    g.lineWidth = 6;
    g.shadowColor = "#ff7ad9";
    g.shadowBlur = 40;
    g.beginPath();
    g.arc(w / 2, h / 2, Math.max(40, r), 0, Math.PI * 2);
    g.stroke();
    g.restore();
    txt(g, "HYPE", w / 2, h / 2, 90, "#ff9ae6");
  } else {
    const k = clamp((c.t - popAt) / 0.6);
    for (let i = 0; i < 40; i++) {
      const a = i / 40 * Math.PI * 2;
      const r = 120 + k * 420;
      g.fillStyle = `rgba(255,140,230,${(1 - k).toFixed(2)})`;
      g.fillRect(w / 2 + Math.cos(a) * r, h / 2 + Math.sin(a) * r, 10, 10);
    }
    txt(g, "BUBBLE!", w / 2, h / 2 - 140, 120 * easeOutBack(clamp((c.t - popAt) / 0.3)), "#ff9ae6", "center", HEAVY, 1 - clamp((c.t - W(23, 0)) / 0.4));
    const gk = clamp((c.t - W(23, 0)) / 2);
    if (gk > 0) {
      g.save();
      g.strokeStyle = GOLD;
      g.shadowColor = GOLD;
      g.shadowBlur = 16;
      g.lineWidth = 6;
      const branch = /* @__PURE__ */ __name((x, y, len, a, d) => {
        if (d > 6 || len < 8) return;
        const lk = clamp(gk * 7 - d);
        if (lk <= 0) return;
        const x2 = x + Math.cos(a) * len * lk;
        const y2 = y + Math.sin(a) * len * lk;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x2, y2);
        g.stroke();
        if (lk >= 1) {
          branch(x2, y2, len * 0.72, a - 0.5, d + 1);
          branch(x2, y2, len * 0.72, a + 0.5, d + 1);
        }
      }, "branch");
      branch(w / 2, h, 170, -Math.PI / 2, 0);
      g.restore();
      txt(g, "EIN NEUER TRAUM", w / 2, 70, 46, GOLD, "center", HEAVY, gk * 2);
    }
  }
}, "bubble");
var triad = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#02040c", "#000");
  const words = ["COMPUTE", "CAPITAL", "ENERGY"];
  const cols = ["#3d8bff", GOLD, RED];
  const geo = clamp((c.t - W(25, 0)) / 0.5);
  words.forEach((wd, i) => {
    const a = W(24, i);
    const k = easeOutBack(clamp((c.t - a) / 0.3));
    const x = 220 + i * 420;
    g.save();
    g.globalAlpha = 1 - geo * 0.6;
    g.fillStyle = cols[i];
    g.globalAlpha *= 0.25;
    g.fillRect(x - 190, 200, 380, 320);
    g.restore();
    txt(g, wd, x, 360, 92 * k, cols[i], "center", HEAVY, 1 - geo * 0.5);
  });
  if (geo > 0) {
    g.save();
    g.globalAlpha = geo;
    g.strokeStyle = "rgba(120,170,255,0.7)";
    g.lineWidth = 2;
    const R = 230;
    const cx = w / 2;
    const cy = h / 2;
    for (let i = 0; i < 9; i++) {
      const a = i / 9 * Math.PI + c.t * 0.4;
      g.beginPath();
      g.ellipse(cx, cy, Math.abs(Math.cos(a)) * R, R, 0, 0, Math.PI * 2);
      g.stroke();
    }
    for (let j = -3; j <= 3; j++) {
      g.beginPath();
      g.ellipse(cx, cy + j / 4 * R, Math.sqrt(1 - (j / 4) ** 2) * R, 18, 0, 0, Math.PI * 2);
      g.stroke();
    }
    g.restore();
    txt(g, "THE NEW GEOPOLITICS", w / 2, h - 70, 56, "#fff", "center", HEAVY, geo);
  }
}, "triad");
var news = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#0a0a12", "#000");
  g.fillStyle = RED;
  g.fillRect(0, 170, w, 170);
  txt(g, "NEWSFLASH", w / 2, 255, 140 * (1 + 0.03 * c.pulse), "#fff");
  g.fillStyle = "#fff";
  g.fillRect(0, 380, w, 80);
  const msg = "+++ EUROPA PR\xC4SENTIERT SEINE SPEZIALIT\xC4T +++ LIVE AUS BR\xDCSSEL +++ 2031 +++ ";
  g.save();
  g.font = `48px ${HEAVY}`;
  g.fillStyle = "#111";
  g.textBaseline = "middle";
  const off = c.t * 260 % 2600;
  g.fillText(msg + msg + msg, -off, 422);
  g.restore();
  txt(g, "LADIES AND GENTLEMEN", w / 2, 600, 54, GOLD, "center", HEAVY, clamp((c.t - W(27, 0)) / 0.3));
}, "news");
var menu = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#1a1410", "#0a0806");
  g.strokeStyle = GOLD;
  g.lineWidth = 4;
  g.strokeRect(160, 40, w - 320, h - 80);
  txt(g, "MEN\xDC \xB7 EUROP\xC4ISCHE SPEZIALIT\xC4T", w / 2, 110, 44, GOLD, "center", HEAVY, clamp((c.t - W(28, 0)) / 0.3));
  const courses = [
    ["1. REGULIEREN", 29, 1],
    ["2. ANALYSIEREN", 29, 3],
    ["3. EVALUIEREN", 30, 1],
    ["4. DISKUTIEREN", 30, 3]
  ];
  courses.forEach(([s, li, wi], i) => {
    const a = W(li, wi);
    const k = easeOutBack(clamp((c.t - a) / 0.3));
    txt(g, s, w / 2, 220 + i * 110, 72 * k, "#f2e6c8");
  });
  const end = clamp((c.t - W(31, 0)) / 0.3);
  txt(g, "\u2026und dann?", w / 2, h - 90, 40, RED, "center", MONO, end);
}, "menu");
var departures = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#05070a", "#000");
  txt(g, "ABFLUG \xB7 DEPARTURES", 60, 70, 46, GOLD, "left");
  const rows = [
    ["09:10", "SAN FRANCISCO", "GR\xDCNDER", "BOARDING"],
    ["09:25", "AUSTIN", "KI-TEAM", "BOARDING"],
    ["09:40", "SINGAPUR", "START-UP", "GATE B12"],
    ["10:05", "SHENZHEN", "HARDWARE", "GATE A3"],
    ["10:30", "BR\xDCSSEL", "ARBEITSKREIS", "VERSP\xC4TET"]
  ];
  rows.forEach((r, i) => {
    const a = W(32, 0) + i * 0.35;
    const y = 170 + i * 105;
    g.fillStyle = "#111620";
    g.fillRect(50, y - 40, w - 100, 80);
    const flip = /* @__PURE__ */ __name((s, at) => [...s].map((ch, j) => c.t < at + j * 0.03 ? String.fromCharCode(65 + Math.floor(hash(j + Math.floor(c.t * 20)) * 26)) : ch).join(""), "flip");
    txt(g, flip(r[0], a), 80, y, 40, "#f0d060", "left", MONO);
    txt(g, flip(r[1], a), 280, y, 46, "#fff", "left", HEAVY);
    txt(g, flip(r[2], a), 700, y, 34, "#9fb3c8", "left", MONO);
    const late = r[3] === "VERSP\xC4TET";
    const blink = r[3] === "BOARDING" && Math.floor(c.t * 2) % 2 === 0;
    txt(g, flip(r[3], a), w - 80, y, 40, late ? RED : blink ? "#7CFC9A" : "#4caf50", "right", HEAVY);
  });
}, "departures");
var revolutions = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#0c0c10", "#000");
  const ev = [
    ["1784", "DAMPF"],
    ["1870", "STROM"],
    ["1969", "COMPUTER"],
    ["2031", "KI"]
  ];
  ev.forEach(([y, s], i) => {
    const a = W(40, 0) + i * 0.6;
    const k = easeOutBack(clamp((c.t - a) / 0.35));
    const x = 200 + i * 300;
    txt(g, y, x, 160, 80 * k, i === 3 ? GOLD : "#fff");
    txt(g, s, x, 230, 34 * k, "#9aa0aa", "center", MONO);
  });
  g.fillStyle = "#2a2420";
  g.fillRect(200, 450, 880, 30);
  const flags = ["USA", "CHINA", "INDIEN", "EUROPA", "GOLF"];
  flags.forEach((f, i) => {
    const x = 270 + i * 185;
    const empty = f === "EUROPA";
    g.fillStyle = empty ? "rgba(255,204,0,0.15)" : "#5a5a66";
    g.fillRect(x - 40, 360, 80, 90);
    if (!empty) {
      g.fillStyle = "#9a9aa6";
      g.beginPath();
      g.arc(x, 340, 26, 0, Math.PI * 2);
      g.fill();
    }
    txt(g, f, x, 520, 26, empty ? GOLD : "#9aa0aa", "center", MONO, empty ? 0.5 + 0.5 * Math.sin(c.t * 5) : 1);
  });
  txt(g, "KEINER VON UNS ERSCHEINT", w / 2, h - 70, 46, RED, "center", HEAVY, clamp((c.t - W(41, 0)) / 0.3));
}, "revolutions");
var rulebook = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#06060a", "#000");
  radial(g, w / 2, h / 2, 420, GOLD, 0.25);
  g.fillStyle = "#7a1018";
  g.fillRect(w / 2 - 230, 90, 460, 540);
  g.fillStyle = "#5a0a10";
  g.fillRect(w / 2 - 230, 90, 30, 540);
  txt(g, "THE RULES", w / 2 + 15, 230, 84, GOLD);
  txt(g, "2031 EDITION", w / 2 + 15, 310, 30, "#f2e6c8", "center", MONO);
  const blink = Math.floor(c.t * 3) % 2 === 0;
  txt(g, `AUTHOR: ${blink ? "???" : "   "}`, w / 2 + 15, 520, 40, "#fff", "center", MONO);
  txt(g, "WHO?", w / 2, h / 2, 200 * easeOutBack(clamp((c.t - W(42, 0)) / 0.35)), "#fff", "center", HEAVY, clamp((c.t - W(42, 0)) / 0.35) * 0.9);
}, "rulebook");
var sunrise = /* @__PURE__ */ __name((g, w, h, c) => {
  const k = clamp(c.local / 4);
  bg(g, w, h, `rgb(${Math.round(20 + 200 * k)},${Math.round(30 + 120 * k)},${Math.round(80 + 20 * k)})`, "#ffcc66");
  radial(g, w / 2, h + 120 - k * 300, 700, "#fff3c0", 0.9);
  g.fillStyle = "#ffe9a0";
  g.beginPath();
  g.arc(w / 2, h + 120 - k * 300, 200, 0, Math.PI * 2);
  g.fill();
  starRing(g, w / 2, h / 2 - 40, 270, 22, BLUE, 0.9, c.t * 0.1);
  txt(g, "INTO THE LIGHT", w / 2, 90, 64, "#0a1c5a", "center", HEAVY, 0.9);
}, "sunrise");
var dance = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#000", "#000");
  const cols = [GOLD, "#fff", "#3d8bff", RED];
  const n = 8;
  for (let i = 0; i < n; i++) {
    const on = (Math.floor(c.beat * 2) + i) % 4 === 0;
    g.fillStyle = cols[i % 4];
    g.globalAlpha = on ? 0.95 : 0.15;
    g.fillRect(i * (w / n), 0, w / n - 6, h);
  }
  g.globalAlpha = 1;
  txt(g, "START THE DANCE", w / 2, h / 2, 120 * (1 + 0.06 * c.pulse), "#000", "center", HEAVY, clamp((c.t - W(46, 3)) / 0.2));
  txt(g, "ONE LAST CHANCE", w / 2, h / 2, 100, "#fff", "center", HEAVY, 1 - clamp((c.t - W(46, 3)) / 0.2));
}, "dance");
var maybeLater = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#0a0a0a", "#000");
  const pair = [
    ["MAYBE", 48, 2],
    ["LATER", 48, 5]
  ];
  pair.forEach(([s, li, wi], i) => {
    const a = W(li, wi);
    const k = clamp((c.t - a + 0.4) / 0.25);
    const y = 220 + i * 260;
    txt(g, s, w / 2, y, 200, "#fff", "center", HEAVY, k);
    const x = clamp((c.t - a - 0.1) / 0.25);
    if (x > 0) {
      g.save();
      g.strokeStyle = RED;
      g.lineWidth = 26;
      g.shadowColor = RED;
      g.shadowBlur = 20;
      g.beginPath();
      g.moveTo(w / 2 - 300, y + 40);
      g.lineTo(w / 2 - 300 + 600 * x, y - 40 * (2 * x - 1));
      g.stroke();
      g.restore();
    }
  });
}, "maybeLater");
var countdown = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#000", "#06001a");
  const a = W(49, 0);
  const yr = Math.min(2031, 2026 + Math.floor(Math.max(0, c.t - a) / 0.42));
  const fin = yr === 2031;
  if (fin) radial(g, w / 2, h / 2, 640, GOLD, 0.45 + 0.35 * c.pulse);
  txt(g, String(yr), w / 2, h / 2 - 20, 300 * (fin ? 1 + 0.05 * c.pulse : 1), fin ? GOLD : "#fff");
  const msg = "TIME DOESN'T WAIT";
  txt(g, msg, w / 2, h - 110, 64, "#fff", "center", HEAVY, clamp((c.t - W(50, 0)) / 0.3));
  g.save();
  g.strokeStyle = RED;
  g.lineWidth = 10;
  g.beginPath();
  g.arc(w / 2, h / 2 - 20, 320, -Math.PI / 2, -Math.PI / 2 + c.t % 4 / 4 * Math.PI * 2);
  g.stroke();
  g.restore();
}, "countdown");
var finale = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#020a2a", "#000");
  radial(g, w / 2, h / 2, 700, BLUE, 0.7);
  starRing(g, w / 2, h / 2, 260, 26, GOLD, 1, c.t * 0.15);
  txt(g, "2031", w / 2, h / 2 - 10, 190 * (1 + 0.06 * c.pulse), "#fff");
  txt(g, "COMFORT ZONE \xB7 LIVE", w / 2, h - 70, 40, GOLD, "center", MONO);
}, "finale");
var danke = /* @__PURE__ */ __name((g, w, h, c) => {
  bg(g, w, h, "#000", "#000");
  radial(g, w / 2, h / 2, 640, GOLD, 0.25 + 0.15 * c.pulse);
  txt(g, "DANKE BR\xDCSSEL", w / 2, h / 2 - 40, 140 * easeOutBack(clamp(c.local / 0.6)), "#fff");
  txt(g, "SEE YOU IN 2031", w / 2, h / 2 + 90, 44, GOLD, "center", MONO, clamp((c.local - 0.8) / 0.5));
  starRing(g, w / 2, h / 2, 300, 14, GOLD, 0.6, -c.t * 0.1);
}, "danke");
export {
  agents,
  bubble,
  clock,
  committees,
  countdown,
  dance,
  danke,
  deck,
  departures,
  eq,
  finale,
  goldenGate,
  hey,
  intro,
  logo,
  maybeLater,
  menu,
  news,
  revolutions,
  rulebook,
  setApi,
  split,
  storm,
  sunrise,
  triad,
  windowSky,
  year2031
};
