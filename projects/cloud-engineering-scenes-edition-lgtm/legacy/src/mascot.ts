// NIMBUS-01: a pixel-art cloud robot, the platform team's tireless teammate.

const SHAPE = [
  '....####....',
  '..########..',
  '.##########.',
  '############',
  '############',
  '.##########.',
];
const NS = 'http://www.w3.org/2000/svg';

export type Mood = 'idle' | 'happy' | 'shrug' | 'sad' | 'alarm';

export class Mascot {
  readonly el: SVGSVGElement;
  private body: SVGGElement;
  private eyes: SVGRectElement[] = [];
  private armL: SVGRectElement;
  private armR: SVGRectElement;
  private legs: SVGRectElement[] = [];
  private mouth: SVGRectElement;

  constructor(parent: HTMLElement, px = 14, color = '#4aa3ff') {
    this.el = document.createElementNS(NS, 'svg');
    this.el.setAttribute('viewBox', '-3 -2 18 12');
    this.el.setAttribute('class', 'mascot');
    this.el.style.width = `${18 * px}px`;
    this.el.style.height = `${12 * px}px`;
    this.body = document.createElementNS(NS, 'g');
    this.el.appendChild(this.body);
    const rect = (x: number, y: number, w: number, h: number, fill: string, parentG: Element = this.body) => {
      const r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', String(x));
      r.setAttribute('y', String(y));
      r.setAttribute('width', String(w));
      r.setAttribute('height', String(h));
      r.setAttribute('fill', fill);
      parentG.appendChild(r);
      return r;
    };
    SHAPE.forEach((row, y) => [...row].forEach((c, x) => c === '#' && rect(x, y, 1.02, 1.02, color)));
    this.eyes = [rect(3.5, 2.5, 1, 1.6, '#0b1020'), rect(7.5, 2.5, 1, 1.6, '#0b1020')];
    this.mouth = rect(5, 4.6, 2, 0.4, '#0b1020');
    this.armL = rect(-1.6, 3.2, 1.6, 0.6, color);
    this.armR = rect(12, 3.2, 1.6, 0.6, color);
    this.legs = [3, 5, 7, 9].map((x) => rect(x - 0.5, 6, 0.8, 1.6, color));
    parent.appendChild(this.el);
  }

  update(t: number, beat: number, mood: Mood = 'idle') {
    const ph = beat - Math.floor(beat);
    const bob = Math.abs(Math.sin(ph * Math.PI)) * 0.35;
    this.body.setAttribute('transform', `translate(0 ${(-bob).toFixed(3)})`);
    const blink = (t * 0.7) % 4 < 0.12;
    const eyeH = mood === 'happy' ? 0.5 : blink ? 0.2 : mood === 'alarm' ? 2 : 1.6;
    this.eyes.forEach((e) => {
      e.setAttribute('height', String(eyeH));
      e.setAttribute('y', String(mood === 'happy' ? 3 : 2.5 + (1.6 - eyeH) / 2));
    });
    this.mouth.setAttribute('width', mood === 'alarm' ? '1' : mood === 'sad' ? '2' : '2');
    this.mouth.setAttribute('y', mood === 'sad' ? '5' : '4.6');
    // arms
    const wave = Math.sin(t * 8) * 25;
    const up = mood === 'shrug' || mood === 'alarm' ? -55 : mood === 'happy' ? -35 + wave : Math.sin(beat * Math.PI) * 12;
    this.armL.setAttribute('transform', `rotate(${(-up).toFixed(1)} 0 3.5)`);
    this.armR.setAttribute('transform', `rotate(${up.toFixed(1)} 12 3.5)`);
    // legs step on the beat
    this.legs.forEach((l, i) => l.setAttribute('height', String(1.6 + ((Math.floor(beat) + i) % 2 ? 0.25 : -0.1))));
  }
}
