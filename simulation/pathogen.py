"""Pathogen lab for Genesis Twin (Part D, Saket).

What this file does
-------------------
1. Simulates how a pathogen grows inside a body over 30 days (a small ODE model).
2. Lets a treatment slider (0 to 1) weaken the pathogen. Treatment can start on any day.
3. Turns the pathogen load into damage for each of the 12 organs,
   using a "tropism table" (which organs does this pathogen like to attack?).
4. NEW: takes a body profile (sex, age, height, weight, optional baseline vitals from the face scan)
   so a child, an older adult, a small or a large body each get their own result.
5. Returns everything in the shape agreed in backend/api-contract.md (Rakhi),
   plus extra keys that make the screen smooth.

Functions the backend (Rakhi) calls (every function takes an optional profile=None):
    list_pathogens()                                           GET  /pathogens
    simulate_pathogen(id, day, treatment, treatment_start=0, profile=None)
    simulate_timeline(id, treatment, treatment_start=0, profile=None)   all 31 days in ONE call
    load_band(id, treatment, treatment_start=0, ..., profile=None)      uncertainty band
    simulate_custom(parameters, target_organs, day, treatment, ..., profile=None)   uploaded pathogen
    simulate_custom_timeline(parameters, target_organs, treatment, ..., profile=None)
    model_info()                                               version, settings and preset parameters
    describe_profile(profile)                                  summary card for the profile form
(fit_pathogen for CSV uploads lives in fitting.py)

Profile = {"sex": "male" or "female", "age": years, "height_cm": number, "weight_kg": number,
           "baseline_vitals": {"heart_rate": bpm, "breathing_rate": per minute}}   (last one optional)
Missing fields default to a reference adult (male, 30 years, 175 cm, 70 kg).
No profile at all gives exactly the same result as before.

Every effect of the profile is a SAMPLE ASSUMPTION, listed in the output ("profile_effects") and
in one place below (_adjustments), so it is visible and easy to change or cite later.
All parameter values are sample values for a demo, not real outbreak or clinical data.
Research and education only, not medical advice.
"""
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp

MODEL_VERSION = "pathogen-lab-1.4.0"   # saved with every experiment so results can be reproduced
DAYS = 30                      # we simulate day 0 to day 30
STEPS_PER_DAY = 4              # fine grid: every quarter of a day
FINE_T = np.linspace(0, DAYS, DAYS * STEPS_PER_DAY + 1)   # 121 points

# The 12 organ ids shared by the whole team.
ORGAN_IDS = [
    "brain", "heart", "lungs", "liver", "stomach", "intestines",
    "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive",
]

# How fast damage builds up and heals (per day). Damage lags behind the load:
# an organ keeps some damage for a while after the pathogen is gone.
K_DAMAGE = 0.35
K_HEAL = 0.12

# Dose-response of the treatment slider: more drug helps, with diminishing returns.
# effect(1.0) = 1 (full strength); effect(0.5) is about 0.7.
DOSE_EC50 = 0.4
DOSE_HILL = 2.0

