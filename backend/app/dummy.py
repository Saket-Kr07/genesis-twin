"""Dummy (made-up but correctly shaped) versions of the functions the other parts provide.

Swap each one for the real function on Day 2 (see api-contract.md for the shapes):
  predict_health      -> ml/          (Ravneet)
  simulate_pathogen   -> simulation/  (Saket)
  fit_pathogen        -> simulation/  (Saket)
  get_sources         -> research/    (Punya)

All numbers here are fake. Research and education only, not medical advice."""
import csv
import io
import math

ORGAN_IDS = [
    "brain", "heart", "lungs", "liver", "stomach", "intestines",
    "kidneys", "bladder", "pancreas", "spleen", "thyroid", "reproductive",
]

SYSTEMS = [
    "skeletal", "muscular", "nervous", "cardiovascular", "respiratory", "digestive",
    "urinary", "endocrine", "immune", "reproductive", "integumentary",
]

ORGAN_SYSTEM = {
    "brain": "nervous", "heart": "cardiovascular", "lungs": "respiratory",
    "liver": "digestive", "stomach": "digestive", "intestines": "digestive",
    "pancreas": "digestive", "kidneys": "urinary", "bladder": "urinary",
    "spleen": "immune", "thyroid": "endocrine", "reproductive": "reproductive",
}

# Mesh names follow system__structure__side. The viewer team renames the real meshes to match.
_MESHES = {
    "brain": ["nervous__brain"],
    "heart": ["cardiovascular__heart"],
    "lungs": ["respiratory__lung__left", "respiratory__lung__right"],
    "liver": ["digestive__liver"],
    "stomach": ["digestive__stomach"],
    "intestines": ["digestive__small_intestine", "digestive__large_intestine"],
    "pancreas": ["digestive__pancreas"],
    "kidneys": ["urinary__kidney__left", "urinary__kidney__right"],
    "bladder": ["urinary__bladder"],
    "spleen": ["immune__spleen"],
    "thyroid": ["endocrine__thyroid"],
}
_REPRODUCTIVE_MESHES = {
    "male": ["reproductive__prostate", "reproductive__testis__left", "reproductive__testis__right"],
    "female": ["reproductive__uterus", "reproductive__ovary__left", "reproductive__ovary__right"],
}


# ---------------------------------------------------------------- body

def get_body(sex: str) -> dict:
    systems = [
        {"system": s, "glb_url": f"/static/models/{sex}/{s}.glb"} for s in SYSTEMS
    ]
    organs = []
    for organ in ORGAN_IDS:
        meshes = _REPRODUCTIVE_MESHES[sex] if organ == "reproductive" else _MESHES[organ]
        organs.append(
            {"id": organ, "system": ORGAN_SYSTEM[organ], "mesh": meshes[0], "meshes": meshes}
        )
    return {"sex": sex, "systems": systems, "organs": organs}


# ---------------------------------------------------------------- predict_health

def _clamp(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, round(x)))


def _vitals(organ: str, score: int, age: int, sex: str) -> dict:
    d = (100 - score) / 100.0  # 0 = healthy, 1 = very unhealthy
    older = max(0, age - 30)
    female = sex == "female"
    if organ == "heart":
        sys_bp = round(112 + d * 45 + older * 0.25)
        dia_bp = round(72 + d * 22 + older * 0.1)
        return {
            "heart_rate": round(62 + d * 30 + (3 if female else 0)),
            "blood_pressure": f"{sys_bp}/{dia_bp}",
            "ejection_fraction": round(64 - d * 25),
        }
    if organ == "lungs":
        return {
            "oxygen_saturation": round(99 - d * 12),
            "breathing_rate": round(13 + d * 10),
            "lung_capacity": round(5.8 - d * 2.0 - (0.9 if female else 0) - older * 0.02, 1),
        }
    if organ == "brain":
        return {
            "neuro_inflammation_index": round(0.5 + d * 4.5, 1),
            "reaction_score": round(95 - d * 40 - older * 0.2),
        }
    if organ in ("liver", "stomach", "pancreas", "intestines"):
        return {
            "alt": round(20 + d * 60),
            "ast": round(22 + d * 55),
            "bilirubin": round(0.6 + d * 1.2, 1),
            "gut_inflammation": round(1 + d * 6, 1),
        }
    if organ in ("kidneys", "bladder"):
        return {
            "egfr": round(112 - d * 50 - older * 0.6),
            "creatinine": round(0.8 + d * 0.9, 2),
            "hydration": round(95 - d * 30),
        }
    if organ == "thyroid":
        return {
            "glucose": round(88 + d * 60),
            "tsh": round(1.5 + d * 3.0, 2),
            "cortisol": round(12 + d * 10, 1),
        }
    if organ == "spleen":
        return {
            "white_cell_count": round(6.5 + d * 5.0, 1),
            "cytokine_level": round(2 + d * 40),
            "pathogen_load": 0.0,
        }
    return {"hormone_indicators": round(90 - d * 45)}  # reproductive


