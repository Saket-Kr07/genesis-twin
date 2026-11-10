# Genesis Twin: API Contract

Version 1.1 | 9 Nov 2026 | Owner: Rakhi (Part A) | Based on Master Project Plan v2.2 | File: `backend/api-contract.md` on branch `rakhi` | Repo: github.com/Saket-Kr07/genesis-twin

> Every output of this platform is a simulation for research and education. It is not medical advice, and every screen must say so.

These shapes are fixed from the first hour so every part can build and test against dummy data. **Change them only after telling the whole team.** Until a real function exists, its owner publishes a dummy function with the same input and output.

Base URL (local): `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

---

## 1. Shared names

**Organ ids (12):** `brain`, `heart`, `lungs`, `liver`, `stomach`, `intestines`, `kidneys`, `bladder`, `pancreas`, `spleen`, `thyroid`, `reproductive`

**Systems (11):** `skeletal`, `muscular`, `nervous`, `cardiovascular`, `respiratory`, `digestive`, `urinary`, `endocrine`, `immune`, `reproductive`, `integumentary`

**Mesh naming rule:** `system__structure__side` (double underscores), e.g. `cardiovascular__heart`, `urinary__kidney__left`. Layer toggles, search, labels and health colours all read these names.

**Sex:** `male` or `female`.

**Roles:** `public` (no login), `pro`, `admin`. The API checks the role on every Pro/Admin endpoint.

**Auth header:** `Authorization: Bearer <access_token>`

**Errors:** all errors return `{"detail": "plain-language message"}` with status 400 (bad input), 401 (not logged in), 403 (wrong role), 404 (not found), 422 (validation).

---

## 2. Function shapes (between parts)

### B to A: `predict_health`

Input:

| Field | Type | Range |
|---|---|---|
| age | int | 20 to 80 |
| sex | string | male or female |
| sleep | number | hours per night |
| exercise | int | days per week (0 to 7) |
| smoking | int | cigarettes per day |
| diet | int | 1 to 5 |

Output: for each organ id, a `score` (0 to 100, higher is healthier) and `vitals` (name and value pairs).

```json
{
  "heart": {
    "score": 82,
    "vitals": { "heart_rate": 72, "blood_pressure": "120/80", "ejection_fraction": 60 }
  },
  "lungs": {
    "score": 76,
    "vitals": { "oxygen_saturation": 97, "breathing_rate": 15, "lung_capacity": 4.8 }
  }
}
```

All 12 organ ids must be present. Every vital has a number (never `null`), except `blood_pressure`, which is a string like `"120/80"`. Scores are integers.

Vitals per organ (v1.1 split: liver biomarkers and gut indicators are separate):

| Organ id | Vitals |
|---|---|
| heart | heart_rate, blood_pressure, ejection_fraction |
| lungs | oxygen_saturation, breathing_rate, lung_capacity |
| brain | neuro_inflammation_index, reaction_score |
| liver | alt, ast, bilirubin |
| stomach, intestines, pancreas | gut_inflammation |
| kidneys, bladder | egfr, creatinine, hydration |
| thyroid | glucose, tsh, cortisol |
| spleen | white_cell_count, cytokine_level, pathogen_load |
| reproductive | hormone_indicators (one number, 0 to 100) |

Units and direction (v1.1). All values are **illustrative demo values, not clinically validated**:

| Vital | Unit / scale | Healthier is |
|---|---|---|
| heart_rate | beats per minute | closer to normal |
| blood_pressure | mmHg, `"systolic/diastolic"` string | closer to normal |
| ejection_fraction | % | higher |
| oxygen_saturation | % | higher |
| breathing_rate | breaths per minute | closer to normal |
| lung_capacity | litres | higher (demo logic lowers it for female and with age) |
| neuro_inflammation_index | 0 to 5 index | lower |
| reaction_score | 0 to 100 | higher |
| alt, ast | U/L | lower |
| bilirubin | mg/dL | lower |
| gut_inflammation | 0 to 10 index | lower |
| egfr | mL/min/1.73 m² | higher |
| creatinine | mg/dL | lower |
| hydration | % | higher |
| glucose | mg/dL | closer to normal |
| tsh | mIU/L | closer to normal |
| cortisol | µg/dL | closer to normal |
| white_cell_count | ×10⁹/L | closer to normal (about 4 to 11) |
| cytokine_level | pg/mL | lower |
| pathogen_load | same units as Part D `load` | lower; 0.0 for a healthy twin (**pending Saket's confirmation**) |
| hormone_indicators | single number, 0 to 100 | higher |

Input notes: `diet` 5 is the healthiest and 1 the worst (**to be confirmed**). Exercise is days per week. More cigarettes per day means worse results. The API rejects invalid inputs with a 422 before `predict_health` is called, so `predict_health` should raise `ValueError` on bad input and not clamp it. Import path: `from ml.predict import predict_health`. The output must stay exactly as above (no extra keys).

Skeletal and skin values (bone_density, muscle_mass, barrier_health) may be added later; C reads only organ ids and scores.

### D to A: `simulate_pathogen`

Input: `pathogen_id` (string), `day` (int, 0 to 30), `treatment` (number, 0 to 1).

```json
{
  "load": 3.4,
  "curve": [ { "day": 0, "load": 1.0 }, { "day": 1, "load": 2.1 } ],
  "organs": {
    "lungs": { "score": 54, "vitals": { "oxygen_saturation": 91, "breathing_rate": 22 } }
  }
}
```

`organs` maps organ id to score and vitals. Organs not affected may be omitted.

### D to A: `fit_pathogen`

Input: CSV file contents. Columns: `day`, `load`. Optional: `tissue`, `receptor`. At least 5 time points; no missing or negative values.

```json
{
  "parameters": { "growth_rate": { "value": 0.8, "low": 0.7, "high": 0.9 } },
  "validation_errors": []
}
```

If the file is bad, `parameters` is `null` and `validation_errors` is a list of plain-language strings.

### F to A: `get_sources`

Input: `limit` (int).

```json
[
  {
    "title": "Paper title",
    "doi": "10.1234/example",
    "date": "2026-10-30",
    "type": "peer_reviewed",
    "change": "Updated viral clearance rate",
    "model_version": "v0.1.0"
  }
]
```

`type` is `peer_reviewed` or `preprint`. Preprints must be flagged as not peer reviewed everywhere they appear.

---

## 3. REST endpoints

Access: **Public** = no login. **Pro** = logged in with role `pro` (or `admin`). **Admin** = role `admin`.

### Health

| Method | Path | Access | Response |
|---|---|---|---|
| GET | `/health` | Public | `{"status": "ok"}` |

### Auth

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| POST | `/auth/register` | Public | `{"email": "a@b.com", "password": "..."}` | `{"id": 1, "email": "a@b.com", "role": "public"}` |
| POST | `/auth/login` | Public | `{"email": "a@b.com", "password": "..."}` | `{"access_token": "<jwt>", "token_type": "bearer", "role": "public"}` |

The JWT carries the user id and role. Registered users start as role `public` until a payment sets them to `pro`.

### Body and twin

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| GET | `/body/{sex}` | Public | path: `male` or `female` | Avatar file list and organ list (below) |
| POST | `/twin/predict` | Public | `age, sex, sleep, exercise, smoking, diet` | Output of `predict_health` |
| POST | `/twin/personal` | Pro | measurements: `age, sex, height_cm, weight_kg, measurements{}`, or a scan upload | `predict_health` output plus `morph` parameters for the viewer |

`GET /body/{sex}` response:

```json
{
  "sex": "male",
  "systems": [
    { "system": "skeletal", "glb_url": "/static/models/male/skeletal.glb" }
  ],
  "organs": [
    { "id": "heart", "system": "cardiovascular", "mesh": "cardiovascular__heart" }
  ]
}
```

### Pathogens

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| GET | `/pathogens` | Public: presets, Pro: all | none | `[{"id": "respiratory_virus", "name": "...", "kind": "virus", "preset": true}]` |
| POST | `/pathogens/upload` | Pro | multipart CSV | Output of `fit_pathogen` plus `pathogen_id` |
| POST | `/pathogens/simulate` | Public: presets, Pro | `{"pathogen_id": "...", "day": 5, "treatment": 0.3}` | Output of `simulate_pathogen` |

Preset ids for the demo: `respiratory_virus`, `gut_virus`, `bloodstream_bacterium` (clearly labelled sample parameters, not real outbreaks).

### Research

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| GET | `/research/sources` | Public: latest 5, Pro: all | optional `?limit=` | Output of `get_sources` |

### Admin

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| POST | `/admin/models/approve` | Admin | `{"candidate_id": 3, "decision": "approve"}` (or `"reject"`) | `{"model_version": "v0.2.0", "status": "approved"}` |

### Experiments

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| POST | `/experiments` | Pro | `{"name": "...", "pathogen_id": "...", "parameters": {}, "seed": 42, "fork_of": null}` | saved experiment with `id`, `model_version`, `created_at` |
| GET | `/experiments` | Pro | none | list of the user's experiments (also used for export) |

An experiment record stores parameters, seed and model version so it is reproducible.

### Billing

| Method | Path | Access | Request | Response |
|---|---|---|---|---|
| POST | `/billing/checkout` | Logged in | `{"plan": "monthly"}` or `"yearly"` | `{"checkout_url": "..."}` (test mode only) |
| POST | `/billing/webhook` | Provider | provider payload | `200 OK`; the API verifies the signature, then sets role `pro` with an expiry date |

Fallback if the payment gateway is blocked: a mock checkout endpoint that sets the role, clearly labelled as a test. Card details are never stored; the provider handles them.

---

## 4. Who connects to what

- **A to C, E:** REST JSON as above. Organ scores drive colours; C reads only organ ids and scores.
- **B to A:** `predict_health`. **D to A:** `simulate_pathogen`, `fit_pathogen`. **F to A:** `get_sources`.
- CORS allows `http://localhost:5173` (Vite dev server).

## 5. Change log

| Date | Change | By |
|---|---|---|
| 7 Nov 2026 | v1.0 first version from plan v2.2, Sections 8 and 9 | Rakhi |
| 9 Nov 2026 | v1.1: `predict_health` vitals split (ALT, AST, bilirubin under liver only; `gut_inflammation` under stomach, intestines, pancreas); added units, direction, no-null and integer-score rules. Agreed with Part B (Ravneet). `pathogen_load` scale pending Saket (Part D). | Rakhi |
