# Genesis Twin – Part B: Health AI & Personal Twin (`ml/`)

Branch: `Ravneet`. Educational/research use only – **not medical advice**.

## Quick start
```bash
pip install -r requirements.txt
python prepare_data.py     # downloads NHANES 2017-2018 (needs internet) -> data/processed/
python train_model.py      # trains + saves models/health_model.joblib
python predict.py          # demo call
python test_predict.py     # self-check
```
No trained model yet? `predict_health()` automatically uses a **formula baseline** with the identical output format (everything labelled `illustrative`). Check `result["model_info"]["mode"]`: `"ml_model"` or `"formula_baseline"`.

## API
```python
from predict import predict_health
r = predict_health(age=35, sex="female", sleep=7.5, exercise=150, smoking="never", diet=4)
r["overall_health"]["score"]            # 0-100
r["organs"]["heart"]["score"]           # same for all 12 organ IDs
r["organs"]["heart"]["vitals"]["systolic_bp"]   # {"value":..., "unit":..., "label":...}
```
| Input | Meaning |
|---|---|
| age | 18–100 |
| sex | `"male"` / `"female"` |
| sleep | hours per night |
| exercise | moderate-equivalent min/week (vigorous ×2) |
| smoking | `"never"` / `"former"` / `"current"` |
| diet | 1 (poor) – 5 (excellent), self-rated |

Organ IDs (fixed order in `predict.ORGAN_IDS`): brain, heart, lungs, liver, stomach, intestines, kidneys, bladder, pancreas, spleen, thyroid, reproductive.

## Labels
| Label | Meaning |
|---|---|
| `measured` | value the user typed in (self-reported) |
| `model_predicted` | estimated by the NHANES-trained model |
| `illustrative` | rule/formula for demo – not a real measurement |

| Organ | Score source | Vitals |
|---|---|---|
| heart, liver, kidneys, pancreas | model-predicted biomarkers → reference-range scoring (`illustrative` in baseline mode) | BP/pulse; ALT/AST/bilirubin; creatinine + eGFR (CKD-EPI 2021); glucose/HbA1c |
| lungs, brain, stomach, intestines, bladder, spleen, thyroid, reproductive | illustrative lifestyle + age rules | lungs SpO₂/resp. rate and thyroid TSH are **illustrative**; brain shows measured sleep; others none |
| overall | weighted mean of 12 organs | labelled `illustrative` because 8 organs are |

## NHANES columns (2017-2018, "J" files)
| Need | File | Column(s) | How it's used |
|---|---|---|---|
| age | DEMO_J | `RIDAGEYR` | adults ≥18; 80 = "80 and over" |
| sex | DEMO_J | `RIAGENDR` | 1 male, 2 female |
| sleep | SLQ_J | `SLD012` | weekday sleep hours |
| exercise | PAQ_J | `PAQ650/655/PAD660` (vigorous), `PAQ665/670/PAD675` (moderate) | days × min; vigorous ×2 |
| smoking | SMQ_J | `SMQ020`, `SMQ040` | never / former / current |
| diet | DBQ_J | `DBQ700` | `6 − value` so 5 = excellent |
| BP, pulse | BPX_J | `BPXSY1-4`, `BPXDI1-4`, `BPXPLS` | targets |
| liver | BIOPRO_J | `LBXSATSI` (ALT), `LBXSASSI` (AST), `LBXSTB` (bilirubin) | targets |
| kidney | BIOPRO_J | `LBXSCR` | target; eGFR computed |
| glucose | GLU_J / GHB_J | `LBXGLU` (fasting), `LBXGH` (HbA1c) | targets |

Please double-check variable names against the CDC codebooks (https://wwwn.cdc.gov/nchs/nhanes/) after downloading; if a column errors, that is the first place to look.

## Honest limitations
- Lifestyle explains only a small part of blood-test variation, so expect modest R² in `train_model.py`; predictions regress toward typical values. Report the printed metrics.
- NHANES here has no SpO₂, TSH (this cycle), or data for 8 of the organs → illustrative only.
- Exercise counts recreational activity only; NHANES survey weights are not used.
- Reference ranges in `predict.RANGES` are rough teaching thresholds, not diagnostic cut-offs.

## Notes
- Your venv can live inside `ml/` (it is git-ignored). Only 6 packages are needed; see `requirements.txt`.
- Works on Python 3.9+.

## Other scripts
- `age_progression.py` – age 20→80, lifestyle fixed; `--csv`, `--json`, `--plot`.
- `twin_comparison.py` – `compare_twins(a, b)`: overall, 12 organ and shared-vital differences.
