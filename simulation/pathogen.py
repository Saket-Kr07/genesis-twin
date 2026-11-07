"""Pathogen lab for Genesis Twin (Part D, Saket).

What this file does
-------------------
1. Simulates how a pathogen grows inside a body over 30 days (a small ODE model).
2. Lets a treatment slider (0 to 1) weaken the pathogen. Treatment can start on any day.
3. Turns the pathogen load into damage for each of the 12 organs,
   using a "tropism table" (which organs does this pathogen like to attack?).
4. Returns everything in the shape agreed in backend/api-contract.md (Rakhi),
   plus extra keys that make the screen smooth (see "Extra keys" below).

Functions the backend (Rakhi) calls:
    list_pathogens()                                           GET  /pathogens
    simulate_pathogen(id, day, treatment, treatment_start=0)   POST /pathogens/simulate (preset)
    simulate_timeline(id, treatment, treatment_start=0)        all 31 days in ONE call (for sliders)
    load_band(id, treatment, treatment_start=0)                uncertainty band around the load curve
    simulate_custom(parameters, target_organs, day, treatment) uploaded pathogen (see fitting.py)
    simulate_custom_timeline(parameters, target_organs, treatment)

Extra keys (the contract keys load, curve and organs are unchanged):
    curve_smooth   load every quarter of a day (121 points) for smooth plots
    organs[...]["status"]   "healthy", "stressed" or "critical" for colours and labels
    treatment_start         the day treatment began

All parameter values are SAMPLE values for a demo, not real outbreak data.
Research and education only, not medical advice.
"""
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp

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
K_DAMAGE = 0.45
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
    """Highest load without treatment. We divide by it so 'load' is a 0 to 1 number."""
    fine = np.linspace(0, DAYS, 601)
    return float(_integrate(pathogen_id, 0.0, 0, fine, PRESETS[pathogen_id]["params"]).max())


@lru_cache(maxsize=512)
def _load_fine(pathogen_id, treatment, start):
    """Normalised load on the quarter-day grid (cached, so dragging a slider is instant)."""
    amount = _integrate(pathogen_id, treatment, start, FINE_T, PRESETS[pathogen_id]["params"])
    return np.clip(amount / _untreated_peak(pathogen_id), 0.0, 1.0)


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


def _round_vitals(vitals):
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
def _make_core(pathogen_id, name, load_fine, tropism, treatment, start):
    damage = {o: _damage_fine(tropism.get(o, 0.0), load_fine) for o in ORGAN_IDS}
    return {"pathogen_id": pathogen_id, "name": name, "load": np.asarray(load_fine, dtype=float),
            "damage": damage, "treatment": treatment, "start": start}


def _organs_at(core, i):
    organs = {}
    for organ in ORGAN_IDS:
        x = float(core["damage"][organ][i])
        score = int(round(100 * (1 - x)))
        organs[organ] = {"score": score, "status": _status(score),
                         "vitals": _round_vitals(VITALS[organ](x, float(core["load"][i])))}
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
        "day": day,
        "treatment": core["treatment"],
        "treatment_start": core["start"],
        "load": round(float(core["load"][i]), 4),
        "curve": _daily_curve(core),
        "curve_smooth": _smooth_curve(core),
        "organs": _organs_at(core, i),
    }


