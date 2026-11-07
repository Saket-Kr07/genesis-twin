"""Tests for the pathogen lab. Run with:  python -m pytest -q"""
import pytest

from pathogen import DAYS, ORGAN_IDS, list_pathogens, simulate_custom, simulate_pathogen

IDS = [p["id"] for p in list_pathogens()]


def test_list_pathogens_matches_the_contract():
    items = list_pathogens()
    assert IDS == ["respiratory_virus", "gut_virus", "bloodstream_bacterium"]
    assert all({"id", "name", "kind", "preset"} <= set(item) for item in items)
    assert all(item["preset"] is True for item in items)


@pytest.mark.parametrize("pid", IDS)
def test_output_matches_the_contract(pid):
    result = simulate_pathogen(pid, 6, 0.3)
    assert {"load", "curve", "organs"} <= set(result)
    assert 0.0 <= result["load"] <= 1.0
    assert len(result["curve"]) == DAYS + 1
    assert all({"day", "load"} == set(point) for point in result["curve"])
    assert set(result["organs"]) == set(ORGAN_IDS)
    for organ in result["organs"].values():
        assert 0 <= organ["score"] <= 100
        assert len(organ["vitals"]) >= 1


def test_vitals_names_follow_the_contract():
    organs = simulate_pathogen("respiratory_virus", 6, 0.0)["organs"]
    assert {"oxygen_saturation", "breathing_rate", "lung_capacity"} == set(organs["lungs"]["vitals"])
    assert {"heart_rate", "blood_pressure", "ejection_fraction"} == set(organs["heart"]["vitals"])
    assert {"alt", "ast", "bilirubin"} == set(organs["liver"]["vitals"])
    assert {"egfr", "creatinine", "hydration"} == set(organs["kidneys"]["vitals"])
    assert {"white_cell_count", "cytokine_level", "pathogen_load"} == set(organs["spleen"]["vitals"])
    assert {"hormone_indicators"} == set(organs["reproductive"]["vitals"])
    assert "/" in organs["heart"]["vitals"]["blood_pressure"]


@pytest.mark.parametrize("pid", IDS)
def test_day_zero_is_healthy(pid):
    organs = simulate_pathogen(pid, 0, 0.0)["organs"]
    assert all(o["score"] >= 99 for o in organs.values())


@pytest.mark.parametrize("pid", IDS)
def test_untreated_peak_is_close_to_one(pid):
    curve = simulate_pathogen(pid, 0, 0.0)["curve"]
    assert 0.9 <= max(p["load"] for p in curve) <= 1.0


@pytest.mark.parametrize("pid", IDS)
def test_treatment_lowers_the_peak_and_the_damage(pid):
    untreated = simulate_pathogen(pid, 8, 0.0)
    treated = simulate_pathogen(pid, 8, 0.8)
    assert max(p["load"] for p in treated["curve"]) < 0.5 * max(p["load"] for p in untreated["curve"])
    assert sum(o["score"] for o in treated["organs"].values()) > sum(o["score"] for o in untreated["organs"].values())


def test_respiratory_virus_hits_lungs_more_than_gut():
    organs = simulate_pathogen("respiratory_virus", 8, 0.0)["organs"]
    assert organs["lungs"]["score"] < organs["intestines"]["score"]


def test_gut_virus_hits_intestines_more_than_lungs():
    organs = simulate_pathogen("gut_virus", 8, 0.0)["organs"]
    assert organs["intestines"]["score"] < organs["lungs"]["score"]


def test_damage_lags_behind_the_load():
    # The organ is worst AFTER the load has peaked, because damage builds up and heals slowly.
    curve = simulate_pathogen("respiratory_virus", 0, 0.0)["curve"]
    peak_day = max(curve, key=lambda p: p["load"])["day"]
    scores = [simulate_pathogen("respiratory_virus", d, 0.0)["organs"]["lungs"]["score"] for d in range(DAYS + 1)]
    assert scores.index(min(scores)) >= peak_day


def test_inputs_are_clamped():
    result = simulate_pathogen("respiratory_virus", 999, 5)
    assert result["day"] == DAYS
    assert result["treatment"] == 1.0


def test_unknown_pathogen_raises():
    with pytest.raises(ValueError):
        simulate_pathogen("not_a_pathogen", 1, 0)


# ---- simulate_custom (for uploaded pathogens) ----
PARAMS = {"growth_rate": {"value": 1.2, "low": 1.1, "high": 1.3}, "decay_rate": 0.6, "peak_day": {"value": 4.0}}


def test_custom_output_matches_the_contract():
    result = simulate_custom(PARAMS, ["lungs"], 6, 0.0)
    assert {"load", "curve", "organs"} <= set(result)
    assert set(result["organs"]) == set(ORGAN_IDS)
    assert max(p["load"] for p in result["curve"]) > 0.9


def test_custom_hits_the_target_organ_hardest():
    organs = simulate_custom(PARAMS, ["lungs"], 8, 0.0)["organs"]
    assert organs["lungs"]["score"] < organs["intestines"]["score"]


def test_custom_treatment_lowers_the_load():
    untreated = max(p["load"] for p in simulate_custom(PARAMS, ["lungs"], 0, 0.0)["curve"])
    treated = max(p["load"] for p in simulate_custom(PARAMS, ["lungs"], 0, 1.0)["curve"])
    assert treated < 0.3 * untreated


def test_custom_without_known_organs_is_systemic():
    result = simulate_custom(PARAMS, [], 8, 0.0)
    assert len({o["score"] for o in result["organs"].values()}) == 1


def test_custom_needs_the_three_parameters():
    with pytest.raises(ValueError):
        simulate_custom({"growth_rate": 1.0}, ["lungs"], 1, 0)