def predict_health(age: int, sex: str, sleep: float, exercise: int, smoking: int, diet: int) -> dict:
    """Formula-based stand-in. Responds to the inputs so the demo sliders visibly work."""
    sleep_penalty = abs(sleep - 7.5) * 3
    base = (
        92
        - max(0, age - 25) * 0.45
        - smoking * 0.5
        - sleep_penalty
        + exercise * 2.2
        + (diet - 3) * 3
    )
    extra = {
        "heart": exercise * 1.5 - smoking * 0.4,
        "lungs": -smoking * 1.0,
        "brain": -sleep_penalty * 1.5,
        "liver": (diet - 3) * 3,
        "stomach": (diet - 3) * 2,
        "intestines": (diet - 3) * 2.5,
        "pancreas": (diet - 3) * 2,
        "spleen": exercise * 0.5,
        "reproductive": -smoking * 0.3,
    }
    result = {}
    for organ in ORGAN_IDS:
        score = _clamp(base + extra.get(organ, 0))
        result[organ] = {"score": score, "vitals": _vitals(organ, score, age, sex)}
    return result


# ---------------------------------------------------------------- pathogens

PATHOGENS = [
    {"id": "respiratory_virus", "name": "Respiratory virus (sample parameters)", "kind": "virus", "preset": True},
    {"id": "gut_virus", "name": "Gut virus (sample parameters)", "kind": "virus", "preset": True},
    {"id": "bloodstream_bacterium", "name": "Bloodstream bacterium (sample parameters)", "kind": "bacterium", "preset": True},
    {"id": "novel_virus_demo", "name": "Uploaded novel virus (demo)", "kind": "virus", "preset": False},
]

# peak = highest load, peak_day = day of the peak, width = how wide the curve is,
# tropism = how strongly each organ is hit (0 to 1).
_PARAMS = {
    "respiratory_virus": {
        "peak": 6.0, "peak_day": 6, "width": 3.5,
        "tropism": {"lungs": 0.9, "spleen": 0.4, "brain": 0.15},
    },
    "gut_virus": {
        "peak": 5.0, "peak_day": 4, "width": 3.0,
        "tropism": {"intestines": 0.9, "stomach": 0.7, "liver": 0.3, "spleen": 0.3},
    },
    "bloodstream_bacterium": {
        "peak": 7.0, "peak_day": 5, "width": 4.0,
        "tropism": {"spleen": 0.8, "kidneys": 0.6, "heart": 0.5, "liver": 0.5, "lungs": 0.3},
    },
    "novel_virus_demo": {
        "peak": 5.5, "peak_day": 8, "width": 4.0,
        "tropism": {"lungs": 0.6, "brain": 0.3, "spleen": 0.4},
    },
}


class UnknownPathogen(KeyError):
    pass


def get_pathogen(pathogen_id: str):
    for p in PATHOGENS:
        if p["id"] == pathogen_id:
            return p
    return None


def list_pathogens(include_all: bool) -> list:
    return [p for p in PATHOGENS if include_all or p["preset"]]


