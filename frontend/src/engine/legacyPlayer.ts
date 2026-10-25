// Preview for an imported video engine ("legacy world"): the original engine runs as its own page
// (projects/<id>/legacy/index.html) in an iframe, so its CSS (vw units), fonts and 3D stay exactly
// as they were. The studio drives it: __renderFrame(t) per frame, __update(project) after edits;
// a new build (project.legacy.built) reloads the page.
import type { Project } from '../types';
import { Timing } from './timing';

export interface Preview {
  timing: Timing;
  setProject(p: Project, bust?: string): Promise<void>;
  renderAt(t: number): void;
  resize(w: number, h: number): void;
  sceneAt(t: number): ReturnType<Timing['sceneAt']>;
}

type LegacyWin = Window & { __ready?: boolean; __renderFrame?: (t: number) => void; __update?: (p: unknown) => void; __duration?: number };

export class LegacyPlayer implements Preview {
  timing!: Timing;
  readonly iframe: HTMLIFrameElement;
  private ready = false;
  private built = -1;
  private loading: Promise<void> | null = null;

  constructor(root: HTMLElement, private pid: string, private render = false) {
    root.classList.add('mv-player');
    this.iframe = document.createElement('iframe');
    this.iframe.className = 'legacy-frame';
    this.iframe.tabIndex = -1;
    root.appendChild(this.iframe);
  }

  private get win() {
    return this.iframe.contentWindow as LegacyWin | null;
  }

  private load(built: number) {
    this.ready = false;
    this.built = built;
    this.iframe.src = `/api/projects/${this.pid}/files/legacy/index.html?project=${this.pid}&v=${built}${this.render ? '&render=1' : ''}`;
    this.loading = new Promise((res, rej) => {
      const t0 = performance.now();
      const poll = () => {
        if (this.win?.__ready) {
          this.ready = true;
          res();
        } else if (performance.now() - t0 > 60000) rej(new Error('legacy engine did not start'));
        else setTimeout(poll, 50);
      };
      setTimeout(poll, 100);
    });
    return this.loading;
  }

  async setProject(p: Project) {
    this.timing = new Timing(p);
    const built = p.legacy?.built ?? 0;
    if (built !== this.built) await this.load(built);
    else if (this.loading) await this.loading;
    // the page loaded the saved project – hand it the editor's current state
    this.win?.__update?.(JSON.parse(JSON.stringify(p)));
  }

  renderAt(t: number) {
    if (this.ready) this.win?.__renderFrame?.(t);
  }

  resize() {
    /* the iframe fills the stage; the engine resizes itself */
  }

  sceneAt(t: number) {
    return this.timing?.sceneAt(t) ?? null;
  }
}
