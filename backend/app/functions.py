"""One place where the API gets predict_health, simulate_pathogen, fit_pathogen and
get_sources. For each function we try the teammate's real module; if it cannot be
imported, we use the dummy from dummy.py. Check which is live: GET /health/functions.

TO CONNECT A REAL FUNCTION: edit the (module, attribute) lists in CANDIDATES below
once the owner tells you where it lives. The input and output shapes must match
api-contract.md. Repo root is added to sys.path so `ml`, `simulation`, `research`
folders at the repo root can be imported."""
import importlib
import logging
import sys
from pathlib import Path

from . import dummy

log = logging.getLogger("genesis.functions")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Guesses only. Replace with the real paths from Ravneet, Saket and Punya.
CANDIDATES = {
    "predict_health": [("ml.predict", "predict_health"), ("ml", "predict_health")],
    "simulate_pathogen": [("simulation.api", "simulate_pathogen"), ("simulation", "simulate_pathogen")],
    "fit_pathogen": [("simulation.api", "fit_pathogen"), ("simulation", "fit_pathogen")],
    "get_sources": [("research.sources", "get_sources"), ("research", "get_sources")],
}

SOURCE = {}  # function name -> "real:module.attr" or "dummy"


def _resolve(name: str):
    for module_name, attr in CANDIDATES[name]:
        try:
            fn = getattr(importlib.import_module(module_name), attr)
        except (ImportError, AttributeError):
            continue
        SOURCE[name] = f"real:{module_name}.{attr}"
        log.info("%s -> %s", name, SOURCE[name])
        return fn
    SOURCE[name] = "dummy"
    log.warning("%s -> dummy (no real function found)", name)
    return getattr(dummy, name)


predict_health = _resolve("predict_health")
simulate_pathogen = _resolve("simulate_pathogen")
fit_pathogen = _resolve("fit_pathogen")
get_sources = _resolve("get_sources")

# Not provided by other parts: these stay on the dummy library for now.
get_body = dummy.get_body
get_pathogen = dummy.get_pathogen
list_pathogens = dummy.list_pathogens
