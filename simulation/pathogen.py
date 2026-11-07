"""Pathogen lab for Genesis Twin (Part D, Saket).

What this file does
-------------------
1. Simulates how a pathogen grows inside a body over 30 days (a small ODE model).
2. Lets a treatment slider (0 to 1) weaken the pathogen.
3. Turns the pathogen load into damage for each of the 12 organs,
   using a "tropism table" (which organs does this pathogen like to attack?).
4. Returns everything in the shape agreed in backend/api-contract.md (Rakhi).

Functions the backend (Rakhi) calls:
    list_pathogens()                      -> GET /pathogens
    simulate_pathogen(id, day, treatment) -> POST /pathogens/simulate (preset pathogens)
    simulate_custom(parameters, target_organs, day, treatment)
                                          -> POST /pathogens/simulate for an uploaded pathogen
(fit_pathogen for CSV uploads lives in fitting.py)

All parameter values are SAMPLE values for a demo, not real outbreak data.
Research and education only, not medical advice.
"""
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp

DAYS = 30  # we simulate day 0 to day 30

# The 12 organ ids shared by the whole team.
ORGAN_IDS = [
    "brain", "heart", "lungs", "liver", "stomach", "intestines",
    "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive",
]

# How fast damage builds up and heals (per day). Damage lags behind the load:
# an organ keeps some damage for a while after the pathogen is gone.
K_DAMAGE = 0.45
K_HEAL = 0.12

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
                   "B0": 1e-3, "max_effect": 1.5},
        "tropism": {"brain": 0.50, "heart": 0.60, "lungs": 0.40, "liver": 0.50,
                    "stomach": 0.20, "intestines": 0.20, "kidneys": 0.60,
                    "bladder": 0.20, "pancreas": 0.30, "spleen": 0.60,
                    "thyroid": 0.10, "reproductive": 0.10},
    },
}


# --------------------------------------------------------------------------
# Step 1: the ODE models (how the pathogen changes over time)
# --------------------------------------------------------------------------
def _virus_rhs(t, y, p, treatment):
    """Virus model. y = [T, I, V, F]
    T = healthy target cells, I = infected cells, V = virus, F = immune response.
    The antiviral lowers how much virus infected cells produce."""
    T, I, V, F = y
    infection = p["beta"] * T * V
    production = (1.0 - treatment * p["max_effect"]) * p["prod"] * I
    dT = -infection
    dI = infection - p["delta"] * I - p["kill"] * F * I
    dV = production - p["clear"] * V
    dF = p["s"] * I - p["dF"] * F
    return [dT, dI, dV, dF]


def _bacteria_rhs(t, y, p, treatment):
    """Bacteria model. y = [B, F]
    B = bacteria (1 = carrying capacity), F = immune response.
    The antibiotic adds an extra death rate."""
    B, F = y
    dB = (p["r"] * B * (1.0 - B / p["K"])
          - p["kill"] * F * B
          - treatment * p["max_effect"] * B)
    dF = p["s"] * B - p["dF"] * F
    return [dB, dF]


def _solve(pathogen_id, treatment, t_eval):
    """Run the ODE and return the pathogen amount (virus or bacteria) at t_eval."""
    preset = PRESETS[pathogen_id]
    p = preset["params"]
    if preset["kind"] == "virus":
        y0 = [1.0, 0.0, p["V0"], 0.0]
        sol = solve_ivp(_virus_rhs, (0, DAYS), y0, t_eval=t_eval, args=(p, treatment),
                        method="LSODA", rtol=1e-8, atol=1e-13)
        amount = sol.y[2]
    else:
        y0 = [p["B0"], 0.0]
        sol = solve_ivp(_bacteria_rhs, (0, DAYS), y0, t_eval=t_eval, args=(p, treatment),
                        method="LSODA", rtol=1e-8, atol=1e-13)
        amount = sol.y[0]
    return np.clip(amount, 0.0, None)


@lru_cache(maxsize=None)
def _untreated_peak(pathogen_id):
    """Highest load without treatment. We divide by it so 'load' is a 0 to 1 number."""
    fine = np.linspace(0, DAYS, 601)
    return float(_solve(pathogen_id, 0.0, fine).max())


# --------------------------------------------------------------------------
# Step 2: from pathogen load to organ damage
# --------------------------------------------------------------------------
def _damage_for_organ(tropism_value, load_by_day):
    """Damage grows when the load is high and heals slowly. Returns a 0 to 1 value per day."""
    damage = [0.0]
    for d in range(DAYS):
        x = damage[-1]
        x = x + K_DAMAGE * tropism_value * load_by_day[d] - K_HEAL * x
        damage.append(float(min(1.0, max(0.0, x))))
    return damage


