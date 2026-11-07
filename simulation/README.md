# simulation/ (Part D: pathogen lab, Saket)

Simulates how a virus or bacterium grows inside the body, how much each organ is damaged, and fits
new pathogen data from a CSV. Sample values only. Research and education, not medical advice.
Shapes follow `backend/api-contract.md` (Rakhi). The contract keys are unchanged; the improvements only add keys.

## Files
- `pathogen.py` : preset pathogens, ODE models, treatment, organ damage, vitals, timeline and uncertainty band.
- `fitting.py` : CSV validation and curve fitting for uploaded pathogens.
- `test_pathogen.py`, `test_fitting.py` : automatic tests (also used by CI).
- `demo_plot.py` : draws `curves.png`, `organs_day6.png`, `fit.png` and `late_treatment.png` for the report.
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
