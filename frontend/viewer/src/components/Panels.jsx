import React, { useMemo, useState } from 'react';
import { SYSTEMS, ORGAN_INFO, ORGANS, CREDITS } from '../config.js';
import { allMeshes, scoreColor } from '../registry.js';

const SYSTEM_LABEL = Object.fromEntries(SYSTEMS.map((s) => [s.id, s.label]));
const ORGAN_LABEL = Object.fromEntries(ORGANS.map((o) => [o.id, o.label]));

export function LayersPanel({ layers, setLayers, counts, sex, setSex, femaleFallback }) {
  const update = (id, patch) => setLayers((L) => ({ ...L, [id]: { ...L[id], ...patch } }));
  return (
    <section className="panel">
      <h2>Body</h2>
      <div className="seg">
        {['male', 'female'].map((s) => (
          <button key={s} className={sex === s ? 'active' : ''} onClick={() => setSex(s)}>
            {s === 'male' ? 'Male' : 'Female'}
          </button>
        ))}
      </div>
      {femaleFallback && <p className="note">No female model found yet, so male meshes are shown.</p>}

      <h2>Layers</h2>
      {SYSTEMS.filter((s) => s.id !== 'other' || counts.other).map((s) => (
        <div className="layer" key={s.id}>
          <label className="layer-head">
            <input type="checkbox" checked={layers[s.id].on} onChange={(e) => update(s.id, { on: e.target.checked })} />
            <span>{s.label}</span>
            <small>{counts[s.id] ? counts[s.id] : layers[s.id].on ? '–' : 'off'}</small>
          </label>
          <input
            type="range" min="0" max="1" step="0.05" value={layers[s.id].opacity}
            disabled={!layers[s.id].on}
            onChange={(e) => update(s.id, { opacity: Number(e.target.value) })}
            aria-label={`${s.label} opacity`}
          />
        </div>
      ))}
    </section>
  );
}

