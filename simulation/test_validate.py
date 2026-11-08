"""Tests for validate_published.py. The data here is SYNTHETIC and only checks that the script works."""
import json
import os

import numpy as np
import pytest

from fitting import fit_pathogen
from validate_published import _preset_csv, main, validate


def curve_csv(growth, decay, peak_day, peak_load=6.0, days=range(0, 21), noise=0.02, seed=5, log10=False, day_shift=0):
    rng = np.random.default_rng(seed)
    out = ["day,load"]
    for d in days:
        t = d + day_shift
        value = 2 * peak_load / (np.exp(-growth * (t - peak_day)) + np.exp(decay * (t - peak_day)))
        value = max(value * (1 + rng.normal(0, noise)), 1e-6)
        out.append("%g,%.5f" % (d, np.log10(value) if log10 else value))
    return "\n".join(out)


def preset_like(pid="respiratory_virus", **kw):
    p = fit_pathogen(_preset_csv(pid))["parameters"]
    return curve_csv(p["growth_rate"]["value"], p["decay_rate"]["value"], p["peak_day"]["value"], **kw)


def test_data_shaped_like_the_preset_agrees(tmp_path):
    report = validate(preset_like(), "respiratory_virus", "synthetic test data", outdir=str(tmp_path))
    assert report["ok"] and report["verdict"] == "agrees"
    for name in ("validation.png", "validation_report.json", "validation_report.md"):
        assert (tmp_path / name).exists()


def test_a_day_zero_shift_does_not_change_the_rates(tmp_path):
    report = validate(preset_like(day_shift=2), "respiratory_virus", "synthetic test data", outdir=str(tmp_path))
    assert report["growth_rate"]["agrees"] and report["decay_rate"]["agrees"]
    assert abs(report["shape"]["best_offset_days"]) > 0.5


def test_very_different_data_does_not_agree_and_gives_advice(tmp_path):
    report = validate(curve_csv(0.5, 0.15, 9, days=range(0, 41, 2)), "respiratory_virus", "synthetic test data",
                      outdir=str(tmp_path))
    assert report["verdict"] in ("does not agree", "partly agrees")
    assert not report["growth_rate"]["agrees"]
    assert report["advice"]


def test_log10_data_is_converted(tmp_path):
    plain = validate(preset_like(), "respiratory_virus", "synthetic", outdir=str(tmp_path / "a"))
    logged = validate(preset_like(log10=True), "respiratory_virus", "synthetic", log10=True, outdir=str(tmp_path / "b"))
    assert logged["ok"]
    assert logged["growth_rate"]["published"]["value"] == pytest.approx(plain["growth_rate"]["published"]["value"], rel=0.25)


def test_bad_file_returns_plain_errors(tmp_path):
    report = validate("day,load\n0,1\n1,-2", "gut_virus", "synthetic", outdir=str(tmp_path))
    assert report["ok"] is False and report["validation_errors"]


def test_a_citation_is_required_and_pathogen_must_exist(tmp_path):
    with pytest.raises(ValueError):
        validate(preset_like(), "respiratory_virus", "  ", outdir=str(tmp_path))
    with pytest.raises(ValueError):
        validate(preset_like(), "nope", "synthetic", outdir=str(tmp_path))


def test_command_line_runs(tmp_path, capsys):
    csv_path = tmp_path / "data.csv"
    csv_path.write_text(preset_like())
    code = main(["--csv", str(csv_path), "--label", "synthetic test data", "--out", str(tmp_path / "out")])
    assert code == 0 and "Verdict" in capsys.readouterr().out
    assert json.load(open(tmp_path / "out" / "validation_report.json"))["label"] == "synthetic test data"
