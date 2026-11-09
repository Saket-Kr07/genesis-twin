"""
Genesis Twin - Part B: health prediction (API contract v1.1).

Two functions
-------------
predict_health(age, sex, sleep, exercise, smoking, diet)          <- what the backend calls
    Strict contract output: exactly the 12 organ ids, each {"score": int, "vitals": {...}}.
    Inputs (contract units):
        age       int, 20-80
        sex       "male" | "female"
        sleep     hours per night (number, 0-24)
        exercise  int, days per week, 0-7
        smoking   int, cigarettes per day, 0-100
        diet      int, 1-5 (5 = healthiest)
    Raises ValueError on invalid input. Never clamps.

predict_health_detailed(age, sex, sleep, exercise, smoking, diet, use_model=True)
    The richer output used by our own scripts: overall score, units, provenance labels
    ("measured" / "model_predicted" / "illustrative"), notes, model info, disclaimer.
    Units here: exercise = minutes per week, smoking = "never"/"former"/"current" or an
    int cigarettes per day, age 18-100.

How exercise / smoking are converted (strict -> detailed)
    exercise_min_week = days * 30           (assumption: ~30 min per exercise day; 5 days = 150 min)
    smoking           = cigarettes per day  (0 -> never; 1+ -> "current" for the ML model,
                                             plus the illustrative dose rules below)

Smoking dose (illustrative, documented demo rule - NOT a medical prediction)
    The trained model only knows never / former / current, so it cannot react to HOW MUCH
    someone smokes. dose = sqrt(cigarettes_per_day / 100), from 0 (none) to 1 (100/day).
      lungs, reproductive (illustrative organs): lifestyle smoking factor = 0.85 - 0.75 * dose
      heart: score = min(model-based score, same person as a never-smoker)
                     - HEART_SMOKING_MAX_PENALTY (20 points) * dose
             heart_rate and blood_pressure stay exactly as the model predicted; the heart SCORE
             carries the adjustment (and so does ejection_fraction, which is an illustrative vital
             derived from the heart score). In the detailed output a smoker's heart
             score is labelled "illustrative" and explained in `note` / `adjustments`.
    More cigarettes per day therefore always give a worse (or equal) lungs, reproductive and heart
    score; liver, kidneys and pancreas are not adjusted for dose.

Pathogen load (Part D agreement)
    spleen.pathogen_load is a RELATIVE load (not copies/mL): 1.0 = the untreated reference-adult
    peak, 0.0 = no or negligible pathogen. Part B models no infection, so it always reports the
    healthy-body day-zero baseline 0.0 (two-decimal display). Infected values come from Part D.

Provenance (which numbers are real model output?)
    model_predicted : heart_rate, blood_pressure, alt, ast, bilirubin, creatinine, egfr
                      (egfr is calculated from the predicted creatinine), glucose
                      -- NHANES-trained model. With no trained model they are "illustrative".
    illustrative    : every other vital, the scores of 8 organs and the smoking-dose adjustment of the heart score. These are demo values
                      from simple rules, NOT medical predictions and NOT clinically validated.
    measured        : values the user typed in (detailed output only).

EDUCATIONAL / RESEARCH USE ONLY - not medical advice.
"""
from __future__ import annotations

import math
import os
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

ORGAN_IDS = ["brain", "heart", "lungs", "liver", "stomach", "intestines",
             "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive"]
FEATURES = ["age", "sex_male", "sleep_hours", "exercise_min_week", "smoking", "diet_score"]
TARGETS = ["sbp", "dbp", "pulse", "alt", "ast", "bilirubin", "creatinine", "glucose", "hba1c"]
MODEL_PATH = Path(os.environ.get("GENESIS_MODEL_PATH",
                                 Path(__file__).resolve().parent / "models" / "health_model.joblib"))

MEASURED, MODEL, ILLUSTRATIVE = "measured", "model_predicted", "illustrative"
DISCLAIMER = ("Educational/research simulation. Not medical advice. Scores are simple "
              "summaries, not diagnoses. Values labelled 'illustrative' are not real measurements.")

