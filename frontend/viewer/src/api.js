import { API_BASE, ORGANS } from './config.js';

// Calls Rakhi's POST /twin/predict. If the API is down, falls back to a dummy formula
// with the same output shape, so the viewer always works.
//   input:  { age, sex, sleep, exercise, smoking, diet }
//   output: { [organId]: { score: 0-100, vitals: [{ name, value }] } }

export async function predictHealth(params) {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch(`${API_BASE}/twin/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: ctrl.signal,
    });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = normalize(await res.json());
    if (!Object.keys(data).length) throw new Error('empty');
    return { data, source: 'api' };
  } catch {
    return { data: dummyPredict(params), source: 'dummy' };
  }
}

// Vitals may come as [{name, value}] or as {name: value}.
export function normalizeVitals(v) {
  if (!v) return [];
  if (Array.isArray(v)) return v.map((x) => ({ name: x.name ?? x.label ?? '', value: x.value ?? '' }));
  return Object.entries(v).map(([name, value]) => ({ name, value: typeof value === 'number' ? Number(value.toFixed(2)) : value }));
}

// Accepts the shapes the backend might send: {organs:{...}}, {heart:{...}}, or [{organ, score, vitals}].
function normalize(json) {
  let raw = json?.organs ?? json;
  if (Array.isArray(raw)) raw = Object.fromEntries(raw.map((o) => [o.organ ?? o.id, o]));
  const out = {};
  for (const [id, v] of Object.entries(raw || {})) {
    if (v == null || typeof v.score !== 'number') continue;
    out[id] = { score: v.score, vitals: normalizeVitals(v.vitals) };
  }
  return out;
}

// ---------------------------------------------------------------
// Infection timeline: POST /pathogens/timeline
//   body: { pathogen_id, day, treatment, treatment_start }
//   response: { times[121], scores{organ: [121]}, load[121], days[31]{organs{organ:{score,status,vitals}}}, model_version }
// ---------------------------------------------------------------
export const PATHOGENS = [
  { id: 'respiratory_virus', label: 'Respiratory virus' },
  { id: 'gut_virus', label: 'Gut virus' },
  { id: 'bloodstream_bacterium', label: 'Bloodstream bacterium' },
];

export async function fetchTimeline({ pathogen, treatment, treatmentStart }) {
  try {
    const res = await fetch(`${API_BASE}/pathogens/timeline`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pathogen_id: pathogen, day: 0, treatment, treatment_start: treatmentStart }),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    if (!data?.scores || !data?.days) throw new Error('bad shape');
    return { data, source: 'api' };
  } catch {
    return { data: dummyTimeline({ pathogen, treatment, treatmentStart }), source: 'dummy' };
  }
}

// What the viewer shows on a given (fractional) day.
export function timelineAt(tl, day) {
  const i = Math.max(0, Math.min((tl.times?.length ?? 121) - 1, Math.round(day * 4)));
  const d = tl.days[Math.max(0, Math.min(tl.days.length - 1, Math.floor(day)))];
  const out = {};
  for (const [id, list] of Object.entries(tl.scores)) {
    const score = list[i];
    if (typeof score !== 'number') continue;
    const damage = (100 - score) / 100;
    out[id] = {
      score,
      glow: 0.15 + 0.85 * damage, // brighter the more damaged
      status: d?.organs?.[id]?.status,
      vitals: normalizeVitals(d?.organs?.[id]?.vitals),
    };
  }
  return { organs: out, load: tl.load?.[i] };
}

// Offline stand-in with the same shape, so the animation can be built before the API is up.
function dummyTimeline({ pathogen, treatment, treatmentStart }) {
  const spread = {
    respiratory_virus: { lungs: [0, 0.85], heart: [5, 0.35], brain: [9, 0.2], kidneys: [8, 0.25] },
    gut_virus: { intestines: [0, 0.8], stomach: [1, 0.6], liver: [5, 0.4], kidneys: [7, 0.3] },
    bloodstream_bacterium: { heart: [1, 0.6], kidneys: [2, 0.7], liver: [3, 0.55], spleen: [1, 0.6], lungs: [4, 0.45], brain: [6, 0.35] },
  }[pathogen] ?? {};
  const times = Array.from({ length: 121 }, (_, k) => k * 0.25);
  const sev = (t, [onset, max]) => {
    if (t < onset) return 0;
    const x = t - onset;
    let s = max * (1 - Math.exp(-x / 3)) * Math.exp(-Math.max(0, x - 8) / 10);
    if (treatment > 0 && t > treatmentStart) s *= Math.exp(-(t - treatmentStart) * 0.25 * treatment);
    return s;
  };
  const scores = {};
  for (const o of ORGANS) scores[o.id] = times.map((t) => Number((100 - 100 * (spread[o.id] ? sev(t, spread[o.id]) : 0)).toFixed(1)));
  const load = times.map((t) => Math.max(...Object.values(spread).map((p) => sev(t, p))) * 100);
  const days = Array.from({ length: 31 }, (_, d) => ({
    day: d,
    organs: Object.fromEntries(ORGANS.map((o) => {
      const s = scores[o.id][d * 4];
      return [o.id, { score: s, status: s >= 80 ? 'healthy' : s >= 50 ? 'stressed' : 'critical', vitals: { 'Tissue damage': `${(100 - s).toFixed(0)} %` } }];
    })),
  }));
  return { times, scores, load, days, model_version: 'dummy' };
}

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const r = (x, d = 0) => Number(x.toFixed(d));

export function dummyPredict({ age = 30, sex = 'male', sleep = 7, exercise = 3, smoking = 0, diet = 3 }) {
  const base = 92 - (age - 20) * 0.45 - Math.abs(sleep - 7.5) * 3 + exercise * 1.2 + (diet - 3) * 2.5;
  const w = {
    lungs: smoking * 2.2, heart: smoking * 1.3, brain: smoking * 0.4, liver: smoking * 0.3,
    kidneys: smoking * 0.4, bladder: smoking * 0.5, pancreas: smoking * 0.4,
  };
  const out = {};
  for (const o of ORGANS) {
    const score = clamp(r(base - (w[o.id] ?? 0.2 * smoking)), 5, 100);
    const bad = (100 - score) / 100;
    const v = {
      heart: [['Heart rate', `${r(62 + bad * 30)} bpm`], ['Blood pressure', `${r(112 + bad * 40)}/${r(72 + bad * 20)} mmHg`], ['Ejection fraction', `${r(65 - bad * 25)} %`]],
      lungs: [['Oxygen saturation', `${r(99 - bad * 8)} %`], ['Breathing rate', `${r(13 + bad * 8)} /min`], ['Lung capacity', `${r((sex === 'male' ? 6 : 4.4) * (1 - bad * 0.4), 1)} L`]],
      brain: [['Neuro-inflammation index', r(bad * 10, 1)], ['Reaction score', r(100 - bad * 40)]],
      liver: [['ALT', `${r(20 + bad * 50)} U/L`], ['AST', `${r(20 + bad * 40)} U/L`], ['Bilirubin', `${r(0.6 + bad * 1.5, 1)} mg/dL`]],
      stomach: [['Gut inflammation', r(bad * 10, 1)]],
      intestines: [['Gut inflammation', r(bad * 10, 1)]],
      kidneys: [['eGFR', `${r(110 - bad * 60)} mL/min`], ['Creatinine', `${r(0.8 + bad * 1.2, 2)} mg/dL`], ['Hydration', `${r(95 - bad * 25)} %`]],
      bladder: [['Hydration', `${r(95 - bad * 25)} %`]],
      pancreas: [['Glucose', `${r(88 + bad * 60)} mg/dL`]],
      spleen: [['White cell count', `${r(6.5 + bad * 5, 1)} x10^9/L`], ['Cytokine level', r(bad * 10, 1)]],
      thyroid: [['TSH', `${r(1.8 + bad * 3, 1)} mIU/L`]],
      reproductive: [['Hormone indicator', r(100 - bad * 50)]],
    }[o.id] ?? [];
    out[o.id] = { score, vitals: v.map(([name, value]) => ({ name, value })) };
  }
  return out;
}