# --------------------------------------------------------------------------
# Presets. "tropism" says how strongly each organ is hit (0 = never, 1 = fully).
# Ids match backend/api-contract.md.
# --------------------------------------------------------------------------
PRESETS = {
    "respiratory_virus": {
        "name": "Sample respiratory virus",
        "kind": "virus",
        "params": {"beta": 1.0, "prod": 15.0, "delta": 0.8, "clear": 1.0,
                   "kill": 1.0, "s": 0.5, "dF": 0.2, "V0": 3e-3, "max_effect": 0.9},
        "tropism": {"brain": 0.15, "heart": 0.35, "lungs": 0.90, "liver": 0.15,
                    "stomach": 0.10, "intestines": 0.10, "kidneys": 0.20,
                    "bladder": 0.05, "pancreas": 0.05, "spleen": 0.30,
                    "thyroid": 0.05, "reproductive": 0.05},
    },
    "gut_virus": {
        "name": "Sample gut virus",
        "kind": "virus",
        "params": {"beta": 1.2, "prod": 15.0, "delta": 1.0, "clear": 1.2,
                   "kill": 1.5, "s": 0.6, "dF": 0.3, "V0": 3e-3, "max_effect": 0.9},
        "tropism": {"brain": 0.10, "heart": 0.15, "lungs": 0.10, "liver": 0.40,
                    "stomach": 0.70, "intestines": 0.90, "kidneys": 0.30,
                    "bladder": 0.10, "pancreas": 0.30, "spleen": 0.25,
                    "thyroid": 0.05, "reproductive": 0.05},
    },
    "bloodstream_bacterium": {
        "name": "Sample bloodstream bacterium",
        "kind": "bacteria",
        "params": {"r": 1.0, "K": 1.0, "kill": 3.0, "s": 1.5, "dF": 0.02,
                   "B0": 1e-3, "max_effect": 1.2},
        "tropism": {"brain": 0.50, "heart": 0.60, "lungs": 0.40, "liver": 0.50,
                    "stomach": 0.20, "intestines": 0.20, "kidneys": 0.60,
                    "bladder": 0.20, "pancreas": 0.30, "spleen": 0.60,
                    "thyroid": 0.10, "reproductive": 0.10},
    },
}

# Parameters that vary in the uncertainty band.
BAND_PARAMS = {"virus": ("beta", "prod", "delta", "clear", "kill", "s", "dF"),
               "bacteria": ("r", "kill", "s", "dF")}


def _effect(treatment):
    """Dose-response: treatment slider (0 to 1) to effect strength (0 to 1)."""
    if treatment <= 0:
        return 0.0
    h, ec = DOSE_HILL, DOSE_EC50
    return float(treatment ** h * (ec ** h + 1.0) / (ec ** h + treatment ** h))


# --------------------------------------------------------------------------
# Body profile: check it, then turn it into adjustments
# --------------------------------------------------------------------------
REFERENCE_PROFILE = {"sex": "male", "age": 30.0, "height_cm": 175.0, "weight_kg": 70.0}
PROFILE_LIMITS = {"age": (0, 110), "height_cm": (40, 230), "weight_kg": (2, 250),
                  "heart_rate": (30, 220), "breathing_rate": (4, 60)}


def _ramp(x, start, end):
    """0 below start, 1 above end, straight line in between."""
    return float(min(1.0, max(0.0, (x - start) / float(end - start))))


def _number(profile, key, limits_key=None):
    lo, hi = PROFILE_LIMITS[limits_key or key]
    try:
        value = float(profile[key])
    except (TypeError, ValueError, KeyError):
        raise ValueError("%s must be a number" % key)
    if not (lo <= value <= hi):
        raise ValueError("%s must be between %g and %g" % (key, lo, hi))
    return value


def clean_profile(profile):
    """Check a profile and fill missing fields with the reference adult. None stays None."""
    if profile is None:
        return None
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object with sex, age, height_cm and weight_kg")
    merged = dict(REFERENCE_PROFILE)
    merged.update({k: v for k, v in profile.items() if k in REFERENCE_PROFILE and v is not None})
    sex = str(merged["sex"]).lower()
    if sex not in ("male", "female"):
        raise ValueError("sex must be male or female")
    out = {"sex": sex, "age": _number(merged, "age"),
           "height_cm": _number(merged, "height_cm"), "weight_kg": _number(merged, "weight_kg")}
    bmi = out["weight_kg"] / (out["height_cm"] / 100.0) ** 2
    if not (8 <= bmi <= 70):
        raise ValueError("height and weight do not look realistic together (BMI %.0f)" % bmi)
    baseline = {}
    given = profile.get("baseline_vitals") or {}
    for key in ("heart_rate", "breathing_rate"):
        if given.get(key) is not None:
            baseline[key] = _number(given, key)
    out["baseline_vitals"] = baseline
    return out


