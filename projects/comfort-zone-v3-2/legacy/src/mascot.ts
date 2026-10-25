// AZZY: a soft, round cloud with a face – the platform team's buddy.

const NS = 'http://www.w3.org/2000/svg';
export type Mood = 'idle' | 'happy' | 'shrug' | 'sad' | 'alarm';

export class Mascot {
  readonly el: SVGSVGElement;
  private body: SVGGElement;
  private eyes: SVGEllipseElement[] = [];
  private mouth: SVGPathElement;
  private armL: SVGPathElement;
  private armR: SVGPathElement;
  private sweat: SVGPathElement;

  constructor(parent: HTMLElement, px = 14, _color = '#ffffff') {
    this.el = document.createElementNS(NS, 'svg');
    this.el.setAttribute('viewBox', '0 0 220 150');
    this.el.setAttribute('class', 'mascot');
    this.el.style.width = `${18 * px}px`;
    this.el.style.height = `${12.3 * px}px`;
    this.el.innerHTML = `
      <defs>
        <linearGradient id="azg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#cfe6ff"/></linearGradient>
      </defs>
      <ellipse cx="110" cy="142" rx="62" ry="6" fill="rgba(0,20,60,0.25)"/>
      <g class="az-body">
        <path class="az-arm-l" d="M42 92 q-26 -6 -30 -26" stroke="#cfe6ff" stroke-width="10" stroke-linecap="round" fill="none"/>
        <path class="az-arm-r" d="M178 92 q26 -6 30 -26" stroke="#cfe6ff" stroke-width="10" stroke-linecap="round" fill="none"/>
        <path d="M58 122 h104 a34 34 0 0 0 4 -67 a44 44 0 0 0 -84 -10 a32 32 0 0 0 -24 77 z" fill="url(#azg)" stroke="#9cc8ff" stroke-width="3"/>
        <ellipse class="az-eye" cx="92" cy="84" rx="6.5" ry="9" fill="#0b2a5c"/>
        <ellipse class="az-eye" cx="130" cy="84" rx="6.5" ry="9" fill="#0b2a5c"/>
        <ellipse cx="78" cy="100" rx="8" ry="5" fill="#ff9e8a" opacity="0.7"/>
        <ellipse cx="144" cy="100" rx="8" ry="5" fill="#ff9e8a" opacity="0.7"/>
        <path class="az-mouth" d="M100 102 q11 10 22 0" stroke="#0b2a5c" stroke-width="4" stroke-linecap="round" fill="none"/>
        <path class="az-sweat" d="M160 52 q6 10 0 14 q-6 -4 0 -14 z" fill="#7fd0ff"/>
      </g>`;
    parent.appendChild(this.el);
    this.body = this.el.querySelector('.az-body')!;
    this.eyes = [...this.el.querySelectorAll<SVGEllipseElement>('.az-eye')];
    this.mouth = this.el.querySelector('.az-mouth')!;
    this.armL = this.el.querySelector('.az-arm-l')!;
    this.armR = this.el.querySelector('.az-arm-r')!;
    this.sweat = this.el.querySelector('.az-sweat')!;
  }

  update(t: number, beat: number, mood: Mood = 'idle') {
    const ph = beat - Math.floor(beat);
    const squash = 1 - Math.exp(-ph * 6) * 0.06;
    const hop = Math.abs(Math.sin(ph * Math.PI)) * 5;
    this.body.setAttribute('transform', `translate(110 122) scale(${(2 - squash).toFixed(3)} ${squash.toFixed(3)}) translate(-110 ${(-122 - hop).toFixed(2)})`);
    const blink = (t * 0.8) % 3.5 < 0.12;
    this.eyes.forEach((e) => {
      e.setAttribute('ry', blink ? '1.5' : mood === 'alarm' ? '11' : mood === 'happy' ? '5' : '9');
    });
    const mouths: Record<Mood, string> = {
      idle: 'M100 102 q11 10 22 0',
      happy: 'M96 100 q15 18 30 0',
      shrug: 'M100 106 h22',
      sad: 'M100 108 q11 -10 22 0',
      alarm: 'M104 104 a7 7 0 1 0 14 0 a7 7 0 1 0 -14 0',
    };
    this.mouth.setAttribute('d', mouths[mood]);
    const wave = Math.sin(t * 9) * 14;
    const up = mood === 'shrug' || mood === 'alarm' ? 40 : mood === 'happy' ? 25 + wave : Math.sin(beat * Math.PI) * 10;
    this.armL.setAttribute('transform', `rotate(${up.toFixed(1)} 42 92)`);
    this.armR.setAttribute('transform', `rotate(${(-up).toFixed(1)} 178 92)`);
    this.sweat.style.opacity = mood === 'alarm' || mood === 'shrug' ? '1' : '0';
  }
}
