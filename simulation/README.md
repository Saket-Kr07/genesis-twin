# simulation/ (Part D: pathogen lab, Saket)

Simulates how a virus or bacterium grows inside the body and how much each organ is damaged.
Sample values only. Research and education, not medical advice.

## Files
- `pathogen.py` : the model. The backend uses two functions from it.
- `test_pathogen.py` : automatic tests (also used by CI).
- `demo_plot.py` : draws `curves.png` and `organs_day6.png`.

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
from pathogen import list_pathogens, simulate_pathogen

list_pathogens()                          # [{"id": "virus_a", "name": "...", "kind": "virus"}, ...]
simulate_pathogen("virus_a", day=6, treatment=0.3)
```
`simulate_pathogen` returns `load` (0 to 1), `curve` (day and load for days 0 to 30) and `organs`
(for each of the 12 organ ids: `score` 0 to 100 and `vitals`). It raises `ValueError` for an unknown id.

Pathogen ids: `virus_a` (respiratory), `virus_b` (gut), `bacterium_c` (blood).
