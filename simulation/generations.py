"""Generation simulator for Genesis Twin (Part D, Saket, P2 feature F14).

Question it answers: "If a gene variant is at frequency p today, how might that frequency change across
generations?"  It uses a Wright-Fisher model: each generation, the next population is a random sample of the
current one, so small populations drift more than large ones. Optional selection (the variant helps or hurts)
and mutation (the variant arises or reverts) are added. Many random runs give a 95 percent range.

Main function (for a future endpoint such as POST /genetics/generations):
    simulate_generations(start_freq, population_size, generations, selection=0.0, mutation=0.0, runs=500, seed=0)

All numbers it returns are model output from sample assumptions, not predictions for a real family or person.
Research and education only, not medical advice.
"""
import numpy as np

GEN_MODEL_VERSION = "generation-sim-1.0.0"

LIMITS = {
    "start_freq": (0.0, 1.0),
    "population_size": (2, 100000),   # number of diploid individuals, so 2N gene copies
    "generations": (1, 200),
    "selection": (-0.9, 5.0),         # s: relative advantage of the variant (0 = none, negative = harmful)
    "mutation": (0.0, 0.1),           # chance per copy per generation that the variant flips
    "runs": (10, 2000),
}


def _number(value, name):
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError("%s must be a number." % name)
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError("%s must be a finite number." % name)
    low, high = LIMITS[name]
    if not (low <= x <= high):
        raise ValueError("%s must be between %g and %g (found %g)." % (name, low, high, x))
    return x


def simulate_generations(start_freq, population_size, generations, selection=0.0, mutation=0.0,
                         runs=500, seed=0):
    """Simulate the frequency of one variant over several generations.

    start_freq:      starting frequency of the variant, 0 to 1
    population_size: number of individuals (diploid, so 2 x this many gene copies), 2 to 100000
    generations:     how many generations to simulate, 1 to 200
    selection:       s, the relative advantage of the variant (0 = neutral, -0.1 = 10 percent worse)
    mutation:        chance per gene copy per generation that the variant flips to the other form, 0 to 0.1
    runs:            how many random repeats (more runs give smoother ranges), 10 to 2000
    seed:            random seed, so the same inputs always give the same result

    Returns generations (0..G), mean, low and high (95 percent range across runs), a few example_runs for
    plotting, fixed_fraction (runs where the variant reached 100 percent), lost_fraction (runs where it
    disappeared), the inputs used, the model version and a note. Bad input raises ValueError.
    """
    p0 = _number(start_freq, "start_freq")
    n = int(_number(population_size, "population_size"))
    g = int(_number(generations, "generations"))
    s = _number(selection, "selection")
    mu = _number(mutation, "mutation")
    r = int(_number(runs, "runs"))
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        raise ValueError("seed must be a whole number.")

    copies = 2 * n
    rng = np.random.default_rng(seed)
    freq = np.empty((g + 1, r))
    freq[0] = p0
    p = np.full(r, p0)
    for t in range(1, g + 1):
        p = p * (1.0 + s) / (1.0 + p * s)          # selection
        p = p * (1.0 - mu) + (1.0 - p) * mu         # mutation (both directions, same rate)
        p = np.clip(p, 0.0, 1.0)
        p = rng.binomial(copies, p) / copies        # random sampling of the next generation (drift)
        freq[t] = p

    low = np.percentile(freq, 2.5, axis=1)
    high = np.percentile(freq, 97.5, axis=1)
    mean = freq.mean(axis=1)
    last = freq[-1]
    keep = min(5, r)
    return {
        "model_version": GEN_MODEL_VERSION,
        "inputs": {"start_freq": p0, "population_size": n, "generations": g, "selection": s,
                   "mutation": mu, "runs": r, "seed": seed},
        "generations": list(range(g + 1)),
        "mean": [round(float(v), 4) for v in mean],
        "low": [round(float(v), 4) for v in low],
        "high": [round(float(v), 4) for v in high],
        "example_runs": [[round(float(v), 4) for v in freq[:, i]] for i in range(keep)],
        "fixed_fraction": round(float(np.mean(last >= 1.0)), 4),
        "lost_fraction": round(float(np.mean(last <= 0.0)), 4),
        "note": ("Wright-Fisher sample model. The range is the middle 95 percent of %d random runs. "
                 "Sample assumptions, not a prediction for a real person or family." % r),
        "disclaimer": "Research and education only, not medical advice.",
    }
