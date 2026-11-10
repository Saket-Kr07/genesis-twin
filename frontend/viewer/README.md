# Genesis Twin — BodyViewer (Part C)

3D body viewer for Genesis Twin, built with React Three Fiber. Research and education only, not medical advice.

## Run it

```bash
cd frontend/viewer
npm install
npm run dev
```

Open http://localhost:5173.

## Models

- Put the Z-Anatomy `.glb` files anywhere inside `public/` (for example `public/models/`). The viewer finds them automatically. You don't need to list them anywhere.
- **File names decide the layer.** Name a file after its system, for example `skeleton.glb`, `muscles.glb`, `nervous.glb`, `cardiovascular.glb`, `respiratory.glb`, `digestive.glb`, `urinary.glb`, `lymphatic.glb`, `skin.glb`.
  - A file whose name matches no system (for example `organs.glb` or `full_body.glb`) always loads. Each mesh inside it is sorted by its own name.
- **Sex.** Put `female` in the file name for female models (for example `female_skeleton.glb`). Put `male` in the name for male-only files.
  - A file with neither word is used for both.
  - If there is no female file at all, the male meshes are shown with a note.
- **Big files.** GLB files are not committed to Git (see `.gitignore`), because GitHub rejects files over 100 MB. Share them through the team drive.
- **Draco compression.** Run `npm run compress`. It shrinks every GLB in place and keeps the originals in `originals/`. Mesh names are kept, so clicking still works.

## Naming contract

Every mesh gets `userData.gt.id` in the form `system__structure__side`, for example `urinary__kidney__left`. This is worked out from Z-Anatomy's names at load time, in `src/registry.js`. Organ meshes also get one of the 12 shared organ ids (`brain, heart, lungs, liver, stomach, intestines, kidneys, bladder, pancreas, spleen, thyroid, reproductive`), and the API scores colour them by that id.

## API

- The viewer calls `POST {VITE_API_BASE}/twin/predict` with `{ age, sex, sleep, exercise, smoking, diet }`.
- The default base URL is `http://localhost:8000`. To change it, create `.env` with `VITE_API_BASE=http://your-host:8000`.
- If the API is offline, a dummy formula with the same output shape is used, and the Lifestyle panel says so.

## Controls

| Action | How |
|---|---|
| Rotate | Drag |
| Zoom | Scroll |
| Pan | Right-drag |
| Select | Click |
| Focus | Double-click |
| Snap to a view | View cube (bottom right) |
| Find a structure | Search box, flies the camera to it |

## Credits and licences

- **Z-Anatomy**: 3D anatomy models, CC BY-SA 4.0 — https://www.z-anatomy.com
- **BodyParts3D** (DBCLS): base anatomy data, CC BY-SA 2.1 JP — https://lifesciencedb.jp/bp3d/
- **three.js, React Three Fiber, drei**: MIT

The anatomy meshes are adapted under share-alike licences, so derived model files keep the same licence.
