import React, { Suspense, useLayoutEffect, useMemo, useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { useGLTF, Html } from '@react-three/drei';
import { registerScene, unregisterFile, allMeshes, boxOf, isShown, meshOpacity } from '../registry.js';
import { ORGANS } from '../config.js';

// ---------- one GLB file ----------
function ModelFile({ file, onChange }) {
  const { scene } = useGLTF(file.url, true); // true = Draco decoder enabled
  useLayoutEffect(() => {
    registerScene(file, scene);
    onChange();
    return () => {
      unregisterFile(file.url);
      onChange();
    };
  }, [scene]); // eslint-disable-line react-hooks/exhaustive-deps
  return <primitive object={scene} />;
}

class ModelErrorBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidCatch(error) {
    console.error(`Could not load ${this.props.url}`, error);
  }
  render() {
    return this.state.error ? null : this.props.children;
  }
}

// ---------- picking helpers ----------
// Prefer the first solid hit; skip see-through skin so you can click organs through it.
function pick(e) {
  const shown = e.intersections.filter((i) => i.object.isMesh && isShown(i.object));
  return (shown.find((i) => meshOpacity(i.object) >= 0.6) ?? shown[0])?.object ?? null;
}

export function Models({ files, onChange, onSelect, onFocus }) {
  return (
    <group
      onClick={(e) => {
        e.stopPropagation();
        if (e.delta > 4) return; // it was a drag, not a click
        onSelect(pick(e));
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        const m = pick(e);
        if (m) {
          onSelect(m);
          onFocus(m);
        }
      }}
    >
      {files.map((f) => (
        <ModelErrorBoundary key={f.url} url={f.url}>
          <Suspense fallback={null}>
            <ModelFile file={f} onChange={onChange} />
          </Suspense>
        </ModelErrorBoundary>
      ))}
    </group>
  );
}

// ---------- fit the camera once when the first model appears ----------
export function AutoFit({ version }) {
  const done = useRef(false);
  const controls = useThree((s) => s.controls);
  const camera = useThree((s) => s.camera);
  useEffect(() => {
    if (done.current || !controls) return;
    const meshes = allMeshes();
    if (!meshes.length) return;
    const box = boxOf(meshes);
    if (box.isEmpty()) return;
    const size = box.getSize(new THREE.Vector3()).length();
    camera.near = size / 1000;
    camera.far = size * 100;
    camera.updateProjectionMatrix();
    const p = size * 0.03;
    controls.fitToBox(box, false, { paddingTop: p, paddingBottom: p, paddingLeft: p, paddingRight: p });
    done.current = true;
  }, [version, controls, camera]);
  return null;
}

// ---------- heartbeat and breathing ----------
export function Animator({ enabled, version }) {
  const lists = useMemo(() => {
    const ms = allMeshes();
    // Only animate the top-most mesh of each organ; child parts follow their parent automatically.
    const top = (organ) => {
      const set = new Set(ms.filter((m) => m.userData.gt.organ === organ && m.userData.pivotOffset));
      return [...set].filter((m) => {
        for (let p = m.parent; p; p = p.parent) if (set.has(p)) return false;
        return true;
      });
    };
    return { heart: top('heart'), lungs: top('lungs') };
  }, [version]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scale around the mesh's own centre without moving the model.
  const pulse = (m, k) => {
    m.scale.copy(m.userData.baseScale).multiplyScalar(k);
    m.position.copy(m.userData.basePosition).addScaledVector(m.userData.pivotOffset, 1 - k);
  };

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
           const beat = enabled ? 1 + 0.015 * Math.pow(Math.max(0, Math.sin(t * Math.PI * 2 * 1.0)), 4) : 1; // 60 bpm, gentle // ~70 bpm
    const breath = enabled ? 1 + 0.03 * (0.5 - 0.5 * Math.cos((t * Math.PI * 2) / 4)) : 1; // 15 breaths/min
    lists.heart.forEach((m) => pulse(m, beat));
    lists.lungs.forEach((m) => pulse(m, breath));
  });
  return null;
}

// ---------- labels with leader lines, one per organ ----------
export function Labels({ show, version, layers }) {
  const labels = useMemo(() => {
    if (!show) return [];
    const ms = allMeshes();
    const all = boxOf(ms);
    if (all.isEmpty()) return [];
    const midX = all.getCenter(new THREE.Vector3()).x;
    return ORGANS.map((o) => {
      const box = boxOf(ms.filter((m) => m.userData.gt.organ === o.id));
      if (box.isEmpty()) return null;
      const c = box.getCenter(new THREE.Vector3());
      return { id: o.id, text: o.label, pos: c.toArray(), left: c.x < midX };
    }).filter(Boolean);
  }, [show, version, layers]);

  return labels.map((l) => (
    <Html key={l.id} position={l.pos} zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
      <div className={`label ${l.left ? 'label-left' : ''}`}>
        <span className="label-dot" />
        <span className="label-line" />
        <span className="label-text">{l.text}</span>
      </div>
    </Html>
  ));
}
