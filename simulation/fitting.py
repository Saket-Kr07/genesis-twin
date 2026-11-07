"""CSV upload, validation and curve fitting for new pathogens (Part D, Saket).

Main function (used by POST /pathogens/upload):
    fit_pathogen(csv_text)

The CSV needs the columns  day  and  load  (at least 5 time points, no missing or negative values).
Optional columns: tissue (e.g. lung, gut), receptor.

The model is a standard "rise and fall" curve with four numbers:
    peak_load, peak_day, growth_rate (per day, the rise), decay_rate (per day, the fall)
The ranges (low and high) are 95 percent confidence ranges from the fit.
With only a few time points the ranges are wide. That is honest, not a bug.

Research and education only, not medical advice.
"""
import csv
import io
import math

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit

MIN_POINTS = 5
MAX_ROWS = 5000

# Words in the tissue column mapped to organ ids (checked in order).
TISSUE_WORDS = [
    (("lung", "respir", "airway", "trachea", "bronch", "nasal"), "lungs"),
    (("intestin", "colon", "bowel", "gut", "faec", "fecal"), "intestines"),
    (("stomach", "gastric"), "stomach"),
    (("liver", "hepat"), "liver"),
    (("brain", "cns", "neural", "neuro"), "brain"),
    (("heart", "cardiac"), "heart"),
    (("kidney", "renal"), "kidneys"),
    (("bladder", "urinary", "urine"), "bladder"),
    (("pancrea",), "pancreas"),
    (("spleen",), "spleen"),
    (("thyroid",), "thyroid"),
    (("blood", "plasma", "serum"), "spleen"),
    (("reproductive", "uterus", "ovar", "testis", "testes", "prostate"), "reproductive"),
]


def _curve(t, peak_load, peak_day, growth, decay):
    """Rise and fall curve. Equals peak_load at t = peak_day."""
    return 2.0 * peak_load / (np.exp(-growth * (t - peak_day)) + np.exp(decay * (t - peak_day)))


def _number(text):
    """Return a finite float, or None if the text is not a number."""
    try:
        value = float(text.strip())
    except (ValueError, AttributeError):
        return None
    return value if math.isfinite(value) else None


def _read_csv(csv_text):
    """Parse and check the file. Returns (days, loads, tissues, receptors, errors)."""
    errors = []
    if isinstance(csv_text, bytes):
        csv_text = csv_text.decode("utf-8-sig", errors="replace")
    text = (csv_text or "").lstrip("\ufeff")
    if not text.strip():
        return None, None, [], [], ["The file is empty."]

    first = text.splitlines()[0]
    delimiter = max([",", ";", "\t"], key=first.count)
    lines = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header = [h.strip().lower() for h in lines[0]]
    missing = [c for c in ("day", "load") if c not in header]
    if missing:
        return None, None, [], [], ["The file must have columns named day and load. Missing: %s." % ", ".join(missing)]
    di, li = header.index("day"), header.index("load")
    ti = header.index("tissue") if "tissue" in header else None
    ri = header.index("receptor") if "receptor" in header else None

    if len(lines) - 1 > MAX_ROWS:
        return None, None, [], [], ["The file has too many rows (the limit is %d)." % MAX_ROWS]

    days, loads, tissues, receptors, seen = [], [], [], [], {}
    for line_no, cells in enumerate(lines[1:], start=2):
        if not any(c.strip() for c in cells):
            continue  # skip blank rows
        raw_day = cells[di] if di < len(cells) else ""
        raw_load = cells[li] if li < len(cells) else ""
        row_ok = True
        for label, raw in (("day", raw_day), ("load", raw_load)):
            if not raw.strip():
                errors.append("Row %d: %s is missing." % (line_no, label))
                row_ok = False
            elif _number(raw) is None:
                errors.append("Row %d: %s must be a number (found '%s')." % (line_no, label, raw.strip()))
                row_ok = False
            elif _number(raw) < 0:
                errors.append("Row %d: %s cannot be negative." % (line_no, label))
                row_ok = False
        if not row_ok:
            continue
        d, v = _number(raw_day), _number(raw_load)
        if d in seen:
            errors.append("Day %g appears more than once (rows %d and %d)." % (d, seen[d], line_no))
            continue
        seen[d] = line_no
        days.append(d)
        loads.append(v)
        if ti is not None and ti < len(cells) and cells[ti].strip():
            tissues.append(cells[ti].strip())
        if ri is not None and ri < len(cells) and cells[ri].strip():
            receptors.append(cells[ri].strip())

    if not errors and len(days) < MIN_POINTS:
        errors.append("At least %d time points are needed, but the file has %d." % (MIN_POINTS, len(days)))
    if not errors and max(loads) == 0:
        errors.append("All load values are zero, so there is nothing to fit.")
    if not errors and max(loads) == min(loads):
        errors.append("All load values are the same, so no rise or fall can be fitted.")
    return days, loads, tissues, receptors, errors


