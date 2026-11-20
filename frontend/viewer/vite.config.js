import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readdirSync, existsSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
const publicDir = join(root, 'public');

// Finds every .glb anywhere inside public/ so you never have to list files by hand.
function scanGlb(dir, base = '') {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    if (d.isDirectory()) return scanGlb(join(dir, d.name), `${base}${d.name}/`);
    return d.name.toLowerCase().endsWith('.glb') ? [`${base}${d.name}`] : [];
  });
}

function glbManifest() {
  return {
    name: 'glb-manifest',
    configureServer(server) {
      server.middlewares.use('/models-manifest.json', (_req, res) => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(scanGlb(publicDir)));
      });
    },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'models-manifest.json',
        source: JSON.stringify(scanGlb(publicDir)),
      });
    },
  };
}

// Serves the Draco decoder from three.js at /draco/ so models load without internet.
const dracoDir = join(root, 'node_modules', 'three', 'examples', 'jsm', 'libs', 'draco', 'gltf');
function localDraco() {
  return {
    name: 'local-draco',
    configureServer(server) {
      server.middlewares.use('/draco', (req, res, next) => {
        const f = join(dracoDir, (req.url || '').split('?')[0].replace(/^\/+/, ''));
        if (!f.startsWith(dracoDir) || !existsSync(f)) return next();
        if (f.endsWith('.wasm')) res.setHeader('Content-Type', 'application/wasm');
        if (f.endsWith('.js')) res.setHeader('Content-Type', 'text/javascript');
        res.end(readFileSync(f));
      });
    },
    generateBundle() {
      if (!existsSync(dracoDir)) return;
      for (const name of readdirSync(dracoDir)) {
        this.emitFile({ type: 'asset', fileName: `draco/${name}`, source: readFileSync(join(dracoDir, name)) });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), glbManifest(), localDraco()],
});
