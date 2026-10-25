// The 15 roles of BST/ESW (taken from the "BST/ESW Roles" page: texts, quotes, families, stages,
// icons and illustrations). The song names them in this order.

import data from './roles.json';

export interface Role {
  name: string;
  summary: string;
  quote: string;
  icon: string;
  illustration: string;
  family: string;
  stages: string[];
  tasks: string[];
  competence: string[];
}
export interface Family {
  label: string;
  color: string;
}

const D = data as { families: Record<string, Family>; stages: { id: string; label: string; text: string }[]; roles: Role[] };

export const FAMILIES = D.families;
export const STAGES = D.stages;
export const ALL_ROLES = D.roles;

// display colours (a little brighter than the brand colours so they glow on the dark stage)
const GLOW: Record<string, string> = { product: '#c651bd', dsp: '#2fa3e6', ai: '#3fd0c8', sw: '#5b8fd6', quality: '#35c27a' };
export const glow = (family: string) => GLOW[family] ?? '#2fa3e6';

export const img = (file: string) => `${import.meta.env.BASE_URL}roles/${file}`;

export function role(name: string): Role {
  const r = D.roles.find((x) => x.name.replace(/\s+/g, ' ') === name || x.name.startsWith(name));
  if (!r) throw new Error(`unknown role ${name}`);
  return r;
}

/** lyric line → role, in the order the song sings them */
export const SUNG: [number, string, string][] = [
  [3, 'DSP Engineer', 'DSP Engineer'],
  [4, 'DSP Embedded Engineer', 'DSP Embedded'],
  [5, 'DSP Data Operations Engineer', 'Data Ops'],
  [6, 'Embedded AI Engineer', 'Embedded AI Engineer'],
  [7, 'Computer Science Engineer', 'CS Engineer, Embedded AI'],
  [8, 'Embedded AI Software Architect', 'AI Architect'],
  [19, 'Software Architect', 'Software Architect'],
  [20, 'Computer Science Expert', 'CS Expert'],
  [21, 'Algorithm Technical Lead', 'Algorithm Lead'],
  [22, 'Software Test Automation Architect', 'Test Architect'],
  [23, 'Software Test Automation Engineer', 'Test Engineer'],
  [24, 'Software Tool and Application Engineer', 'Tool Engineer'],
  [25, 'Software IT Manager', 'IT Manager'],
  [36, 'Product Owner', 'Product Owner'],
  [37, 'Agile Master', 'Agile Master'],
];
export const ROLE_ORDER = SUNG.map(([, n]) => role(n));
