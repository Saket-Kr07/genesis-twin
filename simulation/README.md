# simulation/ (Part D: pathogen lab, Saket)

Simulates how a virus or bacterium grows inside the body, how much each organ is damaged, and fits
new pathogen data from a CSV. Sample values only. Research and education, not medical advice.
Shapes follow `backend/api-contract.md` (Rakhi). The contract keys are unchanged; the improvements only add keys.

## Files
- `pathogen.py` : preset pathogens, ODE models, treatment, organ damage, vitals, timeline and uncertainty band.
- `fitting.py` : CSV validation and curve fitting for uploaded pathogens.
- `test_pathogen.py`, `test_fitting.py` : automatic tests (also used by CI).
- `validate_published.py`, `test_validate.py` : check a preset against a real published time series (see below).
- `demo_plot.py` : draws `curves.png`, `organs_day6.png`, `fit.png`, `late_treatment.png` and `body_profiles.png` for the report.
- `sample_data/example_pathogen.csv` : synthetic example for testing uploads (not real data).

## Run it
```
python -m pip install -r requirements.txt
python -m pytest -q
python demo_plot.py
```

## For the backend (Rakhi)
```python
import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "simulation"))
from pathogen import (list_pathogens, simulate_pathogen, simulate_timeline, load_band,
                      simulate_custom, simulate_custom_timeline)
from fitting import fit_pathogen
```

| Endpoint | Call |
|---|---|
| GET /pathogens | `list_pathogens()` returns `[{"id", "name", "kind", "preset": True}]` |
| POST /pathogens/simulate (preset) | `simulate_pathogen("respiratory_virus", day=6, treatment=0.3)` |
| same, treatment starts late | `simulate_pathogen(..., treatment_start=3)` (optional, default 0) |
| whole timeline in one call (for the sliders) | `simulate_timeline("respiratory_virus", treatment=0.3, treatment_start=0)` |
| body profile (child, adult, older, height, weight, face scan) | add `profile={...}` to any call below (see Body profile) |
| profile summary for the form | `describe_profile(profile)` |
| uncertainty band | `load_band("respiratory_virus", treatment=0.3)` |
| POST /pathogens/upload | `fit_pathogen(csv_text)` (str or bytes) |
| POST /pathogens/simulate (uploaded) | `simulate_custom(parameters, target_organs, day, treatment)` or `simulate_custom_timeline(...)` |

Preset ids: `respiratory_virus`, `gut_virus`, `bloodstream_bacterium`. Unknown ids raise `ValueError`.

### What comes back
Contract keys (unchanged): `load` (0 to 1, where 1 is the untreated peak), `curve` (daily, days 0 to 30) and
`organs` (all 12 organ ids, each with `score` 0 to 100 and `vitals`).

Extra keys (new, safe to ignore):
- `curve_smooth`: load every quarter day (121 points), for smooth plots.
- `organs[id]["status"]`: `"healthy"` (80 and above), `"stressed"` (50 to 79) or `"critical"` (below 50).
- `treatment_start`: the day treatment began.

`simulate_timeline` returns everything for all days in one call, so the day slider never waits for the server:
- `times`: every quarter day (121 numbers) and `load` at each time.
- `scores`: `{organ_id: [score at each time]}`. Smooth, use it to fade organ colours.
- `days`: 31 entries `{"day", "load", "organs": {organ_id: {score, status, vitals}}}`. Use it for the info panel.

`load_band` returns `{"times", "low", "high", "nominal"}`: the 10th to 90th percentile of 40 runs with the main
parameters changed by up to 15 percent. The same inputs always give the same band.

### Uploaded pathogens
`fit_pathogen` returns `parameters` (`growth_rate`, `decay_rate`, `peak_day`, `peak_load`, each with `value`, `low`,
`high`) and `validation_errors`. If the file is bad, `parameters` is `None` and the errors are plain-language strings
with row numbers. Extra keys: `warnings`, `fit`, `fitted_curve`, `target_organs`, `unrecognised_tissues`.
Store the `parameters` and `target_organs` from the upload and pass them to `simulate_custom` later.

### Notes
- Treatment is a slider from 0 to 1 with diminishing returns (0.5 gives about 70 percent of the full effect).
- Results are cached, so dragging a slider is fast (about 4 ms per call).

## Body profile (male, female, child, older, height, weight, face scan)
Every simulate function and `load_band` take an optional `profile`:
```python
profile = {"sex": "female", "age": 8, "height_cm": 128, "weight_kg": 26,
           "baseline_vitals": {"heart_rate": 92, "breathing_rate": 22}}   # last part optional (face scan)
simulate_timeline("respiratory_virus", treatment=0.3, profile=profile)
describe_profile(profile)   # {"profile", "bmi", "age_group", "effects"} for the profile form
```
- Missing fields use a reference adult (male, 30 years, 175 cm, 70 kg). No profile gives the same result as before.
- Allowed ranges: age 0 to 110, height 40 to 230 cm, weight 2 to 250 kg (height and weight must look realistic together),
  face-scan heart rate 30 to 220, breathing rate 4 to 60. Bad input raises `ValueError` with a plain message.
- The output has two extra keys: `profile` (the cleaned profile) and `profile_effects` (a list of plain sentences naming
  every assumption that was applied). Show this list in the UI so the assumptions are visible.

What the profile changes (all SAMPLE assumptions, in `_adjustments` in `pathogen.py`):
- **Age 40 to 65 and above:** weaker immune response (down to 80 percent) and less organ reserve (10 percent).
- **Children (under 18):** higher resting heart and breathing rate, lower blood pressure. No extra infection assumptions.
- **Height, sex and age:** resting lung capacity scales with height cubed, is lower for females and for older adults;
  kidney eGFR falls after 40.
- **Body mass index (adults only):** overweight raises lung and heart damage; underweight raises damage for all organs.
- **Face scan:** a measured resting heart rate or breathing rate replaces the default resting value. The change caused by
  the infection is added on top. These are webcam estimates and must be labelled as estimates.

## Example outputs for teammates
`python export_samples.py` writes `sample_output/*.json` (one file per call, with a `README.txt`).
Rakhi, Rudraksh and Shambhavi can build and test against these files without running Python.

## Validation against real published data
```
python validate_published.py --csv data.csv --pathogen respiratory_virus --label "Author Year, DOI 10.xxxx/xxxx"
```
- `data.csv` needs the columns `day` and `load`, taken from a published paper (a supplementary table, or a figure read with a free
  tool such as WebPlotDigitizer). Add `--log10` if the paper's load is in log10 units. Remove values at or below the detection limit.
- The citation (`--label`) is required. Only use real data you can cite.
- It fits the rise-and-fall curve to the published data and to our preset, and compares the growth rate and decay rate
  (these do not depend on which day the paper calls day 0), then the overall shape after the best shift in days.
- It writes `validation_output/validation.png`, `validation_report.json` and `validation_report.md`, with a verdict
  (agrees, partly agrees, does not agree) and which preset parameters to change if it does not agree.
- Agreement means the rate is inside the published 95 percent range or within 30 percent of it (`--tolerance`).
- A match checks the SHAPE of our sample pathogen against one paper. It is not proof that the model is correct in general.
- The tests use synthetic data only, to check that the script works. Never put synthetic results in the report as validation.