def _map_tissues(tissues):
    organs, unknown = [], []
    for name in dict.fromkeys(t for t in tissues):  # unique, keep order
        low = name.lower()
        hit = next((organ for words, organ in TISSUE_WORDS if any(w in low for w in words)), None)
        if hit is None:
            unknown.append(name)
        elif hit not in organs:
            organs.append(hit)
    return organs, unknown


def _failed(errors):
    return {"parameters": None, "validation_errors": errors, "warnings": [], "fit": None,
            "fitted_curve": [], "target_organs": [], "unrecognised_tissues": []}


def fit_pathogen(csv_text):
    """Validate a CSV and fit the rise and fall curve.

    Returns (matches backend/api-contract.md, plus a few extra keys):
      parameters         {"growth_rate": {"value", "low", "high"}, "decay_rate": ..., "peak_day": ..., "peak_load": ...}
                         or None if the file is bad
      validation_errors  list of plain-language messages (empty if the file is fine)
      warnings           things to know about the fit (not errors)
      fit                {"r_squared", "points", "model"}
      fitted_curve       [{"day", "load"}, ...] for the plot
      target_organs      organ ids found from the tissue column (use with simulate_custom)
      unrecognised_tissues  tissue names we could not map to an organ
    """
    days, loads, tissues, receptors, errors = _read_csv(csv_text)
    if errors:
        return _failed(errors)

    order = np.argsort(days)
    d = np.asarray(days, dtype=float)[order]
    y = np.asarray(loads, dtype=float)[order]
    scale = float(y.max())
    yn = y / scale  # work with a 0 to 1 curve

    peak_guess = float(min(max(d[int(yn.argmax())], d.min() + 1e-6), d.max() - 1e-6))
    lower = [0.2, float(d.min()), 0.01, 0.01]
    upper = [5.0, float(d.max()), 20.0, 20.0]
    try:
        popt, pcov = curve_fit(_curve, d, yn, p0=[1.0, peak_guess, 1.0, 0.7],
                               bounds=(lower, upper), max_nfev=20000)
    except (RuntimeError, ValueError):
        return _failed(["The curve could not be fitted to this data. "
                        "Check that the load rises and then falls over the days."])

    n = len(d)
    dof = max(1, n - 4)
    tcrit = float(stats.t.ppf(0.975, dof))
    se = np.sqrt(np.diag(pcov)) if np.all(np.isfinite(pcov)) else np.full(4, np.nan)

    def entry(value, error, factor=1.0):
        value, error = float(value) * factor, float(error) * factor
        if not math.isfinite(error):
            return {"value": round(value, 4), "low": None, "high": None}
        return {"value": round(value, 4),
                "low": round(max(0.0, value - tcrit * error), 4),
                "high": round(value + tcrit * error, 4)}

    parameters = {
        "growth_rate": entry(popt[2], se[2]),
        "decay_rate": entry(popt[3], se[3]),
        "peak_day": entry(popt[1], se[1]),
        "peak_load": entry(popt[0], se[0], factor=scale),
    }

    fitted = _curve(d, *popt)
    ss_res = float(np.sum((yn - fitted) ** 2))
    ss_tot = float(np.sum((yn - yn.mean()) ** 2))
    r2 = round(1.0 - ss_res / ss_tot, 4) if ss_tot > 0 else None

    warnings = []
    if int(yn.argmax()) in (0, n - 1):
        warnings.append("The highest load is at the first or last time point, so the rise or the fall is not "
                        "fully covered. The growth and decay estimates are uncertain.")
    if r2 is not None and r2 < 0.7:
        warnings.append("The fit is weak (R squared %.2f). Check the data or add more time points." % r2)
    if n < 8:
        warnings.append("Only %d time points: the ranges are wide. More time points give tighter ranges." % n)

    grid = np.arange(int(d.min()), int(min(d.max(), d.min() + 400)) + 1, dtype=float)
    target_organs, unknown = _map_tissues(tissues)
    return {
        "parameters": parameters,
        "validation_errors": [],
        "warnings": warnings,
        "fit": {"r_squared": r2, "points": n, "model": "rise_and_fall_curve"},
        "fitted_curve": [{"day": float(g), "load": round(float(v) * scale, 4)}
                         for g, v in zip(grid, _curve(grid, *popt))],
        "target_organs": target_organs,
        "unrecognised_tissues": unknown,
    }
