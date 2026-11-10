import * as THREE from 'three';
import { ORGANS, NOT_ORGAN, SYSTEM_KEYWORDS, SYSTEMS } from './config.js';

// ---------------------------------------------------------------
// Naming: every mesh gets userData.gt = { id, system, structure, side, organ, pretty }
// id follows the contract: system__structure__side  (e.g. urinary__kidney__left)
// ---------------------------------------------------------------

export function inferSystem(text) {
  const t = text.toLowerCase();
  for (const [sys, kws] of Object.entries(SYSTEM_KEYWORDS)) {
    if (kws.some((k) => t.includes(k))) return sys;
  }
  return null;
}

function cleanName(raw) {
  return (raw || 'unnamed').replace(/\.\d{3,}$/, '').replace(/_/g, ' ').trim();
}

function detectSide(n) {
  if (/\bleft\b/.test(n) || /[ .]l$/.test(n)) return 'left';
  if (/\bright\b/.test(n) || /[ .]r$/.test(n)) return 'right';
  return '';
}

function slug(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}

function detectOrgan(n) {
  if (NOT_ORGAN.some((w) => n.includes(w))) return null;
  for (const o of ORGANS) {
    if (o.not && o.not.some((w) => n.includes(w))) continue;
    if (o.kw.some((k) => n.includes(k))) return o;
  }
  return null;
}

export function classifyMesh(mesh, file) {
  const pretty = cleanName(mesh.name);
  const n = pretty.toLowerCase();
  const organ = detectOrgan(n);

  let ancestors = '';
  for (let p = mesh.parent; p; p = p.parent) ancestors += ' ' + (p.name || '');

  const system =
    organ?.system ??
    (file.system !== 'mixed' ? file.system : null) ??
    inferSystem(ancestors) ??
    inferSystem(n) ??
    'other';

  const side = detectSide(n);
  const structure = slug(n.replace(/\bleft\b|\bright\b/g, '').replace(/[ .][lr]$/, '')) || 'part';
  const id = side ? `${system}__${structure}__${side}` : `${system}__${structure}`;

  mesh.userData.gt = { id, system, structure, side, organ: organ?.id ?? null, pretty: pretty.charAt(0).toUpperCase() + pretty.slice(1) };
}

// ---------------------------------------------------------------
// Materials: each mesh gets its own material so opacity and glow can be set per mesh.
// ---------------------------------------------------------------

const SYSTEM_COLOR = Object.fromEntries(SYSTEMS.map((s) => [s.id, s.color]));

export function forEachMat(mesh, fn) {
  if (Array.isArray(mesh.material)) mesh.material.forEach(fn);
  else if (mesh.material) fn(mesh.material);
}

function prepareMaterial(mesh) {
  const g = mesh.userData.gt;
  const n = g.pretty.toLowerCase();
  const convert = (m) => {
    let mat = m && m.emissive ? m.clone() : new THREE.MeshStandardMaterial({ color: m?.color?.clone?.() ?? '#cccccc', map: m?.map ?? null });
    if (g.system === 'cardiovascular' && !g.organ) {
      if (n.includes('vein')) mat.color.set('#3a68d0');
      else if (n.includes('arter') || n.includes('aorta')) mat.color.set('#c0392b');
    } else if (SYSTEM_COLOR[g.system]) {
      mat.color.set(SYSTEM_COLOR[g.system]);
    }
    if ('roughness' in mat) mat.roughness = 0.55;
    if ('metalness' in mat) mat.metalness = 0.05;
    mat.userData.baseEmissive = mat.emissive.clone();
    mat.userData.baseEmissiveIntensity = mat.emissiveIntensity ?? 1;
    return mat;
  };
  mesh.material = Array.isArray(mesh.material) ? mesh.material.map(convert) : convert(mesh.material);
}

// Stores the mesh's own centre so the heartbeat/breathing can scale it in place.
// Nothing is moved here: the model (and any child meshes) stays exactly where it was exported.
function storePivot(mesh) {
  mesh.geometry.computeBoundingBox();
  const c = mesh.geometry.boundingBox.getCenter(new THREE.Vector3());
  mesh.userData.basePosition = mesh.position.clone();
  mesh.userData.pivotOffset = c.multiply(mesh.scale).applyQuaternion(mesh.quaternion);
}

// ---------------------------------------------------------------
// Registry of every loaded mesh.
// ---------------------------------------------------------------

export const registry = { meshes: new Set(), byFile: new Map() };

export function registerScene(file, scene) {
  const list = [];
  scene.traverse((o) => {
    if (!o.isMesh) return;
    if (!o.userData.gt) {
      classifyMesh(o, file);
      prepareMaterial(o);
      o.userData.baseScale = o.scale.clone();
      if (o.userData.gt.organ === 'heart' || o.userData.gt.organ === 'lungs') storePivot(o);
    }
    list.push(o);
    registry.meshes.add(o);
  });
  registry.byFile.set(file.url, list);
}

export function unregisterFile(url) {
  (registry.byFile.get(url) || []).forEach((m) => registry.meshes.delete(m));
  registry.byFile.delete(url);
}

export const allMeshes = () => [...registry.meshes];

// ---------------------------------------------------------------
// Layers (visibility + opacity) and highlights (health glow + selection).
// ---------------------------------------------------------------

export function applyLayers(layers) {
  for (const m of registry.meshes) {
    const L = layers[m.userData.gt.system] ?? { on: true, opacity: 1 };
    m.visible = L.on;
    const transparent = L.opacity < 0.999;
    forEachMat(m, (mat) => {
      mat.opacity = L.opacity;
      if (mat.transparent !== transparent) {
        mat.transparent = transparent;
        mat.needsUpdate = true;
      }
      mat.depthWrite = !transparent;
    });
    // Skin renders last so the layers under it show through.
    m.renderOrder = m.userData.gt.system === 'integumentary' ? 10 : transparent ? 5 : 0;
  }
}

const SELECT_COLOR = new THREE.Color('#4fc3ff');

export function scoreColor(score) {
  const s = Math.max(0, Math.min(100, score)) / 100;
  return new THREE.Color().setHSL(s * 0.33, 0.85, 0.5); // 0 = red, 50 = yellow, 100 = green
}

export function applyHighlights({ health, healthOn, selected }) {
  for (const m of registry.meshes) {
    const g = m.userData.gt;
    let color = null;
    let intensity = 0;
    if (healthOn && g.organ && health[g.organ]) {
      color = scoreColor(health[g.organ].score);
      intensity = 0.45;
    }
    if (selected === m) {
      color = SELECT_COLOR;
      intensity = 0.8;
    }
    forEachMat(m, (mat) => {
      if (color) {
        mat.emissive.copy(color);
        mat.emissiveIntensity = intensity;
      } else {
        mat.emissive.copy(mat.userData.baseEmissive);
        mat.emissiveIntensity = mat.userData.baseEmissiveIntensity;
      }
    });
  }
}

// True if the mesh and all its parents are visible.
export function isShown(o) {
  for (let p = o; p; p = p.parent) if (!p.visible) return false;
  return true;
}

export function meshOpacity(o) {
  const m = Array.isArray(o.material) ? o.material[0] : o.material;
  return m ? m.opacity : 1;
}

// Bounding box of all visible meshes, or of a list of meshes.
export function boxOf(meshes) {
  const box = new THREE.Box3();
  meshes.forEach((m) => {
    if (isShown(m)) box.expandByObject(m);
  });
  return box;
}
