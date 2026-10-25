// Plays the song and exposes smoothed frequency bands for the visuals.

export interface Bands {
  bass: number; // 0..1
  mid: number;
  high: number;
  level: number;
  beat: boolean; // true on the frame a bass hit is detected
  beatPulse: number; // decays from 1 after each beat
}

export class AudioEngine {
  readonly el: HTMLAudioElement;
  ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private data = new Uint8Array(0);
  private bassAvg = 0;
  private lastBeat = 0;
  readonly bands: Bands = { bass: 0, mid: 0, high: 0, level: 0, beat: false, beatPulse: 0 };

  constructor(src: string) {
    this.el = new Audio(src);
    this.el.preload = 'auto';
  }

  /** Must be called from a user gesture (browser autoplay rules). */
  async start(): Promise<void> {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      const source = this.ctx.createMediaElementSource(this.el);
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 1024;
      this.analyser.smoothingTimeConstant = 0.75;
      source.connect(this.analyser);
      this.analyser.connect(this.ctx.destination);
      this.data = new Uint8Array(this.analyser.frequencyBinCount);
    }
    await this.ctx.resume();
    await this.el.play();
  }

  // ---- render mode (MP4 export): analyse the decoded file at a given time ----
  private offline: Float32Array | null = null;
  private offlineRate = 48000;
  private smoothMag = new Float32Array(0);
  private win = new Float32Array(0);
  renderTime = 0;

  async loadOffline(src: string): Promise<void> {
    const buf = await (await fetch(src)).arrayBuffer();
    const ctx = new OfflineAudioContext(1, 1, 48000);
    const audio = await ctx.decodeAudioData(buf);
    const mono = new Float32Array(audio.length);
    for (let c = 0; c < audio.numberOfChannels; c++) {
      const d = audio.getChannelData(c);
      for (let i = 0; i < d.length; i++) mono[i] += d[i] / audio.numberOfChannels;
    }
    this.offline = mono;
    this.offlineRate = audio.sampleRate;
    this.data = new Uint8Array(512);
    this.smoothMag = new Float32Array(220);
    // Blackman window, same as the browser's AnalyserNode
    this.win = new Float32Array(1024).map((_, i) => {
      const x = (2 * Math.PI * i) / 1024;
      return 0.42 - 0.5 * Math.cos(x) + 0.08 * Math.cos(2 * x);
    });
  }

  /** Emulates AnalyserNode.getByteFrequencyData (fftSize 1024, smoothing 0.75) for bins 0..219. */
  private analyseOffline(t: number): void {
    const N = 1024;
    const src = this.offline!;
    const end = Math.floor(t * this.offlineRate);
    const frame = new Float32Array(N);
    for (let i = 0; i < N; i++) {
      const k = end - N + i;
      frame[i] = k >= 0 && k < src.length ? src[k] * this.win[i] : 0;
    }
    for (let bin = 0; bin < 220; bin++) {
      let re = 0;
      let im = 0;
      const w = (2 * Math.PI * bin) / N;
      for (let i = 0; i < N; i++) {
        re += frame[i] * Math.cos(w * i);
        im -= frame[i] * Math.sin(w * i);
      }
      const mag = Math.sqrt(re * re + im * im) / N;
      this.smoothMag[bin] = 0.75 * this.smoothMag[bin] + 0.25 * mag;
      const db = 20 * Math.log10(this.smoothMag[bin] + 1e-12);
      this.data[bin] = Math.max(0, Math.min(255, Math.round((255 * (db + 100)) / 70)));
    }
  }

  get time(): number {
    return this.offline ? this.renderTime : this.el.currentTime;
  }

  get duration(): number {
    return Number.isFinite(this.el.duration) ? this.el.duration : 194;
  }

  get playing(): boolean {
    if (this.offline) return true;
    return !this.el.paused && !this.el.ended;
  }

  toggle(): void {
    if (this.el.paused) void this.start();
    else this.el.pause();
  }

  seek(t: number): void {
    this.el.currentTime = Math.max(0, Math.min(this.duration - 0.05, t));
  }

  update(dt: number): Bands {
    const b = this.bands;
    b.beat = false;
    if (this.analyser || this.offline) {
      if (this.offline) this.analyseOffline(this.renderTime);
      else this.analyser!.getByteFrequencyData(this.data);
      // ~47 Hz per bin at 48 kHz / 1024
      const avg = (a: number, z: number) => {
        let s = 0;
        for (let i = a; i < z; i++) s += this.data[i];
        return s / ((z - a) * 255);
      };
      const bass = avg(1, 6);
      const mid = avg(6, 60);
      const high = avg(60, 220);
      const k = 1 - Math.exp(-dt * 18);
      b.bass += (bass - b.bass) * k;
      b.mid += (mid - b.mid) * k;
      b.high += (high - b.high) * k;
      b.level = (b.bass + b.mid + b.high) / 3;

      this.bassAvg += (bass - this.bassAvg) * (1 - Math.exp(-dt * 2));
      const now = this.time;
      if (this.playing && bass > this.bassAvg * 1.18 && bass > 0.35 && now - this.lastBeat > 0.28) {
        b.beat = true;
        this.lastBeat = now;
        b.beatPulse = 1;
      }
    }
    b.beatPulse = Math.max(0, b.beatPulse - dt * 3.5);
    return b;
  }

}
