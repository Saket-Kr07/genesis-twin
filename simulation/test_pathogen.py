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


# ---- smooth timeline, treatment start, dose-response, status, band (improvements) ----
import numpy as np

from pathogen import (FINE_T, STEPS_PER_DAY, load_band, simulate_custom_timeline,
                      simulate_timeline)


def test_timeline_has_all_days_and_a_fine_grid():
    tl = simulate_timeline("respiratory_virus", 0.3)
    assert len(tl["times"]) == len(tl["load"]) == len(FINE_T) == DAYS * STEPS_PER_DAY + 1
    assert set(tl["scores"]) == set(ORGAN_IDS)
    assert all(len(v) == len(tl["times"]) for v in tl["scores"].values())
    assert [d["day"] for d in tl["days"]] == list(range(DAYS + 1))


def test_timeline_days_match_single_day_calls():
    tl = simulate_timeline("gut_virus", 0.2, 2)
    for d in (0, 5, 12):
        single = simulate_pathogen("gut_virus", d, 0.2, treatment_start=2)
        assert tl["days"][d]["organs"] == single["organs"]
        assert tl["days"][d]["load"] == single["load"]


def test_smooth_curve_is_smoother_than_the_daily_curve():
    result = simulate_pathogen("respiratory_virus", 0, 0.0)
    daily = np.abs(np.diff([p["load"] for p in result["curve"]])).max()
    smooth = np.abs(np.diff([p["load"] for p in result["curve_smooth"]])).max()
    assert len(result["curve_smooth"]) == len(FINE_T)
    assert smooth < 0.5 * daily


def test_organ_scores_change_gently_between_steps():
    tl = simulate_timeline("respiratory_virus", 0.0)
    assert np.abs(np.diff(tl["scores"]["lungs"])).max() <= 12


def test_treatment_start_leaves_earlier_days_unchanged():
    untreated = simulate_timeline("respiratory_virus", 0.0)["load"]
    late = simulate_timeline("respiratory_virus", 0.8, 5)["load"]
    up_to_day_5 = 5 * STEPS_PER_DAY + 1
    assert np.allclose(untreated[:up_to_day_5], late[:up_to_day_5], atol=1e-3)


def test_late_treatment_helps_less_than_early_treatment():
    def peak(start):
        return max(simulate_timeline("respiratory_virus", 0.8, start)["load"])

    def worst_lungs(start):
        return min(simulate_timeline("respiratory_virus", 0.8, start)["scores"]["lungs"])

    assert peak(0) < peak(2) <= peak(4)
    assert worst_lungs(0) > worst_lungs(3)


def test_dose_response_has_diminishing_returns():
    def peak(t):
        return max(simulate_timeline("respiratory_virus", t)["load"])

    full = peak(0.0) - peak(1.0)
    half = peak(0.0) - peak(0.5)
    assert half > 0.5 * full


def test_status_labels():
    assert all(o["status"] == "healthy" for o in simulate_pathogen("respiratory_virus", 0, 0)["organs"].values())
    assert simulate_pathogen("respiratory_virus", 7, 0)["organs"]["lungs"]["status"] == "critical"
    assert {o["status"] for o in simulate_pathogen("respiratory_virus", 7, 0)["organs"].values()} <= {
        "healthy", "stressed", "critical"}


def test_band_surrounds_the_nominal_curve_and_is_repeatable():
    band = load_band("respiratory_virus", 0.0)
    assert len(band["low"]) == len(band["high"]) == len(band["nominal"]) == len(FINE_T)
    assert all(lo <= hi for lo, hi in zip(band["low"], band["high"]))
    peak_index = int(np.argmax(band["nominal"]))
    assert band["low"][peak_index] <= band["nominal"][peak_index] <= band["high"][peak_index]
    assert band["high"][peak_index] - band["low"][peak_index] > 0.05
    assert load_band("respiratory_virus", 0.0) == band


def test_band_unknown_pathogen_raises():
    with pytest.raises(ValueError):
        load_band("nope")


def test_custom_timeline_and_late_treatment():
    tl = simulate_custom_timeline(PARAMS, ["lungs"], 0.0)
    assert len(tl["times"]) == len(FINE_T) and [d["day"] for d in tl["days"]] == list(range(DAYS + 1))
    early = max(simulate_custom_timeline(PARAMS, ["lungs"], 1.0, 0)["load"])
    after_peak = max(simulate_custom_timeline(PARAMS, ["lungs"], 1.0, 10)["load"])
    assert early < 0.3 and after_peak > 0.95


# ---- body profile: male, female, child, older, height, weight, face-scan baseline ----
from pathogen import clean_profile, describe_profile

ADULT = {"sex": "male", "age": 30, "height_cm": 175, "weight_kg": 70}
CHILD = {"sex": "female", "age": 8, "height_cm": 128, "weight_kg": 26}
OLDER = {"sex": "male", "age": 78, "height_cm": 170, "weight_kg": 72}
OBESE = {"sex": "male", "age": 40, "height_cm": 175, "weight_kg": 115}
UNDERWEIGHT = {"sex": "female", "age": 25, "height_cm": 170, "weight_kg": 48}