def _age_group(age):
    return "child" if age < 13 else ("teen" if age < 18 else ("adult" if age < 65 else "older"))


def _adjustments(p):
    """Everything the profile changes. ALL numbers here are sample assumptions, not clinical data.
    p is a cleaned profile or None."""
    adj = {"immune": 1.0, "damage_scale": {o: 1.0 for o in ORGAN_IDS}, "vitals_scale": {},
           "bp_scale": (1.0, 1.0), "baseline": {}, "effects": []}
    if p is None:
        return adj
    age, sex, height = p["age"], p["sex"], p["height_cm"]
    bmi = p["weight_kg"] / (height / 100.0) ** 2

    # Older age: weaker immune response and less organ reserve, building up from age 40 to 65.
    older = _ramp(age, 40, 65)
    adj["immune"] = 1.0 - 0.2 * older
    if older > 0:
        for o in ORGAN_IDS:
            adj["damage_scale"][o] *= 1.0 + 0.1 * older
        adj["effects"].append("Age %g: immune response %.0f%% of an adult's and less organ reserve." % (age, adj["immune"] * 100))

    # Child (under 18): different resting values. Fully "child" up to 12, adult at 18.
    child = 1.0 - _ramp(age, 12, 18)
    adj["vitals_scale"] = {
        "heart_rate": (1.0 + 0.3 * child) * (1.04 if sex == "female" else 1.0) * (1.03 if age >= 65 else 1.0),
        "breathing_rate": (1.0 + 0.5 * child) * (1.05 if age >= 65 else 1.0),
        "lung_capacity": (height / 175.0) ** 3 * (0.8 if sex == "female" else 1.0) * (0.85 if age >= 65 else 1.0),
        "egfr": 1.0 if age <= 40 else max(0.6, 1.0 - 0.008 * (age - 40)),
        "white_cell_count": 1.0 + 0.3 * child,
    }
    adj["bp_scale"] = ((1.0 - 0.2 * child) * (1.1 if age >= 65 else 1.0),
                       (1.0 - 0.15 * child) * (1.03 if age >= 65 else 1.0))
    if child > 0:
        adj["effects"].append("Age %g: higher resting heart and breathing rate, lower blood pressure, "
                              "lung capacity scaled to height." % age)
    if sex == "female":
        adj["effects"].append("Female: resting heart rate about 4% higher and lung capacity about 20% lower than a male of the same height.")
    adj["effects"].append("Lung capacity scaled to height (%g cm)." % height)

    # Body mass index (adults only: children need growth charts).
    if age >= 18:
        if bmi >= 25:
            factor = 1.0 + 0.012 * (min(bmi, 40.0) - 25.0)
            adj["damage_scale"]["lungs"] *= factor
            adj["damage_scale"]["heart"] *= factor
            adj["effects"].append("BMI %.1f: lung and heart damage scaled by %.2f." % (bmi, factor))
        elif bmi < 18.5:
            for o in ORGAN_IDS:
                adj["damage_scale"][o] *= 1.1
            adj["effects"].append("BMI %.1f (underweight): all organs 10%% more vulnerable." % bmi)
    else:
        adj["effects"].append("BMI effects are not applied under 18 (children need growth charts).")

    if p["baseline_vitals"]:
        adj["baseline"] = dict(p["baseline_vitals"])
        adj["effects"].append("Resting %s set from the face scan (webcam estimates, not measurements)."
                              % " and ".join(k.replace("_", " ") for k in p["baseline_vitals"]))
    return adj


def describe_profile(profile):
    """Summary for the profile form: cleaned profile, BMI, age group and the assumptions that apply."""
    p = clean_profile(profile)
    if p is None:
        p = clean_profile({})
    bmi = p["weight_kg"] / (p["height_cm"] / 100.0) ** 2
    return {"profile": p, "bmi": round(bmi, 1), "age_group": _age_group(p["age"]),
            "effects": _adjustments(p)["effects"]}


