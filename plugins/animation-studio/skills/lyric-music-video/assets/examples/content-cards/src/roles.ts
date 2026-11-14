// The 15 roles of the content page (fictional space-station crew: texts, quotes, families, stages,
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

// display colours (a little brighter than the family colours so they glow on the dark stage)
const GLOW: Record<string, string> = { product: '#b46fd6', dsp: '#3fa0ee', ai: '#3fd0c8', sw: '#5b8fd6', quality: '#45c47e' };
export const glow = (family: string) => GLOW[family] ?? '#2fa3e6';

export const img = (file: string) => `${import.meta.env.BASE_URL}roles/${file}`;

export function role(name: string): Role {
  const r = D.roles.find((x) => x.name.replace(/\s+/g, ' ') === name || x.name.startsWith(name));
  if (!r) throw new Error(`unknown role ${name}`);
  return r;
}

/** lyric line → role, in the order the song sings them */
export const SUNG: [number, string, string][] = [
  [3, 'Radio Operator', 'Radio Operator'],
  [4, 'Power Engineer', 'Power Engineer'],
  [5, 'Water Recycler', 'Water Recycler'],
  [6, 'Rover Robotics Engineer', 'Rover Robotics'],
  [7, 'Flight Software Engineer', 'Flight Software'],
  [8, 'Station Architect', 'Station Architect'],
  [19, 'Habitat Designer', 'Habitat Designer'],
  [20, 'Research Lead', 'Research Lead'],
  [21, 'Greenhouse Lead', 'Greenhouse Lead'],
  [22, 'Safety Officer', 'Safety Officer'],
  [23, 'Night Inspector', 'Night Inspector'],
  [24, 'Station Machinist', 'Machinist'],
  [25, 'Life-Support Manager', 'Life Support'],
  [36, 'Mission Commander', 'Commander'],
  [37, 'Crew Coach', 'Crew Coach'],
];
export const ROLE_ORDER = SUNG.map(([, n]) => role(n));
