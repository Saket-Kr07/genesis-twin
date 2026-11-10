// Draco-compresses every .glb in public/ in place. Originals are copied to originals/ first.
// Run: npm run compress
// It only compresses geometry; it does NOT merge meshes, so names and clicking keep working.
import { readdirSync, mkdirSync, copyFileSync, existsSync, renameSync, statSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const pub = join(root, 'public');
const backup = join(root, 'originals');
const cli = join(root, 'node_modules', '@gltf-transform', 'cli', 'bin', 'cli.js');

const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? walk(join(d, e.name)) : e.name.toLowerCase().endsWith('.glb') ? [join(d, e.name)] : []);

for (const file of walk(pub)) {
  const rel = relative(pub, file);
  const saved = join(backup, rel);
  if (existsSync(saved)) { console.log(`skip (already done): ${rel}`); continue; }
  mkdirSync(dirname(saved), { recursive: true });
  copyFileSync(file, saved);
  const tmp = file + '.tmp.glb';
  const before = statSync(file).size;
  execFileSync(process.execPath, [cli, 'draco', file, tmp], { stdio: 'inherit' });
  renameSync(tmp, file);
  const after = statSync(file).size;
  console.log(`${rel}: ${(before / 1e6).toFixed(1)} MB -> ${(after / 1e6).toFixed(1)} MB`);
}