def worst(profile, organ="lungs", pid="respiratory_virus"):
    return min(simulate_timeline(pid, 0.0, 0, profile)["scores"][organ])


def day0(profile, organ, vital):
    return simulate_pathogen("respiratory_virus", 0, 0.0, profile=profile)["organs"][organ]["vitals"][vital]


def test_no_profile_is_unchanged_and_the_reference_adult_matches_it():
    plain = simulate_pathogen("respiratory_virus", 7, 0.2)
    assert plain["profile"] is None and plain["profile_effects"] == []
    adult = simulate_pathogen("respiratory_virus", 7, 0.2, profile=ADULT)
    assert adult["organs"]["lungs"]["score"] == plain["organs"]["lungs"]["score"]
    assert adult["organs"]["lungs"]["vitals"] == plain["organs"]["lungs"]["vitals"]


def test_older_body_is_hit_harder():
    assert worst(OLDER) < worst(ADULT)


def test_weaker_immune_response_prolongs_the_infection():
    adult = simulate_timeline("respiratory_virus", 0.0, 0, ADULT)["load"]
    older = simulate_timeline("respiratory_virus", 0.0, 0, OLDER)["load"]
    day = 8 * STEPS_PER_DAY
    assert older[day] > adult[day]


def test_obesity_and_underweight_raise_vulnerability_but_not_for_children():
    assert worst(OBESE) < worst(ADULT)
    assert worst(UNDERWEIGHT, "kidneys") < worst(ADULT, "kidneys")
    assert worst(CHILD) == worst(ADULT)
    effects = simulate_pathogen("respiratory_virus", 5, 0, profile=CHILD)["profile_effects"]
    assert any("under 18" in e for e in effects)


def test_child_resting_values_differ_from_an_adult():
    assert day0(CHILD, "heart", "heart_rate") > day0(ADULT, "heart", "heart_rate")
    assert day0(CHILD, "lungs", "breathing_rate") > day0(ADULT, "lungs", "breathing_rate")
    assert day0(CHILD, "lungs", "lung_capacity") < 0.5 * day0(ADULT, "lungs", "lung_capacity")
    systolic = lambda p: int(day0(p, "heart", "blood_pressure").split("/")[0])
    assert systolic(CHILD) < systolic(ADULT) < systolic(OLDER)


def test_height_sex_and_age_change_baseline_values():
    tall = dict(ADULT, height_cm=190)
    short = dict(ADULT, height_cm=160)
    assert day0(tall, "lungs", "lung_capacity") > day0(short, "lungs", "lung_capacity")
    assert day0(dict(ADULT, sex="female"), "lungs", "lung_capacity") < day0(ADULT, "lungs", "lung_capacity")
    assert day0(OLDER, "kidneys", "egfr") < day0(ADULT, "kidneys", "egfr")


def test_face_scan_baseline_sets_the_resting_value_then_rises_with_damage():
    scan = dict(ADULT, baseline_vitals={"heart_rate": 90, "breathing_rate": 18})
    assert day0(scan, "heart", "heart_rate") == 90
    assert day0(scan, "lungs", "breathing_rate") == 18
    later = simulate_pathogen("respiratory_virus", 7, 0.0, profile=scan)["organs"]["heart"]["vitals"]["heart_rate"]
    assert later > 90
    effects = simulate_pathogen("respiratory_virus", 0, 0.0, profile=scan)["profile_effects"]
    assert any("face scan" in e for e in effects)


def test_missing_profile_fields_use_the_reference_adult():
    assert clean_profile({}) == dict(ADULT, age=30.0, height_cm=175.0, weight_kg=70.0, baseline_vitals={})
    assert clean_profile({"sex": "female"})["age"] == 30.0


@pytest.mark.parametrize("bad", [
    {"sex": "robot"}, {"age": 200}, {"age": -1}, {"height_cm": 10}, {"weight_kg": "heavy"},
    {"height_cm": 100, "weight_kg": 200}, {"baseline_vitals": {"heart_rate": 400}}, "male",
])
def test_bad_profiles_raise_a_plain_error(bad):
    with pytest.raises(ValueError):
        simulate_pathogen("respiratory_virus", 5, 0, profile=bad)


def test_describe_profile_for_the_form():
    info = describe_profile(OLDER)
    assert info["age_group"] == "older" and info["bmi"] == pytest.approx(24.9, abs=0.1)
    assert info["effects"] and describe_profile(CHILD)["age_group"] == "child"
    assert describe_profile(None)["profile"]["sex"] == "male"


def test_profile_works_for_band_custom_and_timeline():
    band = load_band("respiratory_virus", 0.0, profile=OLDER)
    assert len(band["low"]) == len(FINE_T)
    adult = simulate_custom_timeline(PARAMS, ["lungs"], 0.0, profile=ADULT)["load"]
    older = simulate_custom_timeline(PARAMS, ["lungs"], 0.0, profile=OLDER)["load"]
    assert older[12 * STEPS_PER_DAY] > adult[12 * STEPS_PER_DAY]
    tl = simulate_timeline("gut_virus", 0.3, 2, CHILD)
    assert tl["profile"]["age"] == 8.0 and len(tl["days"]) == DAYS + 1