def simulate_pathogen(pathogen_id: str, day: int, treatment: float) -> dict:
    params = _PARAMS.get(pathogen_id)
    if params is None:
        raise UnknownPathogen(pathogen_id)

    def load_at(d: float) -> float:
        bump = math.exp(-((d - params["peak_day"]) ** 2) / (2 * params["width"] ** 2))
        return params["peak"] * bump * (1 - 0.85 * treatment)

    curve = [{"day": d, "load": round(load_at(d), 3)} for d in range(0, 31)]
    load = round(load_at(day), 3)

    baseline = predict_health(40, "male", 7, 3, 0, 3)
    organs = {}
    for organ, weight in params["tropism"].items():
        damage = min(1.0, weight * load_at(day) / params["peak"])
        score = _clamp(baseline[organ]["score"] * (1 - 0.8 * damage))
        vitals = _vitals(organ, score, 40, "male")
        if organ == "spleen":
            vitals["pathogen_load"] = load
        organs[organ] = {"score": score, "vitals": vitals}
    return {"load": load, "curve": curve, "organs": organs}


def fit_pathogen(csv_text: str) -> dict:
    """Checks the CSV like the real function will, then returns fixed example parameters."""
    reader = csv.DictReader(io.StringIO(csv_text))
    columns = [c.strip().lower() for c in (reader.fieldnames or []) if c is not None]
    missing = [c for c in ("day", "load") if c not in columns]
    if missing:
        return {
            "parameters": None,
            "validation_errors": [
                "The file is missing the required column(s): "
                + ", ".join(missing)
                + ". The first row must contain the column names 'day' and 'load'."
            ],
        }

    errors = []
    good_rows = 0
    for line_no, row in enumerate(reader, start=2):
        values = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k is not None}
        row_ok = True
        for col in ("day", "load"):
            text = values.get(col, "")
            if text == "":
                errors.append(f"Row {line_no}: the '{col}' value is empty.")
                row_ok = False
                continue
            try:
                number = float(text)
            except ValueError:
                errors.append(f"Row {line_no}: '{text}' in column '{col}' is not a number.")
                row_ok = False
                continue
            if number < 0:
                errors.append(f"Row {line_no}: the '{col}' value is negative.")
                row_ok = False
        if row_ok:
            good_rows += 1
    if good_rows < 5 and not errors:
        errors.append(f"At least 5 time points are needed, but only {good_rows} were found.")
    if errors:
        return {"parameters": None, "validation_errors": errors[:10]}

    return {
        "parameters": {
            "growth_rate": {"value": 0.8, "low": 0.7, "high": 0.9},
            "clearance_rate": {"value": 0.35, "low": 0.28, "high": 0.42},
        },
        "validation_errors": [],
    }


# ---------------------------------------------------------------- get_sources

_SOURCES = [
    ("[Sample] Within-host viral dynamics with an adaptive immune response", "10.1234/sample.001", "2026-11-03", "peer_reviewed", "Updated viral clearance rate"),
    ("[Sample] Receptor expression across human lung tissue", "10.1234/sample.002", "2026-10-30", "peer_reviewed", "Refined lung tropism weight"),
    ("[Sample] Early cytokine response in bacterial bloodstream infection", "10.1234/sample.003", "2026-10-27", "preprint", "Candidate change to immune killing rate"),
    ("[Sample] Sleep duration and inflammatory markers in adults", "10.1234/sample.004", "2026-10-24", "peer_reviewed", "Adjusted sleep effect on brain score"),
    ("[Sample] Smoking and lung function decline: a cohort analysis", "10.1234/sample.005", "2026-10-21", "peer_reviewed", "Adjusted smoking effect on lung score"),
    ("[Sample] Gut epithelial infection kinetics of enteric viruses", "10.1234/sample.006", "2026-10-17", "preprint", "Candidate change to gut virus growth rate"),
    ("[Sample] Exercise frequency and cardiovascular risk markers", "10.1234/sample.007", "2026-10-13", "peer_reviewed", "Adjusted exercise effect on heart score"),
    ("[Sample] Dietary patterns and liver enzyme levels", "10.1234/sample.008", "2026-10-09", "peer_reviewed", "Adjusted diet effect on liver score"),
]


def get_sources(limit: int) -> list:
    """Static sample list, newest first. Titles and DOIs are placeholders, not real papers."""
    return [
        {
            "title": title, "doi": doi, "date": date, "type": kind,
            "change": change, "model_version": "v0.1.0",
        }
        for title, doi, date, kind, change in _SOURCES[:limit]
    ]