def _timeline(core):
    return {
        "pathogen_id": core["pathogen_id"],
        "name": core["name"],
        "treatment": core["treatment"],
        "treatment_start": core["start"],
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


def _preset_core(pathogen_id, treatment, start):
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    preset = PRESETS[pathogen_id]
    return _make_core(pathogen_id, preset["name"], _load_fine(pathogen_id, round(treatment, 3), start),
                      preset["tropism"], treatment, start)


# --------------------------------------------------------------------------
# Functions the backend calls: preset pathogens
# --------------------------------------------------------------------------
def list_pathogens():
    """For GET /pathogens. Returns [{"id", "name", "kind", "preset": True}, ...]."""
    return [{"id": pid, "name": p["name"], "kind": p["kind"], "preset": True}
            for pid, p in PRESETS.items()]


def simulate_pathogen(pathogen_id, day, treatment, treatment_start=0):
    """Simulate one preset pathogen for one day (the day on the slider).

    pathogen_id:     "respiratory_virus", "gut_virus" or "bloodstream_bacterium"
    day:             0 to 30
    treatment:       0 to 1 (drug or antibiotic strength)
    treatment_start: day the treatment begins (default 0)

    Returns load (0 to 1, where 1 is the untreated peak), curve (daily), organs
    (all 12 organ ids with score, status and vitals) and the extra key curve_smooth.
    """
    treatment, start, day = _clean(treatment, treatment_start, day)
    return _result(_preset_core(pathogen_id, treatment, start), day)


def simulate_timeline(pathogen_id, treatment, treatment_start=0):
    """All 31 days in one call, so the day slider and the 3D animation never wait for the server.

    Returns:
      times   every quarter day, 0 to 30 (121 numbers)
      load    load at each time
      scores  {organ_id: [score at each time]}  (smooth, use for colour fading)
      days    31 entries {"day", "load", "organs": {organ_id: {score, status, vitals}}}  (use for panels)
    """
    treatment, start, _ = _clean(treatment, treatment_start)
    return _timeline(_preset_core(pathogen_id, treatment, start))


@lru_cache(maxsize=64)
def _band_arrays(pathogen_id, treatment, start, runs, spread, seed):
    preset = PRESETS[pathogen_id]
    rng = np.random.default_rng(seed)
    peak = _untreated_peak(pathogen_id)
    curves = []
    for _ in range(runs):
        params = dict(preset["params"])
        for key in BAND_PARAMS[preset["kind"]]:
            params[key] = params[key] * float(np.exp(rng.uniform(-spread, spread)))
        try:
            curves.append(_integrate(pathogen_id, treatment, start, FINE_T, params) / peak)
        except Exception:
            continue
    if not curves:
        nominal = _load_fine(pathogen_id, treatment, start)
        return tuple(nominal), tuple(nominal)
    arr = np.vstack(curves)
    return tuple(np.percentile(arr, 10, axis=0)), tuple(np.percentile(arr, 90, axis=0))


def load_band(pathogen_id, treatment=0.0, treatment_start=0, runs=40, spread=0.15, seed=0):
    """Uncertainty band for the load curve.

    Runs the model `runs` times with the main parameters changed by up to +/- spread (15 percent)
    and returns the 10th to 90th percentile. Same inputs always give the same band.
    Returns {"times", "low", "high", "nominal"} (121 points each).
    """
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    treatment, start, _ = _clean(treatment, treatment_start)
    low, high = _band_arrays(pathogen_id, round(treatment, 3), start, int(runs), float(spread), int(seed))
    nominal = _load_fine(pathogen_id, round(treatment, 3), start)
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


def _custom_core(parameters, target_organs, treatment, start, name, pathogen_id):
    try:
        growth = _value(parameters["growth_rate"])
        decay = _value(parameters["decay_rate"])
        peak_day = _value(parameters["peak_day"])
    except (KeyError, TypeError):
        raise ValueError("parameters must contain growth_rate, decay_rate and peak_day")
    peak_day = max(0.0, min(float(DAYS), peak_day))
    shape = 2.0 / (np.exp(-growth * (FINE_T - peak_day)) + np.exp(decay * (FINE_T - peak_day)))
    # Treatment ramps up over 2 days after it starts and cuts the load by up to 90 percent.
    ramp = np.clip((FINE_T - start) / 2.0, 0.0, 1.0)
    load = np.clip(shape * (1.0 - 0.9 * _effect(treatment) * ramp), 0.0, 1.0)

    targets = [o for o in (target_organs or []) if o in ORGAN_IDS]
    tropism = {o: (0.9 if o in targets else 0.1) for o in ORGAN_IDS} if targets else {o: 0.4 for o in ORGAN_IDS}
    return _make_core(pathogen_id, name, load, tropism, treatment, start)


def simulate_custom(parameters, target_organs, day, treatment, name="Uploaded pathogen",
                    pathogen_id="uploaded", treatment_start=0):
    """Simulate a pathogen that was fitted with fit_pathogen (fitting.py).

    parameters:    the "parameters" output of fit_pathogen (growth_rate, decay_rate, peak_day)
    target_organs: organ ids the pathogen attacks, e.g. ["lungs"] (fit_pathogen returns them).
                   If the list has no known organ, the pathogen is treated as systemic.
    """
    treatment, start, day = _clean(treatment, treatment_start, day)
    return _result(_custom_core(parameters, target_organs, treatment, start, name, pathogen_id), day)


def simulate_custom_timeline(parameters, target_organs, treatment, treatment_start=0,
                             name="Uploaded pathogen", pathogen_id="uploaded"):
    """Same as simulate_timeline, for an uploaded pathogen."""
    treatment, start, _ = _clean(treatment, treatment_start)
    return _timeline(_custom_core(parameters, target_organs, treatment, start, name, pathogen_id))
