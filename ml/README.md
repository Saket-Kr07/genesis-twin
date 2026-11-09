# Genesis Twin – Part B: Health AI & Personal Twin (`ml/`)

Branch: `Ravneet`. Educational/research use only – **not medical advice**. Implements API contract **v1.1**.

## Quick start
```bash
pip install -r requirements.txt
python prepare_data.py     # downloads NHANES 2017-2018 -> data/processed/
python train_model.py      # trains + saves models/health_model.joblib
python test_predict.py     # self-check (formula fallback + trained model if present)
```
Backend import: `from ml.predict import predict_health` (run from the repo root; `ml/__init__.py` makes `ml` a package).

## Two functions
| Function | Used by | Output |
|---|---|---|
| `predict_health(age, sex, sleep, exercise, smoking, diet)` | backend (contract v1.1) | exactly 12 organ ids → `{"score": int, "vitals": {...}}`. Nothing else. |
| `predict_health_detailed(..., use_model=True)` | our scripts, UI badges | overall score, units, provenance labels, notes, model info, disclaimer |

### Contract inputs (`predict_health`)
| Input | Rule |
|---|---|
| age | int 20–80 |
| sex | `"male"` / `"female"` |
| sleep | number, 0–24 hours/night |
| exercise | int 0–7 days/week |
| smoking | int 0–100 cigarettes/day |
| diet | int 1–5 (5 = healthiest) |

Invalid input raises `ValueError`; nothing is clamped (bool, str, floats like 2.5, NaN are rejected).

### Conversion to the model's units (assumptions, need team confirmation)
- `exercise_min_week = days × 30` (`MINUTES_PER_EXERCISE_DAY`; 5 days ≈ the 150 min/week guideline).
- `smoking`: 0 → never; 1+ → "current" for the ML model, which has **no dose input** (it only knows never/former/current). Quantity therefore enters through documented **illustrative dose rules** (demo values, not medical predictions), with `dose = sqrt(cigarettes/100)` from 0 to 1:
  - **lungs, reproductive:** lifestyle smoking factor `0.85 − 0.75 × dose` (1/day ≈ 0.78, 10 ≈ 0.61, 20 ≈ 0.51, 40 ≈ 0.38, 100 = 0.10).
  - **heart:** score = `min(model score, same person as a never-smoker) − 20 × dose` points (`HEART_SMOKING_MAX_PENALTY`). Example (age 40 male): 0/day 99, 10/day 91, 40/day 85, 100/day 77. Heart rate and blood pressure stay as the model predicted; ejection fraction (an illustrative vital derived from the heart score) follows the score. In the detailed output a smoker's heart score is labelled `illustrative` with an `adjustments` entry and a `note`.
  - liver, kidneys and pancreas are not dose-adjusted.
- "Former smoker" cannot be expressed in the contract; it exists only in the detailed function.

## Vitals and where each number comes from
| Organ | Vitals (contract names) | Source |
|---|---|---|
| heart | heart_rate, blood_pressure `"sys/dia"` | **model_predicted** (illustrative if no model) |
| heart | ejection_fraction | illustrative (derived from heart score) |
| lungs | oxygen_saturation, breathing_rate, lung_capacity (litres; lower for female and with age) | illustrative |
| brain | neuro_inflammation_index (0–5, lower better), reaction_score (0–100) | illustrative |
| liver | alt, ast, bilirubin | model_predicted |
| stomach, intestines, pancreas | gut_inflammation (0–10, lower better) | illustrative |
| kidneys, bladder | egfr, creatinine | model_predicted (egfr calculated from predicted creatinine, CKD-EPI 2021); same values for both |
| kidneys, bladder | hydration (%) | illustrative |
| thyroid | glucose | model_predicted (NHANES fasting glucose) |
| thyroid | tsh, cortisol | illustrative |
| spleen | white_cell_count, cytokine_level | illustrative |
| spleen | pathogen_load | fixed `0.0`: healthy-body day-zero baseline (see below) |
| reproductive | hormone_indicators (0–100) | illustrative (equals the reproductive score) |

**Illustrative = demo value from a simple rule. Not a medical prediction and not clinically validated.** Scores of brain, lungs, stomach, intestines, bladder, spleen, thyroid and reproductive are illustrative too. Non-contract extras (systolic/diastolic BP, fasting glucose, HbA1c, sleep hours) exist only in the detailed output under `extra_vitals`.

## Pathogen load (agreed with Part D)
`spleen.pathogen_load` is a **relative** load, not copies/mL: **1.0 = the untreated reference-adult peak**, **0.0 = no or negligible pathogen**. Part B models no infection, so a healthy body always returns the day-zero baseline `0.0` (two-decimal display). Infected values come from Part D's `simulate_pathogen`.

## NHANES columns (2017-2018, "J" files)
| Need | File | Column(s) |
|---|---|---|
| age, sex | DEMO_J | `RIDAGEYR`, `RIAGENDR` |
| sleep | SLQ_J | `SLD012` |
| exercise | PAQ_J | `PAQ650/655/PAD660` (vigorous), `PAQ665/670/PAD675` (moderate) |
| smoking | SMQ_J | `SMQ020`, `SMQ040` |
| diet | DBQ_J | `DBQ700` (`6 − value`, 5 = excellent) |
| BP, pulse | BPX_J | `BPXSY1-4`, `BPXDI1-4`, `BPXPLS` |
| liver, kidney | BIOPRO_J | `LBXSATSI`, `LBXSASSI`, `LBXSTB`, `LBXSCR` |
| glucose | GLU_J / GHB_J | `LBXGLU`, `LBXGH` |

## Honest limitations
- Lifestyle explains little of blood-test variation → modest R²; report the metrics printed by `train_model.py`.
- NHANES here has no SpO₂, TSH or data for 8 of the organs → illustrative only.
- Exercise = recreational activity only; no survey weights; NHANES caps age at 80.
- Reference ranges in `predict.RANGES` are rough teaching thresholds, not diagnostic cut-offs.
- If `health_model.joblib` is missing or cannot be loaded (e.g. scikit-learn version mismatch), a formula baseline is used and a `RuntimeWarning` is raised; everything is then labelled `illustrative`.

## Other scripts
- `age_progression.py` – age 20→80, lifestyle fixed (uses the detailed function); `--csv`, `--json`, `--plot`.
- `twin_comparison.py` – `compare_twins(a, b)` (detailed function; minutes/week and smoking categories).
- `test_predict.py` – existing detailed tests + contract v1.1 tests.
