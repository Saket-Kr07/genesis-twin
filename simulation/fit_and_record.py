"""Fit a CSV, simulate the fitted pathogen, and save a reproducible experiment record.

Example:
  python fit_and_record.py --csv real_data/caltech_participant1.csv ^
      --label "Viloria Winnett et al 2022, CaltechDATA DOI 10.22002/D1.20049, participant A nasal swab" ^
      --tropism real_data/tropism_ACE2.json --out real_data/experiment_participant1.json

Research and education only."""
import argparse
import datetime
import json

from fitting import fit_pathogen
from pathogen import simulate_custom_timeline, MODEL_VERSION


def load_tropism(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tropism", data)   # accepts {"tropism": {...}} or {...}


ap = argparse.ArgumentParser()
ap.add_argument("--csv", required=True)
ap.add_argument("--label", required=True, help="source of the data, saved in the record")
ap.add_argument("--tropism", help="optional tropism json from tropism.py")
ap.add_argument("--treatment", type=float, default=0.0)
ap.add_argument("--out", required=True)
a = ap.parse_args()

with open(a.csv, encoding="utf-8") as f:
    fit = fit_pathogen(f.read())
if fit["validation_errors"]:
    print("The file has problems:")
    for m in fit["validation_errors"]:
        print(" -", m)
    raise SystemExit(1)

trop = load_tropism(a.tropism) if a.tropism else None
tl = simulate_custom_timeline(fit["parameters"], fit["target_organs"], a.treatment,
                              name="Fitted: " + a.label[:60], tropism=trop)

record = {
    "created": datetime.datetime.now().isoformat(timespec="seconds"),
    "model_version": MODEL_VERSION,
    "seed": None,   # the model is deterministic, so no random seed is used
    "source_label": a.label,
    "input_csv": a.csv,
    "treatment": a.treatment,
    "tropism_file": a.tropism,
    "fit": fit["fit"],
    "parameters": fit["parameters"],
    "warnings": fit["warnings"],
    "target_organs": fit["target_organs"],
    "peak_scores": {o: min(s) for o, s in tl["scores"].items()},   # lowest organ score over 30 days
    "disclaimer": "Research and education only, not medical advice.",
}
with open(a.out, "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)

p = fit["parameters"]
print("R squared:", fit["fit"]["r_squared"], " points:", fit["fit"]["points"])
for k in ("growth_rate", "decay_rate", "peak_day"):
    print("%-12s %s  (95%%: %s to %s)" % (k, p[k]["value"], p[k]["low"], p[k]["high"]))
for w in fit["warnings"]:
    print("Warning:", w)
print("Lowest organ scores over 30 days:", {o: v for o, v in record["peak_scores"].items() if v < 100})
print("Wrote", a.out)