# --------------------------------------------------------------------------
# Step 1: the ODE models (how the pathogen changes over time)
# --------------------------------------------------------------------------
def _virus_rhs(t, y, p, eff):
    """Virus model. y = [T, I, V, F]
    T = healthy target cells, I = infected cells, V = virus, F = immune response.
    The antiviral (strength eff, 0 to 1) lowers how much virus infected cells produce."""
    T, I, V, F = y
    infection = p["beta"] * T * V
    production = (1.0 - eff * p["max_effect"]) * p["prod"] * I
    dT = -infection
    dI = infection - p["delta"] * I - p["kill"] * F * I
    dV = production - p["clear"] * V
    dF = p["s"] * I - p["dF"] * F
    return [dT, dI, dV, dF]


def _bacteria_rhs(t, y, p, eff):
    """Bacteria model. y = [B, F]
    B = bacteria (1 = carrying capacity), F = immune response.
    The antibiotic (strength eff, 0 to 1) adds an extra death rate."""
    B, F = y
    dB = p["r"] * B * (1.0 - B / p["K"]) - p["kill"] * F * B - eff * p["max_effect"] * B
    dF = p["s"] * B - p["dF"] * F
    return [dB, dF]


def _params_for(pathogen_id, immune=1.0):
    """Preset parameters, with the immune response scaled for the body profile."""
    params = dict(PRESETS[pathogen_id]["params"])
    if immune != 1.0:
        params["kill"] *= immune
        params["s"] *= immune
    return params


def _integrate(pathogen_id, treatment, start, t_eval, params):
    """Solve the ODE. Treatment is off until day `start`, then on. Returns the pathogen amount."""
    kind = PRESETS[pathogen_id]["kind"]
    rhs = _virus_rhs if kind == "virus" else _bacteria_rhs
    state = [1.0, 0.0, params["V0"], 0.0] if kind == "virus" else [params["B0"], 0.0]
    index = 2 if kind == "virus" else 0
    eff = _effect(treatment)
    t_eval = np.asarray(t_eval, dtype=float)

    if eff > 0 and 0 < start < DAYS:
        segments = [(0.0, float(start), 0.0), (float(start), float(DAYS), eff)]
    else:
        segments = [(0.0, float(DAYS), eff if (eff > 0 and start <= 0) else 0.0)]

    out = np.zeros(len(t_eval))
    for n, (a, b, e) in enumerate(segments):
        mask = (t_eval >= a) & (t_eval <= b) if n == 0 else (t_eval > a) & (t_eval <= b)
        times = np.unique(np.append(t_eval[mask], b))
        sol = solve_ivp(rhs, (a, b), state, t_eval=times, args=(params, e),
                        method="LSODA", rtol=1e-8, atol=1e-13)
        out[mask] = np.interp(t_eval[mask], times, sol.y[index])
        state = sol.y[:, -1]
    return np.clip(out, 0.0, None)


@lru_cache(maxsize=None)
def _untreated_peak(pathogen_id):
    """Highest load of the reference adult without treatment. We divide by it, so 1 = that peak."""
    fine = np.linspace(0, DAYS, 601)
    return float(_integrate(pathogen_id, 0.0, 0, fine, PRESETS[pathogen_id]["params"]).max())


@lru_cache(maxsize=512)
def _load_fine(pathogen_id, treatment, start, immune):
    """Load relative to the reference adult's untreated peak, on the quarter-day grid (cached).
    Can go above 1 for a body with a weaker immune response."""
    amount = _integrate(pathogen_id, treatment, start, FINE_T, _params_for(pathogen_id, immune))
    return np.clip(amount / _untreated_peak(pathogen_id), 0.0, 3.0)