# --------------------------------------------------------------------------
# Step 3: from damage to vitals. Names follow backend/api-contract.md.
# x = damage between 0 (healthy) and 1 (severe), load = pathogen load 0 to 1.
# These formulas are PLACEHOLDERS: Day 2 we agree one shared mapping with Ravneet (Part B).
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


def _package(pathogen_id, name, load_by_day, tropism, day, treatment):
    """Build the output dictionary (load, curve, organs) from a daily load curve."""
    days = np.arange(0, DAYS + 1)
    load_by_day = np.clip(np.asarray(load_by_day, dtype=float), 0.0, 1.0)
    organs = {}
    for organ in ORGAN_IDS:
        x = _damage_for_organ(tropism.get(organ, 0.0), load_by_day)[day]
        organs[organ] = {
            "score": int(round(100 * (1 - x))),
            "vitals": _round_vitals(VITALS[organ](x, float(load_by_day[day]))),
        }
    return {
        "pathogen_id": pathogen_id,
        "name": name,
        "day": day,
        "treatment": treatment,
        "load": round(float(load_by_day[day]), 4),
        "curve": [{"day": int(d), "load": round(float(v), 4)} for d, v in zip(days, load_by_day)],
        "organs": organs,
    }


def _clean_inputs(day, treatment):
    return int(max(0, min(DAYS, day))), float(max(0.0, min(1.0, treatment)))


# --------------------------------------------------------------------------
# Functions the backend calls
# --------------------------------------------------------------------------
def list_pathogens():
    """For GET /pathogens. Returns [{"id", "name", "kind", "preset": True}, ...]."""
    return [{"id": pid, "name": p["name"], "kind": p["kind"], "preset": True}
            for pid, p in PRESETS.items()]


def simulate_pathogen(pathogen_id, day, treatment):
    """Simulate one preset pathogen.

    pathogen_id: "respiratory_virus", "gut_virus" or "bloodstream_bacterium"
    day:         0 to 30 (the day shown on the slider)
    treatment:   0 to 1 (drug or antibiotic strength, starts on day 0)

    Returns:
      load    pathogen load on that day, 0 to 1 (1 = untreated peak)
      curve   [{"day": 0, "load": 0.0}, ...] for days 0 to 30
      organs  {organ_id: {"score": 0 to 100, "vitals": {name: value}}}
    """
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    day, treatment = _clean_inputs(day, treatment)
    days = np.arange(0, DAYS + 1)
    load_by_day = _solve(pathogen_id, treatment, days) / _untreated_peak(pathogen_id)
    return _package(pathogen_id, PRESETS[pathogen_id]["name"], load_by_day,
                    PRESETS[pathogen_id]["tropism"], day, treatment)


def _value(p):
    """Accept either 0.8 or {"value": 0.8, "low": ..., "high": ...}."""
    return float(p["value"] if isinstance(p, dict) else p)


def simulate_custom(parameters, target_organs, day, treatment, name="Uploaded pathogen",
                    pathogen_id="uploaded"):
    """Simulate a pathogen that was uploaded and fitted with fit_pathogen (fitting.py).

    parameters:    the "parameters" output of fit_pathogen (needs growth_rate, decay_rate, peak_day)
    target_organs: organ ids the pathogen attacks, e.g. ["lungs"] (fit_pathogen returns them).
                   If the list has no known organ, the pathogen is treated as systemic.
    Treatment lowers the peak by up to 90 percent and speeds up the decline by up to 2 times.
    """
    try:
        growth = _value(parameters["growth_rate"])
        decay = _value(parameters["decay_rate"])
        peak_day = _value(parameters["peak_day"])
    except (KeyError, TypeError):
        raise ValueError("parameters must contain growth_rate, decay_rate and peak_day")
    day, treatment = _clean_inputs(day, treatment)
    peak_day = max(0.0, min(float(DAYS), peak_day))

    t = np.arange(0, DAYS + 1, dtype=float)
    decay_eff = decay * (1.0 + treatment)
    shape = 2.0 / (np.exp(-growth * (t - peak_day)) + np.exp(decay_eff * (t - peak_day)))
    load_by_day = shape * (1.0 - 0.9 * treatment)

    targets = [o for o in (target_organs or []) if o in ORGAN_IDS]
    if targets:
        tropism = {o: (0.9 if o in targets else 0.1) for o in ORGAN_IDS}
    else:
        tropism = {o: 0.4 for o in ORGAN_IDS}
    return _package(pathogen_id, name, load_by_day, tropism, day, treatment)
