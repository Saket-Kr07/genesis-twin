// ---------------------------------------------------------------------------
// Cinematic skull renderer for the Genesis Twin intro (vanilla three.js).
//
// It loads the skull out of the same Z-Anatomy skeleton file the 3D viewer uses
// (public/models/skeletal.glb), keeps only the cranium, facial bones, mandible
// and teeth, re-materials them with a physically based bone shader and lights
// them like a museum specimen: warm key light with real shadows, cool theme-
// coloured rim lights, and an environment map for soft reflections.
//
// Loaded lazily (dynamic import) so three.js never delays first paint.
// ---------------------------------------------------------------------------
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

// Same Draco decoder CDN the 3D viewer (drei) uses.
const DRACO_PATH = 'https://www.gstatic.com/draco/versioned/decoders/1.5.5/';

// ---- Tweakables -----------------------------------------------------------
const SKULL_HEIGHT = 2.15;   // scene units the skull is scaled to
const LIFT = 0.45;           // raises the skull so the title has room underneath
const YAW = 0.62;            // radians: 3/4 view (about 35 degrees, face turned to screen right)
const PITCH = 0.05;          // slight downward tilt
const SPIN_IN = 1.7;         // how far the skull has turned before it settles into the 3/4 pose
const EXPOSURE = 1.15;
// Theme colours (same values as --acc / --acc2 in index.html)
const ACC = 0x5eead4;
const ACC2 = 0x8b9cff;

// Names (from the GLB) of the skull's top-level bones. The GLTFLoader strips
// spaces and dots from node names, so the pattern tolerates both spellings.
const SKULL_BONE =
  /^(frontal bone|parietal bone|occipital bone|temporal bone|sphenoid bone|ethmoid bone|zygomatic bone|maxilla|mandible|nasal bone|lacrimal bone|palatine bone|vomer|inferior nasal concha bone)\.?[lr]?$/i;
const TOOTH = /(incisor|canine|molar|premolar|tooth)\.?[lr]?$/i;
const SINUS = /sinus/i;

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const easeOutQuart = (t) => 1 - Math.pow(1 - t, 4);
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

const nodeName = (o) => String(o.userData?.name || o.name || '').replace(/_/g, ' ').trim();
const hash01 = (s) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return ((h >>> 0) % 1000) / 1000;
};

function hasAncestor(o, set) {
  for (let p = o.parent; p; p = p.parent) if (set.has(p)) return true;
  return false;
}

function makeBoneMaterial(name, tooth) {
  const j = hash01(name) - 0.5; // per-bone tonal variation, so the bones read as individual pieces
  const m = new THREE.MeshPhysicalMaterial(
    tooth
      ? {
          color: new THREE.Color('#f0e9d7'),
          roughness: 0.34,
          clearcoat: 0.55,
          clearcoatRoughness: 0.3,
          sheen: 0.2,
          sheenColor: new THREE.Color('#fff8ea'),
        }
      : {
          color: new THREE.Color('#d9ceb4'),
          roughness: 0.66,
          clearcoat: 0.14,
          clearcoatRoughness: 0.5,
          sheen: 0.35,
          sheenRoughness: 0.55,
          sheenColor: new THREE.Color('#fff1da'),
          side: THREE.DoubleSide, // some facial bones are thin shells
        }
  );
  m.metalness = 0;
  m.color.offsetHSL(j * 0.012, j * 0.05, j * 0.07);
  return m;
}

function glowTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  grad.addColorStop(0, 'rgba(94,234,212,0.55)');
  grad.addColorStop(0.35, 'rgba(94,234,212,0.18)');
  grad.addColorStop(1, 'rgba(94,234,212,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/**
 * @param {HTMLElement} host   element the canvas is appended to (fills it)
 * @param {{ url: string, onProgress?: (p:number)=>void, reducedMotion?: boolean }} opts
 */
export async function createSkullScene(host, { url, onProgress, reducedMotion = false }) {
  // ---------- renderer ----------
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0); // transparent: the site's own background shows through
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.style.display = 'block';
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);

  // ---------- reflections ----------
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
  scene.environment = envRT.texture;
  scene.environmentIntensity = 0.38;

  // ---------- lights ----------
  scene.add(new THREE.HemisphereLight(0x9fb4e6, 0x0a1020, 0.28));

  const key = new THREE.DirectionalLight(0xfff1de, 3.4); // warm key, casts the real shadows
  key.position.set(-3.6, 4.6, 5.2);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = key.shadow.camera.bottom = -2.4;
  key.shadow.camera.right = key.shadow.camera.top = 2.4;
  key.shadow.camera.near = 0.5;
  key.shadow.camera.far = 16;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  key.shadow.radius = 4;
  scene.add(key);

  const fill = new THREE.DirectionalLight(ACC2, 0.9);
  fill.position.set(4.2, 0.8, 3.2);
  scene.add(fill);

  const rimA = new THREE.DirectionalLight(ACC, 3.2);
  rimA.position.set(3.4, 3.2, -4.2);
  scene.add(rimA);
  const rimB = new THREE.DirectionalLight(ACC2, 2.0);
  rimB.position.set(-4.2, 1.6, -3.4);
  scene.add(rimB);

  // soft teal pool of light under the skull
  const glowMat = new THREE.MeshBasicMaterial({
    map: glowTexture(),
    transparent: true,
    opacity: 0.4,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  });
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(5.2, 5.2), glowMat);
  glow.rotation.x = -Math.PI / 2;
  glow.position.y = LIFT - SKULL_HEIGHT / 2 - 0.22;
  scene.add(glow);

  // ---------- load + extract the skull ----------
  const draco = new DRACOLoader();
  draco.setDecoderPath(DRACO_PATH);
  const loader = new GLTFLoader();
  loader.setDRACOLoader(draco);

  const gltf = await loader.loadAsync(url, (e) => {
    if (onProgress && e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total);
  });
  gltf.scene.updateMatrixWorld(true);

  const wanted = new Set();
  gltf.scene.traverse((o) => {
    const n = nodeName(o);
    if (n && (SKULL_BONE.test(n) || TOOTH.test(n))) wanted.add(o);
  });
  const roots = [...wanted].filter((o) => !hasAncestor(o, wanted));
  if (!roots.length) throw new Error('No skull bones found in ' + url);

  const skull = new THREE.Group();
  roots.forEach((o) => skull.attach(o)); // attach() keeps each bone's world transform

  // free everything we are not showing (hands, ribs, spine, ...)
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.geometry?.dispose();
    [].concat(o.material || []).forEach((m) => m.dispose?.());
  });

  // new materials + shadows
  skull.traverse((o) => {
    if (!o.isMesh) return;
    let name = nodeName(o);
    let tooth = TOOTH.test(name);
    for (let p = o.parent; p && p !== skull && !tooth; p = p.parent) tooth = TOOTH.test(nodeName(p));
    if (SINUS.test(name) || [...(function* () { for (let p = o.parent; p && p !== skull; p = p.parent) yield nodeName(p); })()].some((n) => SINUS.test(n))) {
      o.visible = false; // air-cavity volumes, not bone
      return;
    }
    if (!name) name = o.parent ? nodeName(o.parent) : 'bone';
    [].concat(o.material || []).forEach((m) => m.dispose?.());
    o.material = makeBoneMaterial(name, tooth);
    if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
    o.castShadow = true;
    o.receiveShadow = true;
  });

  // centre it and scale to a fixed height
  skull.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(skull, true);
  const centre = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  skull.position.sub(centre);

  const pivot = new THREE.Group();
  pivot.add(skull);
  pivot.scale.setScalar(SKULL_HEIGHT / size.y);

  const rig = new THREE.Group(); // animated pose lives here
  rig.add(pivot);
  rig.position.y = LIFT;
  scene.add(rig);

  // ---------- sizing ----------
  let baseDist = 7.4;
  function resize() {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setSize(w, h);
    camera.aspect = w / h;
    // keep the skull inside the frame on narrow (portrait) screens
    baseDist = Math.max(7.4, 5.6 / camera.aspect);
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  renderer.compile(scene, camera); // avoid a hitch on the first frame

  // ---------- animation ----------
  let raf = 0;
  let t0 = 0;
  let running = false;
  let exitAt = null;
  let exitMs = 1200;
  const pointer = { x: 0, y: 0, sx: 0, sy: 0 };

  function tick(now) {
    raf = requestAnimationFrame(tick);
    if (!running) return;
    const t = (now - t0) / 1000;

    // fade up out of the dark
    const fade = reducedMotion ? clamp01(t / 0.8) : easeOutCubic(clamp01((t - 0.15) / 2.6));

    // the skull turns in from the side and settles at the 3/4 angle, then breathes
    const settle = reducedMotion ? 1 : easeOutQuart(clamp01(t / 4.4));
    pointer.sx += (pointer.x - pointer.sx) * 0.04;
    pointer.sy += (pointer.y - pointer.sy) * 0.04;
    const sway = reducedMotion ? 0 : Math.sin(t * 0.55) * 0.04 * settle;
    rig.rotation.set(PITCH - pointer.sy * 0.05, YAW - (1 - settle) * SPIN_IN + sway + pointer.sx * 0.12, 0);
    rig.position.y = LIFT + (reducedMotion ? 0 : Math.sin(t * 0.9) * 0.022);

    // slow dolly in
    let dist = baseDist * (1 + (reducedMotion ? 0 : (1 - easeOutCubic(clamp01(t / 6))) * 0.16));

    // exit: push through the skull while the overlay dissolves
    let e = 0;
    if (exitAt !== null) {
      e = easeInOut(clamp01((now - exitAt) / exitMs));
      dist *= 1 - 0.36 * e;
    }
    camera.position.set(0, 0.3, dist);
    camera.lookAt(0, 0, 0);

    // moving highlights across the bone, like a slow turntable light
    if (!reducedMotion) {
      key.position.x = -3.6 + Math.sin(t * 0.32) * 0.7;
      rimA.position.z = -4.2 + Math.cos(t * 0.27) * 0.6;
    }
    glowMat.opacity = (0.34 + (reducedMotion ? 0 : Math.sin(t * 1.3) * 0.05)) * fade;

    renderer.toneMappingExposure = EXPOSURE * fade * (1 - 0.6 * e);
    renderer.render(scene, camera);
  }
  raf = requestAnimationFrame(tick);

  return {
    /** Begin the fade-in / turn-in (call once the overlay is ready to play). */
    start() {
      t0 = performance.now();
      running = true;
    },
    /** Camera push + fade out over `ms`. */
    exit(ms) {
      exitMs = ms;
      exitAt = performance.now();
    },
    /** Pointer position in -1..1 for a gentle parallax. */
    setPointer(x, y) {
      pointer.x = x;
      pointer.y = y;
    },
    dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      scene.traverse((o) => {
        if (!o.isMesh) return;
        o.geometry?.dispose();
        [].concat(o.material || []).forEach((m) => {
          m.map?.dispose?.();
          m.dispose?.();
        });
      });
      envRT.dispose();
      pmrem.dispose();
      draco.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    },
  };
}
