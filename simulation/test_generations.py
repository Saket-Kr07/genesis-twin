"""Tests for generations.py. Run:  python -m pytest -q"""
import pytest

from generations import simulate_generations


def test_output_shape():
    r = simulate_generations(0.2, 50, 20, runs=100)
    for key in ("generations", "mean", "low", "high", "example_runs", "fixed_fraction", "lost_fraction",
                "model_version", "inputs", "note", "disclaimer"):
        assert key in r
    assert r["generations"] == list(range(21))
    assert len(r["mean"]) == len(r["low"]) == len(r["high"]) == 21
    assert len(r["example_runs"]) == 5 and len(r["example_runs"][0]) == 21


def test_starts_at_start_freq():
    r = simulate_generations(0.3, 100, 10, runs=50)
    assert r["mean"][0] == r["low"][0] == r["high"][0] == 0.3


def test_values_stay_between_0_and_1_and_ordered():
    r = simulate_generations(0.5, 30, 50, selection=0.2, mutation=0.01, runs=200)
    for lo, m, hi in zip(r["low"], r["mean"], r["high"]):
        assert 0 <= lo <= hi <= 1
        assert lo <= m <= hi + 1e-9


def test_same_seed_same_result_and_different_seed_differs():
    a = simulate_generations(0.4, 40, 30, runs=100, seed=7)
    b = simulate_generations(0.4, 40, 30, runs=100, seed=7)
    c = simulate_generations(0.4, 40, 30, runs=100, seed=8)
    assert a == b
    assert a["example_runs"] != c["example_runs"]


def test_small_population_drifts_more_than_large():
    small = simulate_generations(0.5, 20, 40, runs=300, seed=1)
    large = simulate_generations(0.5, 5000, 40, runs=300, seed=1)
    spread_small = small["high"][-1] - small["low"][-1]
    spread_large = large["high"][-1] - large["low"][-1]
    assert spread_small > spread_large


def test_selection_changes_the_mean_in_the_right_direction():
    good = simulate_generations(0.2, 2000, 40, selection=0.1, runs=200, seed=2)
    bad = simulate_generations(0.2, 2000, 40, selection=-0.1, runs=200, seed=2)
    assert good["mean"][-1] > 0.2 > bad["mean"][-1]


def test_neutral_fixation_chance_is_about_the_start_frequency():
    r = simulate_generations(0.3, 10, 200, runs=2000, seed=3)
    assert abs(r["fixed_fraction"] - 0.3) < 0.05
    assert abs(r["fixed_fraction"] + r["lost_fraction"] - 1.0) < 0.01   # nearly all runs end fixed or lost


def test_mutation_keeps_the_variant_from_being_lost_in_a_big_population():
    r = simulate_generations(0.0, 10000, 30, mutation=0.01, runs=100, seed=4)
    assert r["mean"][-1] > 0.05


@pytest.mark.parametrize("kwargs", [
    dict(start_freq=-0.1, population_size=50, generations=10),
    dict(start_freq=1.5, population_size=50, generations=10),
    dict(start_freq=0.5, population_size=1, generations=10),
    dict(start_freq=0.5, population_size=50, generations=0),
    dict(start_freq=0.5, population_size=50, generations=500),
    dict(start_freq=0.5, population_size=50, generations=10, selection=-1.5),
    dict(start_freq=0.5, population_size=50, generations=10, mutation=0.5),
    dict(start_freq=0.5, population_size=50, generations=10, runs=1),
    dict(start_freq="abc", population_size=50, generations=10),
])
def test_bad_input_gives_a_plain_error(kwargs):
    with pytest.raises(ValueError):
        simulate_generations(**kwargs)
