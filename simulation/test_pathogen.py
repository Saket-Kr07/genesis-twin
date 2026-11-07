"""Tests for the pathogen lab. Run with:  python -m pytest -q"""
import pytest

from pathogen import DAYS, ORGAN_IDS, list_pathogens, simulate_pathogen

IDS = [p["id"] for p in list_pathogens()]


def test_list_pathogens_has_three_presets():
    items = list_pathogens()
    assert len(items) == 3
    assert all({"id", "name", "kind"} <= set(item) for item in items)


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
        assert len(organ["vitals"]) >= 2


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
    organs = simulate_pathogen("virus_a", 8, 0.0)["organs"]
    assert organs["lungs"]["score"] < organs["intestines"]["score"]


def test_gut_virus_hits_intestines_more_than_lungs():
    organs = simulate_pathogen("virus_b", 8, 0.0)["organs"]
    assert organs["intestines"]["score"] < organs["lungs"]["score"]


def test_damage_lags_behind_the_load():
    # The organ is worst AFTER the load has peaked, because damage builds up and heals slowly.
    curve = simulate_pathogen("virus_a", 0, 0.0)["curve"]
    peak_day = max(curve, key=lambda p: p["load"])["day"]
    scores = [simulate_pathogen("virus_a", d, 0.0)["organs"]["lungs"]["score"] for d in range(DAYS + 1)]
    worst_day = scores.index(min(scores))
    assert worst_day >= peak_day


def test_inputs_are_clamped():
    result = simulate_pathogen("virus_a", 999, 5)
    assert result["day"] == DAYS
    assert result["treatment"] == 1.0


def test_unknown_pathogen_raises():
    with pytest.raises(ValueError):
        simulate_pathogen("not_a_pathogen", 1, 0)