# ---- API contract v1.1 -------------------------------------------------------------
CONTRACT_VERSION = "1.1"
MINUTES_PER_EXERCISE_DAY = 30          # assumption: needs team confirmation
HEART_SMOKING_MAX_PENALTY = 20.0       # illustrative: max heart-score points removed at 100 cigarettes/day
CONTRACT_VITALS = {                     # exact names and order from the contract
    "brain": ("neuro_inflammation_index", "reaction_score"),
    "heart": ("heart_rate", "blood_pressure", "ejection_fraction"),
    "lungs": ("oxygen_saturation", "breathing_rate", "lung_capacity"),
    "liver": ("alt", "ast", "bilirubin"),
    "stomach": ("gut_inflammation",),
    "intestines": ("gut_inflammation",),
    "kidneys": ("egfr", "creatinine", "hydration"),
    "bladder": ("egfr", "creatinine", "hydration"),
    "pancreas": ("gut_inflammation",),
    "spleen": ("white_cell_count", "cytokine_level", "pathogen_load"),
    "thyroid": ("glucose", "tsh", "cortisol"),
    "reproductive": ("hormone_indicators",),
}


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
    if isinstance(value, str) or value is None:
        v = value
    elif float(value).is_integer() and isinstance(value, int):
        v = int(value)
    else:
        v = round(float(value), 2)
    d = {"value": v, "unit": unit, "label": label}
    if note:
        d["note"] = note
    return d


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _smoke_dose(cigarettes: float) -> float:
    """Illustrative dose 0..1: sqrt(cigarettes/100). Strictly increasing, steep for the first few."""
    return math.sqrt(min(max(float(cigarettes), 0.0), 100.0) / 100.0)


def _smoke_from(smoking) -> tuple[int, float, int | None]:
    """-> (model code 0/1/2, dose factor 0..1 where 1 = no smoking, cigarettes/day or None)."""
    if isinstance(smoking, bool):
        smoking = "current" if smoking else "never"
    if not isinstance(smoking, str) and smoking is not None:
        try:
            c = float(smoking)
        except (TypeError, ValueError):
            raise ValueError("smoking must be 'never', 'former', 'current' or cigarettes per day (0-100)")
        if not (math.isfinite(c) and c.is_integer() and 0 <= c <= 100):
            raise ValueError("smoking (cigarettes per day) must be a whole number from 0 to 100")
        c = int(c)
        if c == 0:
            return 0, 1.0, 0
        # illustrative dose rule: factor 1.0 = no smoking; 1/day -> 0.78, 10/day -> 0.61,
        # 20/day -> 0.51, 40/day -> 0.38, 100/day -> 0.10
        return 2, 0.85 - 0.75 * _smoke_dose(c), c
    code = {"never": 0, "former": 1, "current": 2}.get(str(smoking).strip().lower())
    if code is None:
        raise ValueError("smoking must be 'never', 'former', 'current' or cigarettes per day (0-100)")
    return code, {0: 1.0, 1: 0.7, 2: 0.2}[code], None


def _normalise(age, sex, sleep, exercise, smoking, diet) -> dict[str, Any]:
    """Validation for predict_health_detailed (exercise = minutes per week)."""
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
    code, factor, cigs = _smoke_from(smoking)
    return {"age": age, "sex_male": male, "sleep_hours": sleep, "exercise_min_week": exercise,
            "smoking": code, "diet_score": diet, "smoke_factor": factor, "cigarettes_per_day": cigs}


def _whole(name: str, v, lo: int, hi: int) -> int:
    msg = f"{name} must be a whole number from {lo} to {hi}"
    if isinstance(v, (bool, str)) or v is None:
        raise ValueError(msg)
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(msg)
    if not math.isfinite(f) or not f.is_integer() or not lo <= f <= hi:
        raise ValueError(msg)
    return int(f)


