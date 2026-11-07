"""Tests for CSV validation and fitting. Run with:  python -m pytest -q"""
import numpy as np

from fitting import fit_pathogen


def make_csv(days=range(0, 15), peak_load=7.5, peak_day=4.0, growth=1.2, decay=0.6,
             noise=0.03, tissue=None, seed=3):
    rng = np.random.default_rng(seed)
    days = np.array(list(days), dtype=float)
    true = 2 * peak_load / (np.exp(-growth * (days - peak_day)) + np.exp(decay * (days - peak_day)))
    noisy = true * (1 + rng.normal(0, noise, len(days)))
    header = "day,load" + (",tissue" if tissue else "")
    rows = ["%g,%.4f%s" % (d, v, ("," + tissue) if tissue else "") for d, v in zip(days, noisy)]
    return "\n".join([header] + rows)


def test_good_file_returns_parameters_in_the_contract_shape():
    result = fit_pathogen(make_csv())
    assert result["validation_errors"] == []
    for name in ("growth_rate", "decay_rate", "peak_day", "peak_load"):
        p = result["parameters"][name]
        assert {"value", "low", "high"} == set(p)
        assert p["low"] <= p["value"] <= p["high"]


def test_fit_recovers_the_true_values():
    p = fit_pathogen(make_csv())["parameters"]
    assert abs(p["growth_rate"]["value"] - 1.2) < 0.2
    assert abs(p["decay_rate"]["value"] - 0.6) < 0.1
    assert abs(p["peak_day"]["value"] - 4.0) < 0.5
    assert abs(p["peak_load"]["value"] - 7.5) < 1.0
    assert fit_pathogen(make_csv())["fit"]["r_squared"] > 0.95


def test_bytes_and_semicolons_are_accepted():
    text = make_csv().replace(",", ";")
    assert fit_pathogen(text.encode("utf-8"))["parameters"] is not None


def test_tissue_column_maps_to_organs():
    result = fit_pathogen(make_csv(tissue="lung"))
    assert result["target_organs"] == ["lungs"]
    assert result["unrecognised_tissues"] == []
    result = fit_pathogen(make_csv(tissue="elbow"))
    assert result["target_organs"] == []
    assert result["unrecognised_tissues"] == ["elbow"]


def test_empty_file():
    result = fit_pathogen("")
    assert result["parameters"] is None
    assert result["validation_errors"] == ["The file is empty."]


def test_missing_column():
    result = fit_pathogen("day,count\n1,2\n2,3\n3,4\n4,5\n5,6")
    assert result["parameters"] is None
    assert "load" in result["validation_errors"][0]


def test_too_few_points():
    result = fit_pathogen("day,load\n0,1\n1,3\n2,2")
    assert result["parameters"] is None
    assert any("At least 5" in e for e in result["validation_errors"])


def test_negative_missing_and_text_values_get_row_numbers():
    text = "day,load\n0,1\n1,-3\n2,\n3,abc\n4,2\n5,1\n6,1"
    errors = fit_pathogen(text)["validation_errors"]
    assert any("Row 3" in e and "negative" in e for e in errors)
    assert any("Row 4" in e and "missing" in e for e in errors)
    assert any("Row 5" in e and "abc" in e for e in errors)


def test_duplicate_days():
    text = "day,load\n0,1\n1,3\n1,4\n2,2\n3,1\n4,1"
    errors = fit_pathogen(text)["validation_errors"]
    assert any("Day 1 appears more than once" in e for e in errors)


def test_all_zero_and_flat_loads():
    assert any("zero" in e for e in fit_pathogen("day,load\n0,0\n1,0\n2,0\n3,0\n4,0")["validation_errors"])
    assert any("same" in e for e in fit_pathogen("day,load\n0,2\n1,2\n2,2\n3,2\n4,2")["validation_errors"])


def test_few_points_give_a_warning():
    result = fit_pathogen(make_csv(days=[0, 2, 4, 6, 9, 12], noise=0.02))
    assert result["parameters"] is not None
    assert any("time points" in w for w in result["warnings"])


def test_rise_only_data_gives_a_warning():
    text = "day,load\n0,1\n1,2\n2,4\n3,8\n4,16\n5,32"
    result = fit_pathogen(text)
    assert any("first or last" in w for w in result["warnings"]) or result["parameters"] is None
