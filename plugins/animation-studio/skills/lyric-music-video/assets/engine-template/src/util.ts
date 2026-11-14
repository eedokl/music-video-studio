// Small helpers shared by all scenes. Everything is driven by song time (no CSS timers),
// so the frame-by-frame MP4 export looks exactly like live playback.

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
/** 0..1 progress of t between a and b */
export const prog = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp(x), 3);
export const easeInOut = (x: number) => {
  x = clamp(x);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};
export const easeOutBack = (x: number) => {
  x = clamp(x);
  const c1 = 1.9;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
};
export const hash = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

export function mk<K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', parent?: HTMLElement, text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  parent?.appendChild(e);
  return e;
}

/** Pop-in: returns scale/opacity for something appearing at time a. */
export function popIn(t: number, a: number, dur = 0.35) {
  const x = prog(t, a, a + dur);
  return { s: x <= 0 ? 0 : easeOutBack(x), o: clamp(x * 3) };
}

export function show(el: HTMLElement, visible: boolean) {
  el.style.visibility = visible ? 'visible' : 'hidden';
}

/** Apply a pop-in (and optional slide) to an element. */
export function popStyle(el: HTMLElement, t: number, a: number, dy = 0, dur = 0.35) {
  const p = popIn(t, a, dur);
  el.style.opacity = p.o.toFixed(3);
  el.style.transform = `translateY(${((1 - p.o) * dy).toFixed(1)}px) scale(${(0.6 + 0.4 * p.s).toFixed(4)})`;
}

/** Fade + slide in from below at time a (for UI rows). */
export function slideIn(el: HTMLElement, t: number, a: number, dy = 18, dur = 0.3) {
  const x = easeOut(prog(t, a, a + dur));
  el.style.opacity = x.toFixed(3);
  el.style.transform = `translateY(${((1 - x) * dy).toFixed(1)}px)`;
}

/** Typewriter: first n characters of s at progress x. */
export const typed = (s: string, x: number) => s.slice(0, Math.round(clamp(x) * s.length));
