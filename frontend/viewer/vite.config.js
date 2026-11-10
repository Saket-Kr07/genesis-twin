import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { readdirSync, existsSync } from 'node:fs';
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

export default defineConfig({
  plugins: [react(), glbManifest()],
});
