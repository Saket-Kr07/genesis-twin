# simulation/ (Part D: pathogen lab, Saket)

Simulates how a virus or bacterium grows inside the body, how much each organ is damaged, and fits
new pathogen data from a CSV. Sample values only. Research and education, not medical advice.
Shapes follow `backend/api-contract.md` (Rakhi).

## Files
- `pathogen.py` : preset pathogens, the ODE models, organ damage and vitals.
- `fitting.py` : CSV validation and curve fitting for uploaded pathogens.
- `test_pathogen.py`, `test_fitting.py` : automatic tests (also used by CI).
- `demo_plot.py` : draws `curves.png`, `organs_day6.png` and `fit.png` for the report.
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
from pathogen import list_pathogens, simulate_pathogen, simulate_custom
from fitting import fit_pathogen
```

| Endpoint | Call |
|---|---|
| GET /pathogens | `list_pathogens()` returns `[{"id", "name", "kind", "preset": True}]` |
| POST /pathogens/simulate (preset) | `simulate_pathogen("respiratory_virus", day=6, treatment=0.3)` |
| POST /pathogens/upload | `fit_pathogen(csv_text)` (str or bytes) |
| POST /pathogens/simulate (uploaded) | `simulate_custom(parameters, target_organs, day, treatment)` |

Preset ids: `respiratory_virus`, `gut_virus`, `bloodstream_bacterium`.

`simulate_pathogen` and `simulate_custom` return `load` (0 to 1, where 1 is the untreated peak),
`curve` (day and load for days 0 to 30) and `organs` (all 12 organ ids, each with `score` 0 to 100 and `vitals`).
Unknown ids raise `ValueError`.

`fit_pathogen` returns `parameters` (`growth_rate`, `decay_rate`, `peak_day`, `peak_load`, each with
`value`, `low`, `high`) and `validation_errors`. If the file is bad, `parameters` is `None` and the errors are
plain-language strings with row numbers. Extra keys: `warnings`, `fit`, `fitted_curve`, `target_organs`,
`unrecognised_tissues`.

To run an uploaded pathogen later, store the `parameters` and `target_organs` from the upload (in the experiment
or pathogen record) and pass them to `simulate_custom`.