def _normalise_contract(age, sex, sleep, exercise, smoking, diet) -> dict[str, Any]:
    """Strict contract validation. No clamping, no silent conversion."""
    age = _whole("age", age, 20, 80)
    if not isinstance(sex, str) or sex.strip().lower() not in ("male", "female"):
        raise ValueError("sex must be 'male' or 'female'")
    if isinstance(sleep, (bool, str)) or sleep is None:
        raise ValueError("sleep must be a number of hours from 0 to 24")
    try:
        sleep = float(sleep)
    except (TypeError, ValueError):
        raise ValueError("sleep must be a number of hours from 0 to 24")
    if not math.isfinite(sleep) or not 0 <= sleep <= 24:
        raise ValueError("sleep must be a number of hours from 0 to 24")
    days = _whole("exercise", exercise, 0, 7)
    cigs = _whole("smoking", smoking, 0, 100)
    diet = _whole("diet", diet, 1, 5)
    return _normalise(age, sex, sleep, days * MINUTES_PER_EXERCISE_DAY, cigs, diet)


@lru_cache(maxsize=1)
def _load_bundle():
    """Load the trained model; fall back to the formula baseline (with a warning) if unusable."""
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib
        bundle = joblib.load(MODEL_PATH)
        if not set(TARGETS) <= set(bundle["models"]) or list(bundle["features"]) != FEATURES:
            raise ValueError("model does not have the expected targets/features")
        for m in bundle["models"].values():          # single-row predictions: threads only add overhead
            if hasattr(m, "n_jobs"):
                m.n_jobs = 1
        return bundle
    except Exception as exc:                          # corrupt file, sklearn version mismatch, ...
        warnings.warn(f"Could not use {MODEL_PATH.name} ({exc!r}); using the formula baseline.",
                      RuntimeWarning)
        return None


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
    f_smoke = x["smoke_factor"]
    f_diet = (x["diet_score"] - 1) / 4
    return f_sleep, f_ex, f_smoke, f_diet


def _illustrative_score(organ: str, x: dict) -> float:
    weights, age_sens = ILLUSTRATIVE_ORGANS[organ]
    mix = sum(w * f for w, f in zip(weights, _lifestyle_factors(x)))
    age_prog = min(max((x["age"] - 20) / 60, 0.0), 1.33)
    return 100 * (1 - age_sens * age_prog) * (0.55 + 0.45 * mix)


def _estimate(x: dict, bundle) -> dict[str, float]:
    """Biomarkers (+ eGFR) from the trained model, or from the formula baseline if bundle is None."""
    bio = _biomarkers_ml(x, bundle) if bundle else _biomarkers_formula(x)
    bio["egfr"] = _egfr_ckd_epi_2021(bio["creatinine"], x["age"], bool(x["sex_male"]))
    return bio