function Slider({ label, value, min, max, step = 1, unit = '', onChange }) {
  return (
    <label className="slider">
      <span>{label}<b>{value}{unit}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

export function LifestylePanel({ life, setLife, source }) {
  const set = (k) => (v) => setLife((l) => ({ ...l, [k]: v }));
  return (
    <section className="panel">
      <h2>Lifestyle</h2>
      <Slider label="Age" value={life.age} min={20} max={80} unit=" y" onChange={set('age')} />
      <Slider label="Sleep" value={life.sleep} min={3} max={10} step={0.5} unit=" h" onChange={set('sleep')} />
      <Slider label="Exercise" value={life.exercise} min={0} max={7} unit=" d/wk" onChange={set('exercise')} />
      <Slider label="Smoking" value={life.smoking} min={0} max={40} unit="/day" onChange={set('smoking')} />
      <Slider label="Diet quality" value={life.diet} min={1} max={5} unit="/5" onChange={set('diet')} />
      <p className="note">
        Data: {source === 'api' ? 'live model API' : source === 'dummy' ? 'dummy values (API offline)' : 'loading…'}
      </p>
    </section>
  );
}

export function BodyShapePanel({ shape, setShape }) {
  const set = (k) => (v) => setShape((s) => ({ ...s, [k]: v }));
  const bmi = shape.weight / Math.pow(shape.height / 100, 2);
  return (
    <section className="panel">
      <h2>Body shape</h2>
      <Slider label="Height" value={shape.height} min={140} max={205} unit=" cm" onChange={set('height')} />
      <Slider label="Weight" value={shape.weight} min={40} max={140} unit=" kg" onChange={set('weight')} />
      <p className="note">BMI {bmi.toFixed(1)} · organs scale with the body</p>
    </section>
  );
}

export function InfectionPanel({ inf, setInf, day, setDay, playing, setPlaying, source, load, pathogens }) {
  const set = (k) => (v) => setInf((s) => ({ ...s, [k]: v }));
  return (
    <section className="panel">
      <h2>Infection</h2>
      <label className="layer-head">
        <input type="checkbox" checked={inf.on} onChange={(e) => setInf((s) => ({ ...s, on: e.target.checked }))} />
        <span>Simulate infection</span>
      </label>
      {inf.on && (
        <>
          <select className="select" value={inf.pathogen} onChange={(e) => set('pathogen')(e.target.value)}>
            {pathogens.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <Slider label="Treatment" value={inf.treatment} min={0} max={1} step={0.1} onChange={set('treatment')} />
          <Slider label="Treatment starts" value={inf.treatmentStart} min={0} max={30} unit=" d" onChange={set('treatmentStart')} />
          <div className="day-row">
            <button onClick={() => { if (day >= 30) setDay(0); setPlaying((p) => !p); }}>{playing ? 'Pause' : 'Play'}</button>
            <Slider label="Day" value={day} min={0} max={30} step={0.25} onChange={(v) => { setPlaying(false); setDay(v); }} />
          </div>
          <p className="note">
            {typeof load === 'number' ? `Pathogen load ${load.toFixed(1)} · ` : ''}
            Data: {source === 'api' ? 'live model API' : source === 'dummy' ? 'dummy (API offline)' : 'loading…'}
          </p>
        </>
      )}
    </section>
  );
}

export function InfoPanel({ mesh, health, onClose }) {
  if (!mesh) return null;
  const g = mesh.userData.gt;
  const h = g.organ ? health[g.organ] : null;
  return (
    <aside className="panel info">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h3>{g.pretty}</h3>
      <p className="muted">{SYSTEM_LABEL[g.system] ?? g.system} system{g.organ ? ` · ${ORGAN_LABEL[g.organ]}` : ''}</p>
      <code className="mesh-id">{g.id}</code>
      {h ? (
        <>
          <div className="score">
            <span className="dot" style={{ background: `#${scoreColor(h.score).getHexString()}` }} />
            Health score <b>{Math.round(h.score)}</b>/100
            {h.status && <span className="status">{h.status}</span>}
          </div>
          <table>
            <tbody>
              {h.vitals.map((v) => (
                <tr key={v.name}><td>{v.name}</td><td>{String(v.value)}</td></tr>
              ))}
            </tbody>
          </table>
          <p>{ORGAN_INFO[g.organ]}</p>
        </>
      ) : (
        <p className="muted">Vitals are simulated for the 12 main organs. This structure has none.</p>
      )}
      <p className="tiny">Simulated model output, not a measurement.</p>
    </aside>
  );
}

export function SearchBox({ version, onFound }) {
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const names = useMemo(() => [...new Set(allMeshes().map((m) => m.userData.gt.pretty))].sort(), [version]);

  const go = (e) => {
    e.preventDefault();
    const s = q.trim().toLowerCase();
    if (!s) return;
    const ms = allMeshes();
    const hit =
      ms.find((m) => m.userData.gt.pretty.toLowerCase() === s) ??
      ms.find((m) => m.userData.gt.organ && ORGAN_LABEL[m.userData.gt.organ].toLowerCase() === s) ??
      ms.find((m) => m.userData.gt.pretty.toLowerCase().includes(s));
    if (hit) {
      setMsg('');
      onFound(hit);
    } else setMsg('Not found');
  };

  return (
    <form className="search" onSubmit={go}>
      <input list="structure-names" placeholder="Search a structure, e.g. heart" value={q} onChange={(e) => setQ(e.target.value)} />
      <datalist id="structure-names">{names.slice(0, 3000).map((n) => <option key={n} value={n} />)}</datalist>
      <button type="submit">Go</button>
      {msg && <span className="search-msg">{msg}</span>}
    </form>
  );
}

export function Toolbar({ opts, setOpts, onReset, onCredits }) {
  const t = (k) => setOpts((o) => ({ ...o, [k]: !o[k] }));
  return (
    <div className="toolbar">
      <button className={opts.labels ? 'active' : ''} onClick={() => t('labels')}>Labels</button>
      <button className={opts.healthView ? 'active' : ''} onClick={() => t('healthView')}>Health view</button>
      <button className={opts.animate ? 'active' : ''} onClick={() => t('animate')}>Animate</button>
      <button onClick={onReset}>Reset view</button>
      <button onClick={onCredits}>Credits</button>
    </div>
  );
}

export function CreditsModal({ onClose }) {
  return (
    <div className="modal" onClick={onClose}>
      <div className="panel modal-body" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        <h3>Credits and licences</h3>
        <ul>
          {CREDITS.map((c) => (
            <li key={c.name}>
              <a href={c.url} target="_blank" rel="noreferrer">{c.name}</a> — {c.what} ({c.licence})
            </li>
          ))}
        </ul>
        <p className="tiny">Anatomy meshes are adapted from Z-Anatomy and BodyParts3D under share-alike licences.</p>
      </div>
    </div>
  );
}
