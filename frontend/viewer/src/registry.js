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
  // three.js strips dots from mesh.name ("Olive.r" -> "Oliver"), so use the original glTF name.
  const pretty = cleanName(mesh.userData.name ?? mesh.name);
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

  const base = pretty.replace(/[ .][lr]$/i, '');
  const display = (base.charAt(0).toUpperCase() + base.slice(1)) + (side && /[ .][lr]$/i.test(pretty) ? ` (${side})` : '');
  mesh.userData.gt = { file: file.url, id, system, structure, side, organ: organ?.id ?? null, pretty: display };
}

// ---------------------------------------------------------------
// Materials: each mesh gets its own material so opacity and glow can be set per mesh.
// ---------------------------------------------------------------

const SYSTEM_COLOR = Object.fromEntries(SYSTEMS.map((s) => [s.id, s.color]));
const EYE = ['eyeball', 'lens', 'retina', 'cornea', 'iris', 'vitreous', 'sclera', 'choroid', 'ciliary', 'zonular'];

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
    } else if (EYE.some((w) => n.includes(w))) {
      mat.color.set(n.includes('lens') || n.includes('cornea') ? '#d6e6f0' : n.includes('iris') ? '#5b6f8a' : '#ece7de');
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

// Team rule: 80+ green, 50-79 yellow, below 50 red.
const GREEN = new THREE.Color('#2ecc71');
const YELLOW = new THREE.Color('#f1c40f');
const RED = new THREE.Color('#e74c3c');
export function scoreColor(score) {
  return (score >= 80 ? GREEN : score >= 50 ? YELLOW : RED).clone();
}

// health[organ] = { score, vitals, glow? }  glow (0-1) overrides the default intensity.
export function applyHighlights({ health, healthOn, selected }) {
  for (const m of registry.meshes) {
    const g = m.userData.gt;
    let color = null;
    let intensity = 0;
    if (healthOn && g.organ && health[g.organ]) {
      color = scoreColor(health[g.organ].score);
      intensity = health[g.organ].glow ?? 0.45;
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

// ---------------------------------------------------------------
// Auto-alignment. Some Blender exports lose a parent transform, so a part
// (often the brain) lands in the wrong place or at the wrong size.
// - Brain: moved and scaled to sit inside the skull.
// - Skin:  scaled and moved to wrap the skeleton (works for any human body mesh).
// Safe to call many times: once things are aligned it changes nothing.
// ---------------------------------------------------------------
const CRANIAL = ['frontal bone', 'parietal bone', 'occipital bone', 'temporal bone', 'sphenoid', 'ethmoid', 'cranium', 'skull', 'calvaria'];

function worldBox(meshes) {
  const box = new THREE.Box3();
  meshes.forEach((m) => box.expandByObject(m));
  return box;
}

function refreshWorld(meshes) {
  const roots = new Set();
  meshes.forEach((m) => {
    let r = m;
    while (r.parent) r = r.parent;
    roots.add(r);
  });
  roots.forEach((r) => r.updateMatrixWorld(true));
}

// Keep only meshes that have no ancestor in the same list, so children aren't moved twice.
function topLevel(list) {
  const set = new Set(list);
  return list.filter((m) => {
    for (let p = m.parent; p; p = p.parent) if (set.has(p)) return false;
    return true;
  });
}

// Applies world transform W' = T(to) * S(scale) * T(-from) * W to each mesh.
function moveInWorld(meshes, from, to, scale) {
  const T = new THREE.Matrix4().makeTranslation(to.x, to.y, to.z)
    .multiply(new THREE.Matrix4().makeScale(scale.x, scale.y, scale.z))
    .multiply(new THREE.Matrix4().makeTranslation(-from.x, -from.y, -from.z));
  for (const m of topLevel(meshes)) {
    const world = T.clone().multiply(m.matrixWorld);
    const local = m.parent ? m.parent.matrixWorld.clone().invert().multiply(world) : world;
    local.decompose(m.position, m.quaternion, m.scale);
    m.userData.baseScale = m.scale.clone();
    if (m.userData.pivotOffset) {
      m.userData.basePosition = m.position.clone();
      m.geometry.computeBoundingBox();
      m.userData.pivotOffset = m.geometry.boundingBox.getCenter(new THREE.Vector3()).multiply(m.scale).applyQuaternion(m.quaternion);
    }
    m.updateMatrixWorld(true);
  }
}

// A mesh whose name matches an organ keyword but sits far from that organ's main part
// (e.g. something in the chest tagged "brain") loses its organ tag, so it no longer drags
// the label, the glow or the auto-alignment away. The organ's largest mesh is the anchor.
const ORGAN_RADIUS = { brain: 0.1, heart: 0.08, thyroid: 0.06, bladder: 0.08, spleen: 0.08, pancreas: 0.1, stomach: 0.1, liver: 0.12 };

function cleanOrganTags(ms, bodyHeight) {
  let changed = false;
  const byOrgan = {};
  ms.forEach((m) => {
    const o = m.userData.gt.organ;
    if (o) (byOrgan[o] ??= []).push(m);
  });
  for (const [organ, list] of Object.entries(byOrgan)) {
    if (list.length < 2) continue;
    const info = list.map((m) => {
      const b = new THREE.Box3().setFromObject(m);
      const sz = b.getSize(new THREE.Vector3());
      return { m, c: b.getCenter(new THREE.Vector3()), vol: sz.x * sz.y * sz.z };
    });
    // Median of all part centres: one big stray mesh can't pull it away.
    const med = (k) => { const v = info.map((x) => x.c[k]).sort((p, q) => p - q); return v[Math.floor(v.length / 2)]; };
    const anchor = new THREE.Vector3(med('x'), med('y'), med('z'));
    const r = (ORGAN_RADIUS[organ] ?? 0.22) * bodyHeight;
    for (const { m, c } of info) {
      if (c.distanceTo(anchor) > r) {
        console.info(`[BodyViewer] "${m.userData.gt.pretty}" is far from the ${organ}, untagged from it`);
        m.userData.gt.organ = null;
        changed = true;
      }
    }
  }
  return changed;
}

export function alignAnatomy() {
  const ms = [...registry.meshes];
  if (!ms.length) return false;
  refreshWorld(ms);
  let changed = false;

  {
    const skel = ms.filter((m) => m.userData.gt.system === 'skeletal');
    const h = worldBox(skel.length ? skel : ms).getSize(new THREE.Vector3()).y;
    if (h > 0 && cleanOrganTags(ms, h)) changed = true;
  }

  const skeleton = ms.filter((m) => m.userData.gt.system === 'skeletal');
  if (!skeleton.length) return false;
  const skelBox = worldBox(skeleton);
  const skelSize = skelBox.getSize(new THREE.Vector3());

  // ---- brain into skull ----
  let skull = skeleton.filter((m) => CRANIAL.some((k) => m.userData.gt.pretty.toLowerCase().includes(k)));
  if (!skull.length) {
    // No named skull bones: use the top 12% of the skeleton.
    const cut = skelBox.max.y - skelSize.y * 0.12;
    skull = skeleton.filter((m) => new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3()).y > cut);
  }
  const core = ms.filter((m) => m.userData.gt.organ === 'brain');
  if (skull.length && core.length) {
    const S = worldBox(skull);
    const B = worldBox(core);
    // Every other brain part (ventricles, nuclei, gyri...) is picked up by position around the core.
    const sz = B.getSize(new THREE.Vector3());
    const near = B.clone().expandByVector(sz.clone().multiplyScalar(0.2));
    const files = new Set(core.map((m) => m.userData.gt.file));
    const parts = ms.filter((m) =>
      (m.userData.gt.organ === 'brain' || (m.userData.gt.system === 'nervous' && files.has(m.userData.gt.file))) &&
      near.containsPoint(new THREE.Box3().setFromObject(m).getCenter(new THREE.Vector3()))
    );
    const all = worldBox(parts);
    const allC = all.getCenter(new THREE.Vector3());
    const allSize = all.getSize(new THREE.Vector3());
    const sC = S.getCenter(new THREE.Vector3());
    const sSize = S.getSize(new THREE.Vector3());
    const ratio = allSize.y / sSize.y;
    // Only move it when it is clearly wrong: centre outside the skull, or a very wrong size.
    if (!S.containsPoint(allC) || ratio < 0.4 || ratio > 1.6) {
      const k = ratio < 0.4 || ratio > 1.6 ? (0.75 * sSize.y) / allSize.y : 1;
      // Brain sits a little above the skull box centre (the face bones pull the box down).
      const target = sC.clone().add(new THREE.Vector3(0, sSize.y * 0.08, 0));
      moveInWorld(parts, allC, target, new THREE.Vector3(k, k, k));
      console.info(`[BodyViewer] Brain re-aligned to skull (moved ${allC.distanceTo(target).toFixed(3)}, scale ${k.toFixed(2)})`);
      changed = true;
    }
  }

  // ---- skin around skeleton ----
  const skin = ms.filter((m) => m.userData.gt.system === 'integumentary');
  if (skin.length) {
    const K = worldBox(skin);
    const kSize = K.getSize(new THREE.Vector3());
    const kC = K.getCenter(new THREE.Vector3());
    const sC = skelBox.getCenter(new THREE.Vector3());
    // Skin is a bit taller than bone (soft tissue on the feet and scalp).
    const wantH = skelSize.y * 1.02;
    const k = wantH / kSize.y;
    const off = Math.hypot(kC.x - sC.x, kC.z - sC.z) + Math.abs(K.min.y - (skelBox.min.y - skelSize.y * 0.01));
    if (Math.abs(k - 1) > 0.04 || off > skelSize.y * 0.03) {
      const target = new THREE.Vector3(sC.x, skelBox.min.y - skelSize.y * 0.01 + (kSize.y * k) / 2, sC.z);
      moveInWorld(skin, kC, target, new THREE.Vector3(k, k, k));
      console.info(`[BodyViewer] Skin fitted to skeleton (scale ${k.toFixed(2)})`);
      changed = true;
    }
  }
  return changed;
}
