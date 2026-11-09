"""
Self-check for Part B.   python test_predict.py     (or: python -m pytest ml/test_predict.py)

Contract tests run on the formula fallback and, when models/health_model.joblib exists,
also on the trained model.
"""
import json
import math
import re

try:                                    # works as `ml.test_predict` and as a plain script
    from . import predict as P
    from .age_progression import age_progression
    from .twin_comparison import compare_twins
except ImportError:
    import predict as P
    from age_progression import age_progression
    from twin_comparison import compare_twins

ORGAN_IDS = P.ORGAN_IDS
LABELS = {"measured", "model_predicted", "illustrative"}
BP = re.compile(r"^\d{2,3}/\d{2,3}$")
# (low, high) sanity ranges taken from the contract's scales
RANGES = {"neuro_inflammation_index": (0, 5), "reaction_score": (0, 100), "gut_inflammation": (0, 10),
          "hormone_indicators": (0, 100), "hydration": (0, 100), "oxygen_saturation": (80, 100),
          "ejection_fraction": (20, 80), "lung_capacity": (1, 8), "pathogen_load": (0, 0)}


def with_formula_fallback(fn):
    """Run a test with the trained model disabled."""
    def run():
        orig = P._load_bundle
        P._load_bundle = lambda: None
        try:
            fn()
        finally:
            P._load_bundle = orig
    run.__name__ = fn.__name__ + "_formula"
    return run


# ------------------------------------------------ existing tests (detailed output)
def test_detailed_structure_and_labels():
    r = P.predict_health_detailed(40, "male", 7, 150, "never", 4)
    assert list(r["organs"]) == ORGAN_IDS, "organ IDs/order changed!"
    assert 0 <= r["overall_health"]["score"] <= 100
    for organ, o in r["organs"].items():
        assert 0 <= o["score"] <= 100, organ
        assert o["score_label"] in LABELS, organ
        for v in {**o["vitals"], **o.get("extra_vitals", {})}.values():
            assert v["label"] in LABELS, organ
    assert r["disclaimer"]


def test_detailed_lifestyle_ordering():
    good = P.predict_health_detailed(40, "male", 8, 200, "never", 5)["overall_health"]["score"]
    bad = P.predict_health_detailed(40, "male", 5, 0, "current", 1)["overall_health"]["score"]
    assert good > bad, "healthy lifestyle should score higher"


def test_detailed_input_validation():
    for bad in [dict(age=10), dict(sex="x"), dict(sleep=30), dict(exercise=-1), dict(diet=9), dict(smoking="sometimes")]:
        args = dict(age=40, sex="male", sleep=7, exercise=100, smoking="never", diet=3)
        args.update(bad)
        try:
            P.predict_health_detailed(**args)
        except ValueError:
            continue
        raise AssertionError(f"{bad} should be rejected")


def test_age_progression():
    tl = age_progression("female", 7.5, 150, "never", 3)["timeline"]
    assert tl[0]["age"] == 20 and tl[-1]["age"] == 80
    assert tl[0]["overall"] > tl[-1]["overall"], "health should decline with age"


def test_twin_comparison():
    c = compare_twins(dict(age=40, sex="male", sleep=5, exercise=0, smoking="current", diet=1),
                      dict(age=40, sex="male", sleep=8, exercise=200, smoking="never", diet=5))
    assert c["overall"]["difference"] > 0


# ------------------------------------------------ contract v1.1 tests (strict output)
def check_contract_output(out):
    assert list(out) == ORGAN_IDS, "top level must be exactly the 12 organ ids, in order"
    for organ, o in out.items():
        assert set(o) == {"score", "vitals"}, f"{organ}: only score and vitals allowed"
        assert type(o["score"]) is int and 0 <= o["score"] <= 100, f"{organ}: score must be an int 0-100"
        assert tuple(o["vitals"]) == P.CONTRACT_VITALS[organ], f"{organ}: vital names must match the contract"
        for name, v in o["vitals"].items():
            if name == "blood_pressure":
                assert isinstance(v, str) and BP.match(v), f"blood_pressure must look like '120/80', got {v!r}"
                sys_, dia = map(int, v.split("/"))
                assert sys_ > dia
            else:
                assert type(v) in (int, float) and math.isfinite(v), f"{organ}.{name} must be a plain number, got {v!r}"
                if name in RANGES:
                    lo, hi = RANGES[name]
                    assert lo <= v <= hi, f"{organ}.{name}={v} outside {lo}-{hi}"
                else:
                    assert v >= 0, f"{organ}.{name} negative"
    assert out["liver"]["vitals"].keys() == {"alt", "ast", "bilirubin"}
    for organ in ("stomach", "intestines", "pancreas"):
        assert set(out[organ]["vitals"]) == {"gut_inflammation"}
    assert out["spleen"]["vitals"]["pathogen_load"] == 0.0
    assert out["kidneys"]["vitals"] == out["bladder"]["vitals"]
    json.dumps(out)                                   # must be JSON-serialisable


