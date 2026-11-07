"""Pathogen lab for Genesis Twin (Part D, Saket).

What this file does
-------------------
1. Simulates how a pathogen grows inside a body over 30 days (a small ODE model).
2. Lets a treatment slider (0 to 1) weaken the pathogen.
3. Turns the pathogen load into damage for each of the 12 organs,
   using a "tropism table" (which organs does this pathogen like to attack?).
4. Returns everything in the exact JSON shape agreed in Section 9 of the plan.

The backend (Rakhi) only needs two functions:
    list_pathogens()
    simulate_pathogen(pathogen_id, day, treatment)

All parameter values are SAMPLE values for a demo. They are not real outbreak data.
Research and education only, not medical advice.
"""
from functools import lru_cache

import numpy as np
from scipy.integrate import solve_ivp

DAYS = 30  # we simulate day 0 to day 30

# The 12 organ ids shared by the whole team (Section 9 of the plan).
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
# --------------------------------------------------------------------------
PRESETS = {
    "virus_a": {
        "name": "Sample virus A (respiratory)",
        "kind": "virus",
        "params": {"beta": 1.0, "prod": 15.0, "delta": 0.8, "clear": 1.0,
                   "kill": 1.0, "s": 0.5, "dF": 0.2, "V0": 3e-3, "max_effect": 0.9},
        "tropism": {"brain": 0.15, "heart": 0.35, "lungs": 0.9, "liver": 0.15,
                    "stomach": 0.10, "intestines": 0.10, "kidneys": 0.20,
                    "bladder": 0.05, "pancreas": 0.05, "spleen": 0.30,
                    "thyroid": 0.05, "reproductive": 0.05},
    },
    "virus_b": {
        "name": "Sample virus B (gut)",
        "kind": "virus",
        "params": {"beta": 1.2, "prod": 15.0, "delta": 1.0, "clear": 1.2,
                   "kill": 1.5, "s": 0.6, "dF": 0.3, "V0": 3e-3, "max_effect": 0.9},
        "tropism": {"brain": 0.10, "heart": 0.15, "lungs": 0.10, "liver": 0.40,
                    "stomach": 0.70, "intestines": 0.90, "kidneys": 0.30,
                    "bladder": 0.10, "pancreas": 0.30, "spleen": 0.25,
                    "thyroid": 0.05, "reproductive": 0.05},
    },
    "bacterium_c": {
        "name": "Sample bacterium C (blood)",
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
# Step 3: from damage to vitals (PLACEHOLDER formulas.
# On Day 2 we agree one shared mapping with Ravneet, Part B.)
# x is damage between 0 (healthy) and 1 (severe).
# --------------------------------------------------------------------------
VITALS = {
    "brain": lambda x: {"Neuro-inflammation index": 0.1 + 0.8 * x, "Reaction score": 95 - 45 * x},
    "heart": lambda x: {"Heart rate bpm": 70 + 35 * x, "Ejection fraction %": 60 - 18 * x},
    "lungs": lambda x: {"Oxygen saturation %": 98 - 16 * x, "Breathing rate /min": 14 + 16 * x},
    "liver": lambda x: {"ALT U/L": 25 + 140 * x, "Bilirubin mg/dL": 0.7 + 2.2 * x},
    "stomach": lambda x: {"Acidity index": 1 + 1.5 * x, "Wall inflammation (0-10)": 10 * x},
    "intestines": lambda x: {"Gut inflammation (0-10)": 10 * x, "Motility %": 100 - 45 * x},
    "kidneys": lambda x: {"eGFR mL/min": 100 - 45 * x, "Creatinine mg/dL": 0.9 + 1.1 * x},
    "bladder": lambda x: {"Capacity %": 100 - 10 * x, "Irritation (0-10)": 10 * x},
    "pancreas": lambda x: {"Glucose mg/dL": 90 + 60 * x, "Lipase U/L": 40 + 120 * x},
    "spleen": lambda x: {"White cell count 10^9/L": 7 + 6 * x, "Cytokine level pg/mL": 5 + 95 * x},
    "thyroid": lambda x: {"TSH mIU/L": 2.0 + 1.5 * x, "Free T4 ng/dL": 1.2 - 0.4 * x},
    "reproductive": lambda x: {"Hormone index": 100 - 20 * x, "Inflammation (0-10)": 10 * x},
}


def _round_vitals(vitals):
    return {name: round(float(value), 1) for name, value in vitals.items()}


# --------------------------------------------------------------------------
# The two functions the backend calls
# --------------------------------------------------------------------------
def list_pathogens():
    """For GET /pathogens. Returns a list like [{"id": "virus_a", "name": "...", "kind": "virus"}]."""
    return [{"id": pid, "name": p["name"], "kind": p["kind"]} for pid, p in PRESETS.items()]


def simulate_pathogen(pathogen_id, day, treatment):
    """Simulate one pathogen.

    pathogen_id: "virus_a", "virus_b" or "bacterium_c"
    day:         0 to 30 (the day shown on the slider)
    treatment:   0 to 1 (drug or antibiotic strength, starts on day 0)

    Returns:
      load    pathogen load on that day, 0 to 1 (1 = untreated peak)
      curve   [{"day": 0, "load": 0.0}, ...] for days 0 to 30
      organs  {organ_id: {"score": 0 to 100, "vitals": {name: value}}}
    """
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    day = int(max(0, min(DAYS, day)))
    treatment = float(max(0.0, min(1.0, treatment)))

    days = np.arange(0, DAYS + 1)
    load_by_day = _solve(pathogen_id, treatment, days) / _untreated_peak(pathogen_id)
    load_by_day = np.clip(load_by_day, 0.0, 1.0)

    tropism = PRESETS[pathogen_id]["tropism"]
    organs = {}
    for organ in ORGAN_IDS:
        x = _damage_for_organ(tropism[organ], load_by_day)[day]
        organs[organ] = {
            "score": int(round(100 * (1 - x))),
            "vitals": _round_vitals(VITALS[organ](x)),
        }

    return {
        "pathogen_id": pathogen_id,
        "name": PRESETS[pathogen_id]["name"],
        "day": day,
        "treatment": treatment,
        "load": round(float(load_by_day[day]), 4),
        "curve": [{"day": int(d), "load": round(float(l), 4)} for d, l in zip(days, load_by_day)],
        "organs": organs,
    }
