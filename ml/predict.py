"""
Genesis Twin - Part B: health prediction.

    from predict import predict_health
    result = predict_health(age=35, sex="female", sleep=7.5, exercise=150,
                            smoking="never", diet=4)

Inputs
    age       years (18-100)
    sex       "male" | "female"
    sleep     hours per night
    exercise  moderate-equivalent minutes per week (vigorous counts double)
    smoking   "never" | "former" | "current"   (True/False also accepted)
    diet      self-rated 1 (poor) ... 5 (excellent)

Every number in the output carries a label:
    measured         = value the user typed in (self-reported)
    model_predicted  = estimated by the ML model trained on NHANES
    illustrative     = simple rule/formula for demo purposes - NOT real medical data

If models/health_model.joblib is missing, a formula baseline is used and every
estimate is labelled "illustrative". The output format is identical.
EDUCATIONAL / RESEARCH USE ONLY - not medical advice.
"""
from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

ORGAN_IDS = ["brain", "heart", "lungs", "liver", "stomach", "intestines",
             "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive"]
FEATURES = ["age", "sex_male", "sleep_hours", "exercise_min_week", "smoking", "diet_score"]
MODEL_PATH = Path(os.environ.get("GENESIS_MODEL_PATH",
                                 Path(__file__).resolve().parent / "models" / "health_model.joblib"))

MEASURED, MODEL, ILLUSTRATIVE = "measured", "model_predicted", "illustrative"
DISCLAIMER = ("Educational/research simulation. Not medical advice. Scores are simple "
              "summaries, not diagnoses. Values labelled 'illustrative' are not real measurements.")


# ----------------------------------------------------------------- helpers
def _trap(v: float, z_lo: float, f_lo: float, f_hi: float, z_hi: float) -> float:
    """Trapezoid score: 100 inside [f_lo, f_hi], falling linearly to 0 at z_lo / z_hi."""
    if v <= z_lo or v >= z_hi:
        return 0.0
    if v < f_lo:
        return 100 * (v - z_lo) / (f_lo - z_lo)
    if v <= f_hi:
        return 100.0
    return 100 * (z_hi - v) / (z_hi - f_hi)


# (zero_low, full_low, full_high, zero_high) - rough textbook reference ranges, for teaching only
RANGES = {
    "sbp": (80, 95, 120, 180), "dbp": (45, 60, 80, 120), "pulse": (35, 55, 80, 130),
    "alt": (-1, 0, 30, 200), "ast": (-1, 0, 35, 200), "bilirubin": (-1, 0.1, 1.2, 5),
    "egfr": (15, 90, 200, 300), "glucose": (40, 70, 99, 200), "hba1c": (3, 4, 5.6, 10),
}


def _score(name: str, v: float) -> float:
    return _trap(v, *RANGES[name])


def _egfr_ckd_epi_2021(creatinine: float, age: float, male: bool) -> float:
    k, a = (0.9, -0.302) if male else (0.7, -0.241)
    r = creatinine / k
    return 142 * min(r, 1) ** a * max(r, 1) ** -1.200 * 0.9938 ** age * (1 if male else 1.012)


def _vital(value, unit, label, note=None) -> dict:
    d = {"value": None if value is None else round(float(value), 2), "unit": unit, "label": label}
    if note:
        d["note"] = note
    return d


def _normalise(age, sex, sleep, exercise, smoking, diet) -> dict[str, Any]:
    age = float(age)
    if not 18 <= age <= 100:
        raise ValueError("age must be between 18 and 100 (the model is trained on adults)")
    s = str(sex).strip().lower()
    if s in ("m", "male", "man"):
        male = 1
    elif s in ("f", "female", "woman"):
        male = 0
    else:
        raise ValueError("sex must be 'male' or 'female'")
    sleep, exercise, diet = float(sleep), float(exercise), float(diet)
    if not 0 <= sleep <= 24:
        raise ValueError("sleep must be 0-24 hours")
    if exercise < 0:
        raise ValueError("exercise must be >= 0 minutes/week")
    if not 1 <= diet <= 5:
        raise ValueError("diet must be between 1 (poor) and 5 (excellent)")
    if isinstance(smoking, bool):
        smoking = "current" if smoking else "never"
    smk = {"never": 0, "former": 1, "current": 2}.get(str(smoking).strip().lower())
    if smk is None:
        raise ValueError("smoking must be 'never', 'former' or 'current'")
    return {"age": age, "sex_male": male, "sleep_hours": sleep,
            "exercise_min_week": exercise, "smoking": smk, "diet_score": diet}


