"""One place where the API gets predict_health, simulate_pathogen, simulate_timeline,
fit_pathogen, list_pathogens and get_sources. For each function we try the teammate's
real module; if it cannot be imported, we use the dummy from dummy.py.
Check which is live: GET /health/functions. The reason for any fallback is printed in
the server terminal as a warning.

The input and output shapes must match api-contract.md."""
import importlib
import logging
import sys
from pathlib import Path

from . import dummy

log = logging.getLogger("genesis.functions")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Files in simulation/ may import each other without a package prefix (import tropism).
_SIM_DIR = _REPO_ROOT / "simulation"
if str(_SIM_DIR) not in sys.path:
    sys.path.append(str(_SIM_DIR))

CANDIDATES = {
    "predict_health": [("ml.predict", "predict_health")],
    "simulate_pathogen": [("simulation.pathogen", "simulate_pathogen"), ("pathogen", "simulate_pathogen")],
    "simulate_timeline": [("simulation.pathogen", "simulate_timeline"), ("pathogen", "simulate_timeline")],
    "list_pathogens": [("simulation.pathogen", "list_pathogens"), ("pathogen", "list_pathogens")],
    "fit_pathogen": [("simulation.fitting", "fit_pathogen"), ("fitting", "fit_pathogen")],
    "get_sources": [("research.sources", "get_sources")],
}

SOURCE = {}  # function name -> "real:module.attr" or "dummy"


def _missing(name):
    def stub(*args, **kwargs):
        raise RuntimeError(f"{name} is not available yet.")

    return stub


def _resolve(name: str):
    for module_name, attr in CANDIDATES[name]:
        try:
            fn = getattr(importlib.import_module(module_name), attr)
        except Exception as err:  # ImportError, AttributeError, or an error inside the module
            log.warning("%s: could not load %s.%s (%s: %s)", name, module_name, attr, type(err).__name__, err)
            continue
        SOURCE[name] = f"real:{module_name}.{attr}"
        log.info("%s -> %s", name, SOURCE[name])
        return fn
    SOURCE[name] = "dummy"
    log.warning("%s -> dummy (no real function found)", name)
    return getattr(dummy, name, None) or _missing(name)


predict_health = _resolve("predict_health")
fit_pathogen = _resolve("fit_pathogen")
_simulate = _resolve("simulate_pathogen")
_timeline = _resolve("simulate_timeline")
_list = _resolve("list_pathogens")
_sources = _resolve("get_sources")


def simulate_pathogen(pathogen_id, day, treatment, treatment_start=0, profile=None):
    if SOURCE["simulate_pathogen"] == "dummy":
        return _simulate(pathogen_id, day, treatment)
    return _simulate(pathogen_id, day, treatment, treatment_start, profile)


def simulate_timeline(pathogen_id, treatment, treatment_start=0, profile=None):
    if SOURCE["simulate_timeline"] == "dummy":
        return _timeline(pathogen_id, treatment)
    return _timeline(pathogen_id, treatment, treatment_start, profile)


def list_pathogens(include_all=False):
    if SOURCE["list_pathogens"] == "dummy":
        return _list(include_all=include_all)
    return _list()


def _items(result):
    """The list of pathogens, whether the real function returns a list or a dict."""
    if isinstance(result, dict):
        for key in ("pathogens", "items", "presets"):
            if isinstance(result.get(key), list):
                return result[key]
        return []
    return result or []


def get_pathogen(pathogen_id):
    """Info about one pathogen (with a 'preset' flag), or None if the id is unknown."""
    if SOURCE["list_pathogens"] == "dummy":
        return dummy.get_pathogen(pathogen_id)
    for p in _items(_list()):
        if isinstance(p, dict) and pathogen_id in (p.get("id"), p.get("pathogen_id")):
            info = dict(p)
            info.setdefault("preset", True)
            return info
    return None


def get_sources(limit=None):
    try:
        items = _sources(limit) if limit else _sources()
    except TypeError:  # the real get_sources takes no limit argument
        items = _sources()
    if limit and isinstance(items, list):
        items = items[:limit]
    return items


# Not provided by other parts: this stays on the dummy library for now.
get_body = dummy.get_body
