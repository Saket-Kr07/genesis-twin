import React, { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas } from '@react-three/fiber';
import { CameraControls, GizmoHelper, GizmoViewcube, Loader } from '@react-three/drei';
import { SYSTEMS } from './config.js';
import { inferSystem, applyLayers, applyHighlights, allMeshes, boxOf } from './registry.js';
import { predictHealth } from './api.js';
import { Models, AutoFit, Animator, Labels } from './components/Scene.jsx';
import { LayersPanel, LifestylePanel, InfoPanel, SearchBox, Toolbar, CreditsModal } from './components/Panels.jsx';

// Turns the list of GLB paths into files with a sex and a system.
function buildFiles(paths, sex, modelsBase) {
  const files = paths.map((p) => {
    const lower = p.toLowerCase();
    const fileSex = lower.includes('female') ? 'female' : /(^|[^a-z])male/.test(lower) ? 'male' : 'any';
    const base = lower.split('/').pop().replace(/\.glb$/, '');
    return {
      url: modelsBase + p.split('/').map(encodeURIComponent).join('/'),
      sex: fileSex,
      system: inferSystem(base) ?? 'mixed',
    };
  });
  const hasFemale = files.some((f) => f.sex === 'female');
  const want = sex === 'female' && !hasFemale ? 'male' : sex;
  return { files: files.filter((f) => f.sex === want || f.sex === 'any'), femaleFallback: sex === 'female' && !hasFemale };
}

const initialLayers = Object.fromEntries(SYSTEMS.map((s) => [s.id, { on: s.on, opacity: s.opacity }]));

export default function BodyViewer({ modelsBase = '/' }) {
  const [paths, setPaths] = useState(null);
  const [sex, setSex] = useState('male');
  const [layers, setLayers] = useState(initialLayers);
  const [version, bump] = useReducer((x) => x + 1, 0);
  const [selected, setSelected] = useState(null);
  const [life, setLife] = useState({ age: 30, sleep: 7, exercise: 3, smoking: 0, diet: 3 });
  const [health, setHealth] = useState({ data: {}, source: '' });
  const [opts, setOpts] = useState({ labels: false, healthView: true, animate: true });
  const [credits, setCredits] = useState(false);
  const [panelsOpen, setPanelsOpen] = useState(true);
  const [everLoaded, setEverLoaded] = useState(() => new Set());
  const controlsRef = useRef();

  // 1. Find the GLB files in public/
  useEffect(() => {
    fetch(`${modelsBase}models-manifest.json`)
      .then((r) => r.json())
      .then(setPaths)
      .catch(() => setPaths([]));
  }, [modelsBase]);

  const { files, femaleFallback } = useMemo(
    () => (paths ? buildFiles(paths, sex, modelsBase) : { files: [], femaleFallback: false }),
    [paths, sex, modelsBase]
  );

  // 2. Lazy loading: a system file loads the first time its layer is switched on.
  const toLoad = files.filter((f) => f.system === 'mixed' || layers[f.system]?.on || everLoaded.has(f.url));
  useEffect(() => {
    const missing = toLoad.filter((f) => !everLoaded.has(f.url));
    if (missing.length) setEverLoaded((s) => new Set([...s, ...missing.map((f) => f.url)]));
  }, [toLoad, everLoaded]);

  // 3. Health scores from the API (or dummy), refreshed when sliders change.
  useEffect(() => {
    let live = true;
    const t = setTimeout(async () => {
      const res = await predictHealth({ ...life, sex });
      if (live) setHealth(res);
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [life, sex]);

  // 4. Push state into the 3D materials.
  useEffect(() => applyLayers(layers), [layers, version]);
  useEffect(
    () => applyHighlights({ health: health.data, healthOn: opts.healthView, selected }),
    [health, opts.healthView, selected, version]
  );
  useEffect(() => {
    if (selected && !allMeshes().includes(selected)) setSelected(null);
  }, [version, selected]);

  const counts = useMemo(() => {
    const c = {};
    allMeshes().forEach((m) => (c[m.userData.gt.system] = (c[m.userData.gt.system] ?? 0) + 1));
    return c;
  }, [version]);

  const focus = (obj) => {
    const c = controlsRef.current;
    if (!c) return;
    const box = new THREE.Box3().setFromObject(obj);
    const p = box.getSize(new THREE.Vector3()).length() * 0.6;
    c.fitToBox(box, true, { paddingTop: p, paddingBottom: p, paddingLeft: p, paddingRight: p });
  };

  const resetView = () => {
    const c = controlsRef.current;
    const box = boxOf(allMeshes());
    if (!c || box.isEmpty()) return;
    const p = box.getSize(new THREE.Vector3()).length() * 0.03;
    c.setLookAt(0, 0, 1, 0, 0, 0, false);
    c.fitToBox(box, true, { paddingTop: p, paddingBottom: p, paddingLeft: p, paddingRight: p });
  };

  const onFound = (mesh) => {
    const sys = mesh.userData.gt.system;
    if (!layers[sys].on) setLayers((L) => ({ ...L, [sys]: { ...L[sys], on: true } }));
    setSelected(mesh);
    focus(mesh);
  };

  return (
    <div className="gt-viewer">
      <div className="gt-canvas">
        <Canvas camera={{ position: [0, 0, 5], fov: 35 }} dpr={[1, 1.75]} onPointerMissed={() => setSelected(null)}>
          <hemisphereLight args={['#bcd3ff', '#141c2c', 0.6]} />
          <directionalLight position={[2, 4, 5]} intensity={2.2} />
          <spotLight position={[0, 6, 4]} angle={0.5} penumbra={0.8} intensity={40} />
          <directionalLight position={[-3, 2, -5]} intensity={1.6} color="#7fb2ff" />
          <directionalLight position={[3, 1, -4]} intensity={1.0} color="#9fc4ff" />

          <Models files={toLoad} onChange={bump} onSelect={setSelected} onFocus={focus} />
          <CameraControls ref={controlsRef} makeDefault />
          <AutoFit version={version} />
          <Animator enabled={opts.animate} version={version} />
          <Labels show={opts.labels} version={version} layers={layers} />

          <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
            <GizmoViewcube color="#22304a" textColor="#e6edf7" strokeColor="#4a5f85" hoverColor="#2f7dd1" opacity={0.95} />
          </GizmoHelper>
        </Canvas>
        <div className="vignette" />
      </div>

      <Loader />

      <header className="topbar">
        <button className="panel-toggle" onClick={() => setPanelsOpen((o) => !o)}>{panelsOpen ? 'Hide panels' : 'Show panels'}</button>
        <SearchBox version={version} onFound={onFound} />
        <Toolbar opts={opts} setOpts={setOpts} onReset={resetView} onCredits={() => setCredits(true)} />
      </header>

      {panelsOpen && (
        <div className="side">
          <LayersPanel layers={layers} setLayers={setLayers} counts={counts} sex={sex} setSex={setSex} femaleFallback={femaleFallback} />
          <LifestylePanel life={life} setLife={setLife} source={health.source} />
        </div>
      )}

      <InfoPanel mesh={selected} health={health.data} onClose={() => setSelected(null)} />

      {paths && paths.length === 0 && (
        <div className="empty panel">No .glb files found in <code>public/</code>. Copy your Z-Anatomy GLB files there and refresh.</div>
      )}

      {credits && <CreditsModal onClose={() => setCredits(false)} />}

      <footer className="disclaimer">
        Simulation for research and education only. Not medical advice. Vitals are model outputs, not measurements.
      </footer>
    </div>
  );
}