@lru_cache(maxsize=1)
def _load_bundle():
    if not MODEL_PATH.exists():
        return None
    import joblib
    return joblib.load(MODEL_PATH)


# ------------------------------------------------- biomarker estimation
def _biomarkers_ml(x: dict, bundle: dict) -> dict[str, float]:
    import pandas as pd
    row = pd.DataFrame([[x[f] for f in bundle["features"]]], columns=bundle["features"])
    return {t: float(m.predict(row)[0]) for t, m in bundle["models"].items()}


def _biomarkers_formula(x: dict) -> dict[str, float]:
    """Hand-written rough trends (illustrative only, not fitted to real data)."""
    age, male, sleep = x["age"], x["sex_male"], x["sleep_hours"]
    ex = min(x["exercise_min_week"], 300) / 300          # 0..1
    cur = 1 if x["smoking"] == 2 else 0
    poor_diet = 3 - x["diet_score"]                      # +2 poor ... -2 excellent
    short_sleep = max(0.0, 7 - sleep)
    return {
        "sbp": 100 + 0.5 * age + 3 * male + 4 * cur - 6 * ex + 1.5 * poor_diet + 1.5 * short_sleep,
        "dbp": 62 + 0.12 * age + 2 * male + 2 * cur - 3 * ex + 1.0 * poor_diet,
        "pulse": 70 + 2 * (1 - male) + 5 * cur - 8 * ex + 1.0 * poor_diet,
        "alt": 18 + 7 * male + 2 * poor_diet + 2 * cur,
        "ast": 21 + 3 * male + 0.05 * age + 1.0 * poor_diet,
        "bilirubin": 0.65 + 0.15 * male - 0.1 * cur,
        "creatinine": 0.70 + 0.20 * male + 0.004 * age,
        "glucose": 88 + 0.25 * age + 2 * poor_diet + 2 * cur - 4 * ex,
        "hba1c": 5.0 + 0.008 * age + 0.05 * poor_diet + 0.05 * cur - 0.1 * ex,
    }


# ------------------------------------------------- illustrative organs
# per-organ lifestyle weights (sleep, exercise, smoking, diet) and how strongly age hurts it
ILLUSTRATIVE_ORGANS = {
    "brain":        ((0.35, 0.20, 0.15, 0.30), 0.35),
    "lungs":        ((0.00, 0.30, 0.60, 0.10), 0.30),
    "stomach":      ((0.20, 0.00, 0.30, 0.50), 0.15),
    "intestines":   ((0.15, 0.25, 0.00, 0.60), 0.20),
    "bladder":      ((0.00, 0.20, 0.60, 0.20), 0.15),
    "spleen":       ((0.30, 0.30, 0.10, 0.30), 0.10),
    "thyroid":      ((0.30, 0.10, 0.30, 0.30), 0.15),
    "reproductive": ((0.25, 0.25, 0.30, 0.20), 0.30),
}
OVERALL_WEIGHTS = {"brain": 1.3, "heart": 1.5, "lungs": 1.3, "liver": 1.1, "stomach": 0.8,
                   "intestines": 0.8, "kidneys": 1.2, "bladder": 0.7, "pancreas": 1.0,
                   "spleen": 0.6, "thyroid": 0.8, "reproductive": 0.7}


def _lifestyle_factors(x: dict) -> tuple[float, float, float, float]:
    f_sleep = _trap(x["sleep_hours"], 3, 7, 9, 12) / 100
    f_ex = min(x["exercise_min_week"] / 150, 1.0)        # 150 min/week = common guideline
    f_smoke = {0: 1.0, 1: 0.7, 2: 0.2}[x["smoking"]]
    f_diet = (x["diet_score"] - 1) / 4
    return f_sleep, f_ex, f_smoke, f_diet


def _illustrative_score(organ: str, x: dict) -> float:
    weights, age_sens = ILLUSTRATIVE_ORGANS[organ]
    mix = sum(w * f for w, f in zip(weights, _lifestyle_factors(x)))
    age_prog = min(max((x["age"] - 20) / 60, 0.0), 1.33)
    return 100 * (1 - age_sens * age_prog) * (0.55 + 0.45 * mix)