# --------------------------------------------------------------------------
# Step 2: from pathogen load to organ damage (integrated on the fine grid)
# --------------------------------------------------------------------------
def _damage_fine(tropism_value, load_fine):
    """Damage grows when the load is high and heals slowly. Returns 0 to 1 per grid point."""
    dt = 1.0 / STEPS_PER_DAY
    damage = np.zeros(len(load_fine))
    for i in range(len(load_fine) - 1):
        gain = K_DAMAGE * tropism_value * 0.5 * (load_fine[i] + load_fine[i + 1])
        x = damage[i] + dt * (gain - K_HEAL * damage[i])
        damage[i + 1] = min(1.0, max(0.0, x))
    return damage


# --------------------------------------------------------------------------
# Step 3: from damage to vitals. Names follow backend/api-contract.md.
# x = damage between 0 (healthy) and 1 (severe), load = pathogen load 0 to 1.
# These formulas are PLACEHOLDERS: we agree one shared mapping with Ravneet (Part B).
# --------------------------------------------------------------------------
VITALS = {
    "brain": lambda x, load: {"neuro_inflammation_index": 0.1 + 0.8 * x, "reaction_score": 95 - 45 * x},
    "heart": lambda x, load: {"heart_rate": 70 + 35 * x,
                              "blood_pressure": "%d/%d" % (round(120 + 25 * x), round(80 + 12 * x)),
                              "ejection_fraction": 60 - 18 * x},
    "lungs": lambda x, load: {"oxygen_saturation": 98 - 16 * x, "breathing_rate": 14 + 16 * x,
                              "lung_capacity": 4.8 - 1.8 * x},
    "liver": lambda x, load: {"alt": 25 + 140 * x, "ast": 22 + 120 * x, "bilirubin": 0.7 + 2.2 * x},
    "stomach": lambda x, load: {"gut_inflammation": 10 * x},
    "intestines": lambda x, load: {"gut_inflammation": 10 * x},
    "pancreas": lambda x, load: {"gut_inflammation": 10 * x},
    "kidneys": lambda x, load: {"egfr": 100 - 45 * x, "creatinine": 0.9 + 1.1 * x, "hydration": 100 - 20 * x},
    "bladder": lambda x, load: {"hydration": 100 - 20 * x},
    "thyroid": lambda x, load: {"glucose": 90 + 30 * x, "tsh": 2.0 + 1.5 * x, "cortisol": 12 + 8 * x},
    "spleen": lambda x, load: {"white_cell_count": 7 + 6 * x, "cytokine_level": 5 + 95 * x,
                               "pathogen_load": load},
    "reproductive": lambda x, load: {"hormone_indicators": 100 - 20 * x},
}


def _scaled(raw, adj):
    """Apply the profile's resting-value scaling to a vitals dictionary."""
    out = {}
    for name, value in raw.items():
        if name == "blood_pressure":
            sys_, dia = (float(v) for v in value.split("/"))
            out[name] = "%d/%d" % (round(sys_ * adj["bp_scale"][0]), round(dia * adj["bp_scale"][1]))
        else:
            out[name] = value * adj["vitals_scale"].get(name, 1.0)
    return out


def _vitals(organ, x, load, adj):
    vitals = _scaled(VITALS[organ](x, load), adj)
    if adj["baseline"]:
        healthy = _scaled(VITALS[organ](0.0, 0.0), adj)
        for key, measured in adj["baseline"].items():
            if key in vitals:
                vitals[key] = measured + (vitals[key] - healthy[key])  # measured rest value plus the change
    out = {}
    for name, value in vitals.items():
        if isinstance(value, str):
            out[name] = value
        else:
            value = float(value)
            out[name] = round(value, 2) if abs(value) < 20 else round(value, 1)
    return out


def _status(score):
    """Label for colours: healthy (80 and above), stressed (50 to 79), critical (below 50)."""
    return "healthy" if score >= 80 else ("stressed" if score >= 50 else "critical")