def contract_suite():
    for args in [(40, "male", 7, 3, 0, 3), (20, "female", 9, 7, 0, 5), (80, "male", 4, 0, 100, 1),
                 (55, "female", 6.5, 2, 12, 2)]:
        check_contract_output(P.predict_health(*args))


def input_validation_suite():
    ok = dict(age=40, sex="male", sleep=7, exercise=3, smoking=0, diet=3)
    P.predict_health(**ok)
    for edge in [dict(age=20), dict(age=80), dict(exercise=0), dict(exercise=7), dict(smoking=100),
                 dict(diet=1), dict(diet=5), dict(sleep=0), dict(sleep=24), dict(sex="female"), dict(sex="Male")]:
        P.predict_health(**{**ok, **edge})            # boundaries are valid
    invalid = [dict(age=19), dict(age=81), dict(age=40.5), dict(age=True), dict(age="40"), dict(age=None),
               dict(sex="other"), dict(sex=None), dict(sex=1),
               dict(sleep=-0.5), dict(sleep=24.5), dict(sleep=float("nan")), dict(sleep="7"), dict(sleep=True),
               dict(exercise=-1), dict(exercise=8), dict(exercise=2.5), dict(exercise=True),
               dict(smoking=-1), dict(smoking=101), dict(smoking=1.5), dict(smoking="never"), dict(smoking=True),
               dict(diet=0), dict(diet=6), dict(diet=3.5), dict(diet=False)]
    for bad in invalid:
        try:
            P.predict_health(**{**ok, **bad})
        except ValueError:
            continue
        raise AssertionError(f"{bad} must raise ValueError (no clamping)")


def direction_suite():
    s = lambda **k: P.predict_health(**{**dict(age=40, sex="male", sleep=7.5, exercise=3, smoking=0, diet=3), **k})
    tot = lambda out: sum(o["score"] for o in out.values())
    assert tot(s(diet=5)) > tot(s(diet=1)), "diet 5 must be healthier than diet 1"
    assert tot(s(exercise=6)) > tot(s(exercise=0)), "more exercise days must be healthier"
    assert tot(s(smoking=0)) > tot(s(smoking=10)) >= tot(s(smoking=40)), "more cigarettes must not be healthier"
    assert s(smoking=0)["lungs"]["score"] > s(smoking=10)["lungs"]["score"] > s(smoking=40)["lungs"]["score"]
    assert s(sleep=7.5)["brain"]["score"] > s(sleep=3)["brain"]["score"]
    assert tot(s(age=20)) > tot(s(age=80)), "older twin should score lower"
    assert s(sex="female")["lungs"]["vitals"]["lung_capacity"] < s(sex="male")["lungs"]["vitals"]["lung_capacity"]
    assert s(age=80)["lungs"]["vitals"]["lung_capacity"] < s(age=30)["lungs"]["vitals"]["lung_capacity"]


def consistency_suite():
    strict = P.predict_health(45, "female", 6.5, 4, 5, 4)
    det = P.predict_health_detailed(45, "female", 6.5, 4 * P.MINUTES_PER_EXERCISE_DAY, 5, 4)
    for o in ORGAN_IDS:
        assert strict[o]["score"] == int(math.floor(det["organs"][o]["score"] + 0.5)), o
        for k, v in strict[o]["vitals"].items():
            assert det["organs"][o]["vitals"][k]["value"] == v, (o, k)
    assert strict["lungs"]["score"] == P.predict_health(45, "female", 6.5, 4, 5, 4)["lungs"]["score"]   # deterministic



PROFILES = [dict(age=25, sex="female", sleep=8, exercise=5, diet=3), dict(age=40, sex="male", sleep=7.5, exercise=3, diet=3),
            dict(age=65, sex="male", sleep=6.5, exercise=2, diet=3), dict(age=50, sex="female", sleep=7, exercise=4, diet=4)]
GRID = [0, 1, 5, 10, 20, 30, 40, 60, 100]


