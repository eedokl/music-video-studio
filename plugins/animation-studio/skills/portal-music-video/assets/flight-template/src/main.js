// Live player: the flight follows the song (after its end it starts again).
//   click / Space = play, pause     arrow keys = 2 s back / forward     F = fullscreen
//   ?t=12.3  start there (seconds of the excerpt)      ?render=1  frame-exact mode for a later MP4 render
import { Engine } from './engine.js';
import { FLAT, MONO } from './kit.js';
import { FROM } from './song.js';

const params = new URLSearchParams(location.search);
const RENDER = params.has('render');
if (RENDER) document.body.classList.add('render');
const $ = (id) => document.getElementById(id);

await Promise.all([FLAT, MONO].map((f) => document.fonts.load(f).catch(() => null)));
await document.fonts.ready;

const engine = new Engine($('gl'), $('glow'));
window.addEventListener('resize', () => engine.resize());
const hud = $('hud');
window.__engine = engine; // for checks from the console
engine.warmUp();

if (RENDER) {
  window.__renderFrame = (t) => ($('label').textContent = engine.frame(t).label);
  window.__duration = engine.total;
  engine.frame(0);
  window.__ready = true;
} else {
  // Sound through Web Audio: the song is one buffer, the film's clock follows the sound's clock.
  const startEl = $('start');
  let ctx = null, buffer = null, source = null, anchor = 0; // anchor = context time at which the excerpt was at 0
  let started = false, loading = false;
  const wrap = (t) => ((t % engine.total) + engine.total) % engine.total;
  // where the sound is, at the moment `stamp` (a performance.now() time)
  const soundAt = (stamp) => {
    const ts = ctx.getOutputTimestamp?.();
    const t = ts && ts.performanceTime ? ts.contextTime + (stamp - ts.performanceTime) / 1000 : ctx.currentTime;
    return wrap(t - anchor);
  };
  const now = () => soundAt(performance.now());
  // The picture's clock runs on the screen's own frame times, which are perfectly even. The sound's clock is
  // only read to keep the two together: small differences are averaged out slowly, a seek re-anchors.
  let film0 = null; // frame time at which the film was at second 0
  const filmAt = (stamp) => {
    const s = soundAt(stamp);
    if (film0 === null) film0 = stamp - s * 1000;
    let err = s - wrap((stamp - film0) / 1000);
    if (err > engine.total / 2) err -= engine.total;
    if (err < -engine.total / 2) err += engine.total;
    if (Math.abs(err) > 0.08) film0 = stamp - s * 1000;
    else film0 -= err * 1000 * 0.01;
    return wrap((stamp - film0) / 1000);
  };
  const playFrom = (sec) => {
    source?.stop();
    source = ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.loopStart = 0;
    source.loopEnd = Math.min(engine.total, buffer.duration);
    source.connect(ctx.destination);
    const at = ctx.currentTime + 0.05;
    source.start(at, sec);
    anchor = at - sec;
    film0 = null;
  };
  const begin = async () => {
    if (loading) return;
    loading = true;
    startEl.textContent = 'loading the song …';
    ctx = new AudioContext();
    buffer = await ctx.decodeAudioData(await (await fetch('./public/song.wav')).arrayBuffer());
    playFrom(Number(params.get('t') ?? 0) % engine.total);
    started = true;
    startEl.classList.add('gone');
  };
  const toggle = () => (!started ? void begin() : ctx.state === 'running' ? void ctx.suspend() : void ctx.resume());
  const seek = (d) => started && playFrom((((now() + d) % engine.total) + engine.total) % engine.total);
  startEl.addEventListener('click', toggle);
  $('stage').addEventListener('click', (e) => e.target !== startEl && toggle());
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space') e.preventDefault(), toggle();
    if (e.code === 'ArrowRight') seek(2);
    if (e.code === 'ArrowLeft') seek(-2);
    if (e.code === 'KeyF') void document.documentElement.requestFullscreen?.();
  });
  // for checks from outside: draw one frame and hold it
  let held = null;
  window.__hold = (t) => (held = t);
  window.__audio = () => ({ state: ctx?.state, t: started ? now() : null, loopEnd: source?.loopEnd, bufferSeconds: buffer?.duration });

  let demo = 0, last = performance.now();
  const loop = (stamp) => {
    const dt = Math.min(0.1, (stamp - last) / 1000);
    last = stamp;
    const t = held !== null ? held : started ? (ctx.state === 'running' ? filmAt(stamp) : now()) : (demo = (demo + dt) % engine.total); // silent demo run behind the start card
    const info = engine.frame(t);
    $('label').textContent = info.label;
    hud.textContent = `${info.world}  ·  song ${(FROM + t).toFixed(1)} s  ·  bar ${Math.floor(info.beat / 4) + 1}.${(Math.floor(info.beat) % 4) + 1}  ·  ${t.toFixed(1)} s / ${engine.total.toFixed(1)} s`;
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