# --------------------------------------------------------------------------
# Building the output
# --------------------------------------------------------------------------
def _make_core(pathogen_id, name, load_true, tropism, treatment, start, profile):
    adj = _adjustments(profile)
    load_true = np.clip(np.asarray(load_true, dtype=float), 0.0, 3.0)
    damage_load = np.clip(load_true, 0.0, 2.0)
    damage = {o: _damage_fine(min(1.0, tropism.get(o, 0.0) * adj["damage_scale"][o]), damage_load)
              for o in ORGAN_IDS}
    return {"pathogen_id": pathogen_id, "name": name, "load": np.clip(load_true, 0.0, 1.0),
            "damage": damage, "treatment": treatment, "start": start, "profile": profile, "adj": adj}


def _organs_at(core, i):
    organs = {}
    for organ in ORGAN_IDS:
        x = float(core["damage"][organ][i])
        score = int(round(100 * (1 - x)))
        organs[organ] = {"score": score, "status": _status(score),
                         "vitals": _vitals(organ, x, float(core["load"][i]), core["adj"])}
    return organs


def _daily_curve(core):
    return [{"day": d, "load": round(float(core["load"][d * STEPS_PER_DAY]), 4)} for d in range(DAYS + 1)]


def _smooth_curve(core):
    return [{"day": round(float(t), 2), "load": round(float(v), 4)} for t, v in zip(FINE_T, core["load"])]


def _result(core, day):
    i = day * STEPS_PER_DAY
    return {
        "pathogen_id": core["pathogen_id"],
        "name": core["name"],
        "model_version": MODEL_VERSION,
        "day": day,
        "treatment": core["treatment"],
        "treatment_start": core["start"],
        "profile": core["profile"],
        "profile_effects": core["adj"]["effects"],
        "load": round(float(core["load"][i]), 4),
        "curve": _daily_curve(core),
        "curve_smooth": _smooth_curve(core),
        "organs": _organs_at(core, i),
    }


def _timeline(core):
    return {
        "pathogen_id": core["pathogen_id"],
        "name": core["name"],
        "model_version": MODEL_VERSION,
        "treatment": core["treatment"],
        "treatment_start": core["start"],
        "profile": core["profile"],
        "profile_effects": core["adj"]["effects"],
        "times": [round(float(t), 2) for t in FINE_T],
        "load": [round(float(v), 4) for v in core["load"]],
        "scores": {o: [int(round(100 * (1 - x))) for x in core["damage"][o]] for o in ORGAN_IDS},
        "days": [{"day": d,
                  "load": round(float(core["load"][d * STEPS_PER_DAY]), 4),
                  "organs": _organs_at(core, d * STEPS_PER_DAY)} for d in range(DAYS + 1)],
    }


def _clean(treatment, start, day=0):
    return (float(max(0.0, min(1.0, treatment))),
            int(max(0, min(DAYS, round(start)))),
            int(max(0, min(DAYS, day))))


def _preset_core(pathogen_id, treatment, start, profile):
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    profile = clean_profile(profile)
    immune = round(_adjustments(profile)["immune"], 3)
    preset = PRESETS[pathogen_id]
    return _make_core(pathogen_id, preset["name"], _load_fine(pathogen_id, round(treatment, 3), start, immune),
                      preset["tropism"], treatment, start, profile)


# --------------------------------------------------------------------------
# Functions the backend calls: preset pathogens
# --------------------------------------------------------------------------
def list_pathogens():
    """For GET /pathogens. Returns [{"id", "name", "kind", "preset": True}, ...]."""
    return [{"id": pid, "name": p["name"], "kind": p["kind"], "preset": True}
            for pid, p in PRESETS.items()]