# ------------------------------------------------- shared calculation
def _compute(x: dict, use_model: bool = True):
    """-> (organs dict with units/labels, overall score, mode, bundle). x is already validated."""
    bundle = _load_bundle() if use_model else None
    bio_label, mode = (MODEL, "ml_model") if bundle else (ILLUSTRATIVE, "formula_baseline")
    bio = _estimate(x, bundle)
    f_sleep, _, f_smoke, _ = _lifestyle_factors(x)
    age, male = x["age"], bool(x["sex_male"])
    older = max(0.0, age - 30)

    def mean_score(*names, b=None):
        b = bio if b is None else b
        return sum(_score(n, b[n]) for n in names) / len(names)

    raw = {"heart": mean_score("sbp", "dbp", "pulse"), "liver": mean_score("alt", "ast", "bilirubin"),
           "kidneys": mean_score("egfr"), "pancreas": mean_score("glucose", "hba1c")}
    # Illustrative smoking-dose adjustment of the HEART SCORE (the model only sees never/current).
    heart_penalty = 0.0
    cigs = x["cigarettes_per_day"]
    if cigs:                                                      # 1+ cigarettes per day
        never = {**x, "smoking": 0, "smoke_factor": 1.0, "cigarettes_per_day": 0}
        raw["heart"] = min(raw["heart"], mean_score("sbp", "dbp", "pulse", b=_estimate(never, bundle)))
        heart_penalty = HEART_SMOKING_MAX_PENALTY * _smoke_dose(cigs)
        raw["heart"] -= heart_penalty
    for organ in ILLUSTRATIVE_ORGANS:
        raw[organ] = _illustrative_score(organ, x)
    score = {o: round(_clamp(raw[o], 0, 100), 1) for o in ORGAN_IDS}
    d = {o: (100 - score[o]) / 100 for o in ORGAN_IDS}          # 0 = healthy ... 1 = very unhealthy

    ill = ILLUSTRATIVE
    V: dict[str, dict] = {o: {} for o in ORGAN_IDS}             # contract vitals
    X: dict[str, dict] = {o: {} for o in ORGAN_IDS}             # extra (non-contract) vitals

    V["heart"] = {
        "heart_rate": _vital(round(bio["pulse"]), "bpm", bio_label),
        "blood_pressure": _vital(f"{round(bio['sbp'])}/{round(bio['dbp'])}", "mmHg", bio_label,
                                 "systolic/diastolic"),
        "ejection_fraction": _vital(round(64 - 25 * d["heart"]), "%", ill, "demo value from heart score")}
    X["heart"] = {"systolic_bp": _vital(bio["sbp"], "mmHg", bio_label),
                  "diastolic_bp": _vital(bio["dbp"], "mmHg", bio_label)}
    V["lungs"] = {
        "oxygen_saturation": _vital(_clamp(98.5 - 2.5 * (1 - f_smoke) - 0.02 * max(0, age - 30), 90, 99),
                                    "%", ill, "demo value; no oxygen data in the training set"),
        "breathing_rate": _vital(14 + 3 * (1 - f_smoke), "breaths/min", ill, "demo value"),
        "lung_capacity": _vital(max(2.0, 5.8 - (0 if male else 0.9) - 0.02 * older - 2.0 * d["lungs"]),
                                "litres", ill, "demo value; lower for female and with age")}
    V["brain"] = {
        "neuro_inflammation_index": _vital(_clamp(0.5 + 4.5 * d["brain"], 0, 5), "index 0-5", ill,
                                           "demo value; lower is healthier"),
        "reaction_score": _vital(round(_clamp(95 - 40 * d["brain"] - 0.2 * older, 0, 100)), "score 0-100",
                                 ill, "demo value; higher is healthier")}
    X["brain"] = {"sleep_hours": _vital(x["sleep_hours"], "h/night", MEASURED, "self-reported input")}
    V["liver"] = {"alt": _vital(bio["alt"], "U/L", bio_label), "ast": _vital(bio["ast"], "U/L", bio_label),
                  "bilirubin": _vital(bio["bilirubin"], "mg/dL", bio_label)}
    for o in ("stomach", "intestines", "pancreas"):
        V[o] = {"gut_inflammation": _vital(_clamp(1 + 6 * d[o], 0, 10), "index 0-10", ill,
                                           "demo value; lower is healthier")}
    X["pancreas"] = {"fasting_glucose": _vital(bio["glucose"], "mg/dL", bio_label),
                     "hba1c": _vital(bio["hba1c"], "%", bio_label)}
    hydration = _vital(_clamp(95 - 30 * d["kidneys"], 0, 100), "%", ill, "demo value")
    for o in ("kidneys", "bladder"):                           # systemic markers: same values for both
        V[o] = {"egfr": _vital(bio["egfr"], "mL/min/1.73m2", bio_label,
                               "calculated from creatinine with CKD-EPI 2021"),
                "creatinine": _vital(bio["creatinine"], "mg/dL", bio_label),
                "hydration": dict(hydration)}
    V["thyroid"] = {
        "glucose": _vital(bio["glucose"], "mg/dL", bio_label, "fasting glucose (NHANES-based)"),
        "tsh": _vital(1.8 + 0.01 * (age - 40), "mIU/L", ill, "demo value; TSH is not in the training data"),
        "cortisol": _vital(12 + 8 * d["thyroid"], "ug/dL", ill, "demo value")}
    V["spleen"] = {
        "white_cell_count": _vital(6.0 + 4.0 * d["spleen"], "x10^9/L", ill, "demo value"),
        "cytokine_level": _vital(2 + 20 * d["spleen"], "pg/mL", ill, "demo value; lower is healthier"),
        "pathogen_load": _vital(0.0, "relative load (1.0 = untreated reference-adult peak)", ill,
                                "0.0 = no or negligible pathogen; healthy-body day-zero baseline "
                                "(Part B models no infection; infected values come from Part D)")}
    V["reproductive"] = {"hormone_indicators": _vital(round(score["reproductive"]), "index 0-100", ill,
                                                      "demo index derived from the reproductive score")}

    organs: dict[str, dict] = {}
    for o in ORGAN_IDS:
        is_model_organ = o in ("heart", "liver", "kidneys", "pancreas")
        organs[o] = {"score": score[o], "score_label": bio_label if is_model_organ else ILLUSTRATIVE,
                     "vitals": V[o]}
        if X[o]:
            organs[o]["extra_vitals"] = X[o]
        if not is_model_organ:
            organs[o]["note"] = "Score from illustrative lifestyle/age rules; demo vitals, not medical data."
    if heart_penalty > 0:
        organs["heart"]["score_label"] = ILLUSTRATIVE
        organs["heart"]["adjustments"] = {"smoking_dose_penalty": -round(heart_penalty, 1)}
        organs["heart"]["note"] = (
            f"Model-based heart score minus an illustrative smoking-dose adjustment of "
            f"{heart_penalty:.1f} points ({cigs}/day). Heart vitals are unadjusted model output.")
    total_w = sum(OVERALL_WEIGHTS.values())
    overall = sum(score[o] * OVERALL_WEIGHTS[o] for o in ORGAN_IDS) / total_w
    return organs, overall, mode, bundle


