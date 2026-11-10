"""Tests for the reliability warnings, the inconclusive verdict and the helpful error messages.
Run:  python -m pytest -q"""
import os

from fitting import fit_pathogen, rate_reliability
from validate_published import validate

HERE = os.path.dirname(os.path.abspath(__file__))


def _csv(name):
    with open(os.path.join(HERE, "real_data", name), encoding="utf-8") as f:
        return f.read()


def test_rate_reliability_rules():
    assert rate_reliability({"value": 4.0, "low": 2.0, "high": 6.0}) == "ok"
    assert rate_reliability({"value": 20.0, "low": 0.0, "high": 90.0}) == "at_limit"
    assert rate_reliability({"value": 0.01, "low": 0.0, "high": 5.0}) == "at_limit"
    assert rate_reliability({"value": 6.8, "low": 0.0, "high": 84.0}) == "wide_range"
    assert rate_reliability({"value": 2.0, "low": None, "high": None}) == "wide_range"


def test_good_fit_has_ok_rates_and_no_limit_warning():
    r = fit_pathogen(_csv("caltech_participant1.csv"))
    assert r["reliability"] == {"growth_rate": "ok", "decay_rate": "ok"}
    assert not any("not a reliable estimate" in w for w in r["warnings"])


def test_edge_fit_gets_a_plain_warning():
    r = fit_pathogen(_csv("caltech_participant3.csv"))
    assert r["reliability"]["growth_rate"] == "at_limit"
    assert any("limit of the fitting range" in w for w in r["warnings"])


def test_bad_file_still_returns_the_usual_keys():
    r = fit_pathogen("day,load\n1,2\n")
    assert r["parameters"] is None and r["validation_errors"] and r["reliability"] == {}


def test_negative_day_message_says_what_to_do():
    r = fit_pathogen("day,load\n-1,5\n0,6\n1,7\n2,8\n3,9\n4,10\n")
    assert any("cannot be negative" in e and "from 0" in e for e in r["validation_errors"])


def test_negative_load_message_says_what_to_do():
    r = fit_pathogen("day,load\n0,-5\n1,6\n2,7\n3,8\n4,9\n5,10\n")
    assert any("cannot be negative" in e and "detection limit" in e for e in r["validation_errors"])


def test_unreliable_series_gives_inconclusive_verdict(tmp_path):
    rep = validate(_csv("caltech_participant3.csv"), "respiratory_virus", "test", outdir=str(tmp_path))
    assert rep["verdict"] == "inconclusive"
    assert rep["growth_rate"]["agrees"] is None and rep["decay_rate"]["agrees"] is None
    assert "inconclusive" in (tmp_path / "validation_report.md").read_text(encoding="utf-8")


def test_reliable_series_keeps_the_normal_verdicts(tmp_path):
    rep = validate(_csv("caltech_participant1.csv"), "respiratory_virus", "test", outdir=str(tmp_path))
    assert rep["verdict"] in ("agrees", "partly agrees", "does not agree")
    assert rep["growth_rate"]["reliable"] and rep["decay_rate"]["reliable"]
