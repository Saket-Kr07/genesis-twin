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

// Accepts the shapes the backend might send: {organs:{...}}, {heart:{...}}, or [{organ, score, vitals}].
function normalize(json) {
  let raw = json?.organs ?? json;
  if (Array.isArray(raw)) raw = Object.fromEntries(raw.map((o) => [o.organ ?? o.id, o]));
  const out = {};
  for (const [id, v] of Object.entries(raw || {})) {
    if (v == null || typeof v.score !== 'number') continue;
    let vitals = v.vitals ?? [];
    if (!Array.isArray(vitals)) vitals = Object.entries(vitals).map(([name, value]) => ({ name, value }));
    out[id] = { score: v.score, vitals };
  }
  return out;
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