def smoking_dose_suite():
    """More cigarettes per day must give progressively worse heart, lungs and reproductive scores."""
    for prof in PROFILES:
        by_c = {c: P.predict_health(smoking=c, **prof) for c in GRID}
        for organ in ("heart", "lungs", "reproductive"):
            scores = [by_c[c][organ]["score"] for c in GRID]
            assert scores == sorted(scores, reverse=True), f"{organ} must not improve with more cigarettes: {scores} {prof}"
            assert by_c[0][organ]["score"] > by_c[10][organ]["score"] > by_c[40][organ]["score"], \
                f"{organ}: expected score(0) > score(10) > score(40), got " \
                f"{[by_c[c][organ]['score'] for c in (0, 10, 40)]} for {prof}"
            assert by_c[1][organ]["score"] < by_c[0][organ]["score"], f"{organ}: 1/day must score below 0/day"
            assert by_c[100][organ]["score"] < by_c[40][organ]["score"], f"{organ}: 100/day must score below 40/day"
        # contract output stays valid at every dose
        for out in by_c.values():
            check_contract_output(out)
        # heart_rate and blood_pressure stay as predicted (not dose-adjusted); ejection_fraction is an
        # illustrative vital derived from the heart score, so it may only fall as the dose rises
        for k in ("heart_rate", "blood_pressure"):
            assert by_c[10]["heart"]["vitals"][k] == by_c[40]["heart"]["vitals"][k], k
        efs = [by_c[c]["heart"]["vitals"]["ejection_fraction"] for c in GRID]
        assert efs == sorted(efs, reverse=True), efs
        # liver, kidneys, pancreas are not dose-adjusted
        for organ in ("liver", "kidneys", "pancreas"):
            assert by_c[10][organ] == by_c[40][organ], f"{organ} must not depend on smoking quantity"


def smoking_dose_documentation_suite():
    base = dict(age=40, sex="male", sleep=7.5, exercise=150, diet=3)
    smoker = P.predict_health_detailed(smoking=20, **base)["organs"]["heart"]
    never = P.predict_health_detailed(smoking=0, **base)["organs"]["heart"]
    assert smoker["score_label"] == "illustrative" and "adjustments" in smoker and "smoking-dose" in smoker["note"]
    assert smoker["adjustments"]["smoking_dose_penalty"] < 0
    assert "adjustments" not in never                              # no adjustment for non-smokers
    assert P.HEART_SMOKING_MAX_PENALTY > 0


def pathogen_load_suite():
    """Part D agreement: relative scale, 1.0 = untreated reference-adult peak, 0.0 = healthy body."""
    for args in [(40, "male", 7, 3, 0, 3), (80, "female", 4, 0, 100, 1), (20, "male", 9, 7, 0, 5)]:
        v = P.predict_health(*args)["spleen"]["vitals"]["pathogen_load"]
        assert v == 0.0 and isinstance(v, float), "healthy-body pathogen_load must be the float 0.0"
        assert round(v, 2) == v                                    # two-decimal display
    d = P.predict_health_detailed(40, "male", 7, 90, "never", 3)["organs"]["spleen"]["vitals"]["pathogen_load"]
    assert d["value"] == 0.0
    assert "relative" in d["unit"] and "1.0" in d["unit"] and "reference-adult" in d["unit"]
    assert "0.0" in d["note"] and "pending" not in (d["note"] + d["unit"]).lower()
    assert "copies" not in (d["note"] + d["unit"]).lower()


def test_contract_output_formula():       with_formula_fallback(contract_suite)()
def test_validation_formula():            with_formula_fallback(input_validation_suite)()
def test_directions_formula():            with_formula_fallback(direction_suite)()
def test_consistency_formula():           with_formula_fallback(consistency_suite)()
def test_smoking_dose_formula():          with_formula_fallback(smoking_dose_suite)()
def test_smoking_dose_docs_formula():     with_formula_fallback(smoking_dose_documentation_suite)()
def test_pathogen_load_formula():         with_formula_fallback(pathogen_load_suite)()


def test_trained_model_if_present():
    if not P.MODEL_PATH.exists():
        print("  (skipped: no trained model at", P.MODEL_PATH, ")")
        return
    assert P._load_bundle() is not None, "model file exists but could not be used"
    assert P.predict_health_detailed(40, "male", 7, 150, "never", 3)["model_info"]["mode"] == "ml_model"
    contract_suite(); input_validation_suite(); direction_suite(); consistency_suite()
    smoking_dose_suite(); smoking_dose_documentation_suite(); pathogen_load_suite()


def main():
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    mode = "ml_model" if P.MODEL_PATH.exists() and P._load_bundle() else "formula_baseline"
    print(f"All {len(tests)} test groups passed. Active mode: {mode}")


if __name__ == "__main__":
    main()