# ------------------------------------------------- public functions
def predict_health_detailed(age, sex, sleep, exercise, smoking, diet, use_model: bool = True) -> dict:
    """Rich output (units, provenance labels, notes). exercise = minutes/week; see module docstring."""
    x = _normalise(age, sex, sleep, exercise, smoking, diet)
    organs, overall, mode, bundle = _compute(x, use_model)
    inputs = {
        "age": _vital(x["age"], "years", MEASURED), "sex": {"value": "male" if x["sex_male"] else "female", "label": MEASURED},
        "sleep": _vital(x["sleep_hours"], "h/night", MEASURED),
        "exercise": _vital(x["exercise_min_week"], "min/week", MEASURED),
        "smoking": {"value": ["never", "former", "current"][x["smoking"]], "label": MEASURED},
        "diet": _vital(x["diet_score"], "1-5", MEASURED)}
    if x["cigarettes_per_day"] is not None:
        inputs["cigarettes_per_day"] = _vital(x["cigarettes_per_day"], "cigarettes/day", MEASURED)
    return {
        "inputs": inputs,
        "overall_health": {"score": round(overall, 1), "label": ILLUSTRATIVE,
                           "note": "weighted mean of the 12 organ scores; 8 of them are illustrative"},
        "organs": organs,
        "model_info": {"mode": mode, "trained_on": bundle["trained_on"] if bundle else None},
        "disclaimer": DISCLAIMER,
    }


def predict_health(age, sex, sleep, exercise, smoking, diet) -> dict:
    """API contract v1.1 output: {organ_id: {"score": int, "vitals": {name: number | "sys/dia"}}}."""
    x = _normalise_contract(age, sex, sleep, exercise, smoking, diet)
    organs, _, _, _ = _compute(x, True)
    out = {}
    for o in ORGAN_IDS:
        vitals = {name: organs[o]["vitals"][name]["value"] for name in CONTRACT_VITALS[o]}
        out[o] = {"score": int(math.floor(organs[o]["score"] + 0.5)), "vitals": vitals}
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(predict_health(40, "male", 7, 3, 0, 3), indent=2))