def simulate_pathogen(pathogen_id, day, treatment, treatment_start=0, profile=None):
    """Simulate one preset pathogen for one day (the day on the slider).

    pathogen_id:     "respiratory_virus", "gut_virus" or "bloodstream_bacterium"
    day:             0 to 30
    treatment:       0 to 1 (drug or antibiotic strength)
    treatment_start: day the treatment begins (default 0)
    profile:         body profile (see top of this file), or None for the reference adult

    Returns load (0 to 1, where 1 is the reference adult's untreated peak), curve (daily), organs
    (all 12 organ ids with score, status and vitals) and the extra keys curve_smooth,
    profile and profile_effects. Bad input raises ValueError with a plain message.
    """
    treatment, start, day = _clean(treatment, treatment_start, day)
    return _result(_preset_core(pathogen_id, treatment, start, profile), day)


def simulate_timeline(pathogen_id, treatment, treatment_start=0, profile=None):
    """All 31 days in one call, so the day slider and the 3D animation never wait for the server.

    Returns:
      times   every quarter day, 0 to 30 (121 numbers)
      load    load at each time
      scores  {organ_id: [score at each time]}  (smooth, use for colour fading)
      days    31 entries {"day", "load", "organs": {organ_id: {score, status, vitals}}}  (use for panels)
    """
    treatment, start, _ = _clean(treatment, treatment_start)
    return _timeline(_preset_core(pathogen_id, treatment, start, profile))


@lru_cache(maxsize=64)
def _band_arrays(pathogen_id, treatment, start, runs, spread, seed, immune):
    preset = PRESETS[pathogen_id]
    rng = np.random.default_rng(seed)
    peak = _untreated_peak(pathogen_id)
    curves = []
    for _ in range(runs):
        params = _params_for(pathogen_id, immune)
        for key in BAND_PARAMS[preset["kind"]]:
            params[key] = params[key] * float(np.exp(rng.uniform(-spread, spread)))
        try:
            curves.append(_integrate(pathogen_id, treatment, start, FINE_T, params) / peak)
        except Exception:
            continue
    if not curves:
        nominal = _load_fine(pathogen_id, treatment, start, immune)
        return tuple(nominal), tuple(nominal)
    arr = np.vstack(curves)
    return tuple(np.percentile(arr, 10, axis=0)), tuple(np.percentile(arr, 90, axis=0))


def load_band(pathogen_id, treatment=0.0, treatment_start=0, runs=40, spread=0.15, seed=0, profile=None):
    """Uncertainty band for the load curve.

    Runs the model `runs` times with the main parameters changed by up to +/- spread (15 percent)
    and returns the 10th to 90th percentile. Same inputs always give the same band.
    Returns {"times", "low", "high", "nominal"} (121 points each).
    """
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    treatment, start, _ = _clean(treatment, treatment_start)
    immune = round(_adjustments(clean_profile(profile))["immune"], 3)
    low, high = _band_arrays(pathogen_id, round(treatment, 3), start, int(runs), float(spread), int(seed), immune)
    nominal = _load_fine(pathogen_id, round(treatment, 3), start, immune)
    return {"times": [round(float(t), 2) for t in FINE_T],
            "low": [round(float(v), 4) for v in low],
            "high": [round(float(v), 4) for v in high],
            "nominal": [round(float(v), 4) for v in nominal]}


# --------------------------------------------------------------------------
# Functions the backend calls: uploaded pathogens (fitted with fitting.py)
# --------------------------------------------------------------------------
def _value(p):
    """Accept either 0.8 or {"value": 0.8, "low": ..., "high": ...}."""
    return float(p["value"] if isinstance(p, dict) else p)