# ------------------------------------------------- main function
def predict_health(age, sex, sleep, exercise, smoking, diet, use_model: bool = True) -> dict:
    x = _normalise(age, sex, sleep, exercise, smoking, diet)
    bundle = _load_bundle() if use_model else None
    if bundle:
        bio, bio_label, mode = _biomarkers_ml(x, bundle), MODEL, "ml_model"
    else:
        bio, bio_label, mode = _biomarkers_formula(x), ILLUSTRATIVE, "formula_baseline"
    bio["egfr"] = _egfr_ckd_epi_2021(bio["creatinine"], x["age"], bool(x["sex_male"]))
    _, _, f_smoke, _ = _lifestyle_factors(x)

    def mean_score(*names):
        return sum(_score(n, bio[n]) for n in names) / len(names)

    organs: dict[str, dict] = {}
    organs["heart"] = {"score": mean_score("sbp", "dbp", "pulse"), "score_label": bio_label,
        "vitals": {"systolic_bp": _vital(bio["sbp"], "mmHg", bio_label),
                   "diastolic_bp": _vital(bio["dbp"], "mmHg", bio_label),
                   "resting_heart_rate": _vital(bio["pulse"], "bpm", bio_label)}}
    organs["liver"] = {"score": mean_score("alt", "ast", "bilirubin"), "score_label": bio_label,
        "vitals": {"alt": _vital(bio["alt"], "U/L", bio_label),
                   "ast": _vital(bio["ast"], "U/L", bio_label),
                   "bilirubin": _vital(bio["bilirubin"], "mg/dL", bio_label)}}
    organs["kidneys"] = {"score": mean_score("egfr"), "score_label": bio_label,
        "vitals": {"creatinine": _vital(bio["creatinine"], "mg/dL", bio_label),
                   "egfr": _vital(bio["egfr"], "mL/min/1.73m2", bio_label,
                                  "calculated from predicted creatinine with CKD-EPI 2021")}}
    organs["pancreas"] = {"score": mean_score("glucose", "hba1c"), "score_label": bio_label,
        "vitals": {"fasting_glucose": _vital(bio["glucose"], "mg/dL", bio_label),
                   "hba1c": _vital(bio["hba1c"], "%", bio_label)}}

    for organ in ILLUSTRATIVE_ORGANS:
        organs[organ] = {"score": _illustrative_score(organ, x), "score_label": ILLUSTRATIVE, "vitals": {}}

    organs["brain"]["vitals"] = {"sleep_hours": _vital(x["sleep_hours"], "h/night", MEASURED, "self-reported input")}
    organs["lungs"]["vitals"] = {
        "oxygen_saturation": _vital(min(99.0, max(90.0, 98.5 - 2.5 * (1 - f_smoke) - 0.02 * max(0, x["age"] - 30))),
                                    "%", ILLUSTRATIVE, "demo value; no oxygen data in this dataset"),
        "respiratory_rate": _vital(14 + 3 * (1 - f_smoke), "breaths/min", ILLUSTRATIVE)}
    organs["thyroid"]["vitals"] = {
        "tsh": _vital(1.8 + 0.01 * (x["age"] - 40), "mIU/L", ILLUSTRATIVE, "demo value; TSH is not in the training data")}
    for o in ("stomach", "intestines", "bladder", "spleen", "reproductive"):
        organs[o]["vitals"] = {}
        organs[o]["note"] = "No reliable vitals available for this organ; score is illustrative."

    for o in organs.values():
        o["score"] = round(o["score"], 1)
    total_w = sum(OVERALL_WEIGHTS.values())
    overall = sum(organs[o]["score"] * OVERALL_WEIGHTS[o] for o in ORGAN_IDS) / total_w

    return {
        "inputs": {
            "age": _vital(x["age"], "years", MEASURED), "sex": {"value": "male" if x["sex_male"] else "female", "label": MEASURED},
            "sleep": _vital(x["sleep_hours"], "h/night", MEASURED),
            "exercise": _vital(x["exercise_min_week"], "min/week", MEASURED),
            "smoking": {"value": ["never", "former", "current"][x["smoking"]], "label": MEASURED},
            "diet": _vital(x["diet_score"], "1-5", MEASURED)},
        "overall_health": {"score": round(overall, 1), "label": ILLUSTRATIVE,
                           "note": "weighted mean of the 12 organ scores; 8 of them are illustrative"},
        "organs": {o: organs[o] for o in ORGAN_IDS},
        "model_info": {"mode": mode, "trained_on": bundle["trained_on"] if bundle else None},
        "disclaimer": DISCLAIMER,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(predict_health(35, "female", 7.5, 150, "never", 4), indent=2))