def _clean_tropism(tropism):
    """Check an organ-to-tropism dictionary ({organ_id: 0 to 1}). Organs not listed get a small default (0.05)."""
    if tropism is None:
        return None
    if not isinstance(tropism, dict):
        raise ValueError("tropism must be an object like {organ_id: number from 0 to 1}")
    out = {}
    for organ, value in tropism.items():
        if organ not in ORGAN_IDS:
            raise ValueError("Unknown organ id in tropism: %s" % organ)
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError("tropism values must be numbers between 0 and 1")
        if not (0.0 <= value <= 1.0):
            raise ValueError("tropism values must be between 0 and 1 (found %g for %s)" % (value, organ))
        out[organ] = value
    return {o: out.get(o, 0.05) for o in ORGAN_IDS}


def _custom_core(parameters, target_organs, treatment, start, name, pathogen_id, profile, tropism=None):
    try:
        growth = _value(parameters["growth_rate"])
        decay = _value(parameters["decay_rate"])
        peak_day = _value(parameters["peak_day"])
    except (KeyError, TypeError):
        raise ValueError("parameters must contain growth_rate, decay_rate and peak_day")
    profile = clean_profile(profile)
    decay = decay * _adjustments(profile)["immune"]   # a weaker immune response clears the pathogen more slowly
    peak_day = max(0.0, min(float(DAYS), peak_day))
    shape = 2.0 / (np.exp(-growth * (FINE_T - peak_day)) + np.exp(decay * (FINE_T - peak_day)))
    # Treatment ramps up over 2 days after it starts and cuts the load by up to 90 percent.
    ramp = np.clip((FINE_T - start) / 2.0, 0.0, 1.0)
    load = np.clip(shape * (1.0 - 0.9 * _effect(treatment) * ramp), 0.0, 1.0)

    custom = _clean_tropism(tropism)
    if custom is not None:
        values = custom
    else:
        targets = [o for o in (target_organs or []) if o in ORGAN_IDS]
        values = {o: (0.9 if o in targets else 0.1) for o in ORGAN_IDS} if targets else {o: 0.4 for o in ORGAN_IDS}
    return _make_core(pathogen_id, name, load, values, treatment, start, profile)


def simulate_custom(parameters, target_organs, day, treatment, name="Uploaded pathogen",
                    pathogen_id="uploaded", treatment_start=0, profile=None, tropism=None):
    """Simulate a pathogen that was fitted with fit_pathogen (fitting.py).

    parameters:    the "parameters" output of fit_pathogen (growth_rate, decay_rate, peak_day)
    target_organs: organ ids the pathogen attacks, e.g. ["lungs"] (fit_pathogen returns them).
                   If the list has no known organ, the pathogen is treated as systemic.
    tropism:       optional {organ_id: 0 to 1}, for example the "tropism" from tropism.py (receptor expression
                   data). When given, it is used instead of target_organs.
    """
    treatment, start, day = _clean(treatment, treatment_start, day)
    return _result(_custom_core(parameters, target_organs, treatment, start, name, pathogen_id, profile, tropism), day)


def simulate_custom_timeline(parameters, target_organs, treatment, treatment_start=0,
                             name="Uploaded pathogen", pathogen_id="uploaded", profile=None, tropism=None):
    """Same as simulate_timeline, for an uploaded pathogen."""
    treatment, start, _ = _clean(treatment, treatment_start)
    return _timeline(_custom_core(parameters, target_organs, treatment, start, name, pathogen_id, profile, tropism))


def model_info():
    """Version, settings and preset parameters. Save the version with every experiment, and let the weekly
    research pipeline (Punya) read the current parameters from here."""
    return {
        "model_version": MODEL_VERSION,
        "settings": {"days": DAYS, "steps_per_day": STEPS_PER_DAY, "damage_rate": K_DAMAGE, "heal_rate": K_HEAL,
                     "dose_ec50": DOSE_EC50, "dose_hill": DOSE_HILL},
        "presets": {pid: {"name": p["name"], "kind": p["kind"], "params": dict(p["params"]),
                          "tropism": dict(p["tropism"])} for pid, p in PRESETS.items()},
        "note": "All values are sample values for a demo, not real outbreak or clinical data.",
    }
