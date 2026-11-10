"""
Simulate how one twin's health profile changes from age 20 to 80
(lifestyle held constant - only age changes).

    python age_progression.py --sex male --sleep 6 --exercise 30 --smoking current --diet 2
    python age_progression.py --sex female --sleep 8 --exercise 200 --smoking never --diet 5 --plot out.png --csv out.csv
"""
import argparse
import csv
import json
try:                                   # works as `ml.age_progression` and as a plain script
    from .predict import predict_health_detailed, ORGAN_IDS
except ImportError:
    from predict import predict_health_detailed, ORGAN_IDS


def _all_vitals(organ: dict) -> dict:
    return {**organ["vitals"], **organ.get("extra_vitals", {})}


def age_progression(sex, sleep, exercise, smoking, diet, start_age=20, end_age=80, step=5) -> dict:
    timeline = []
    for age in range(start_age, end_age + 1, step):
        r = predict_health_detailed(age, sex, sleep, exercise, smoking, diet)
        timeline.append({
            "age": age,
            "overall": r["overall_health"]["score"],
            "organs": {o: r["organs"][o]["score"] for o in ORGAN_IDS},
            "vitals": {f"{o}.{k}": v["value"] for o in ORGAN_IDS
                       for k, v in _all_vitals(r["organs"][o]).items()},
            "labels": {o: r["organs"][o]["score_label"] for o in ORGAN_IDS},
        })
    return {"profile": dict(sex=sex, sleep=sleep, exercise=exercise, smoking=smoking, diet=diet),
            "model_mode": r["model_info"]["mode"],
            "note": "Simulation: lifestyle is held constant and only age changes. Not a forecast of a real person.",
            "timeline": timeline}


def print_table(result: dict) -> None:
    print(f"Mode: {result['model_mode']}   Profile: {result['profile']}")
    print("age  overall  " + " ".join(f"{o[:6]:>6}" for o in ORGAN_IDS))
    for t in result["timeline"]:
        print(f"{t['age']:3d}  {t['overall']:7.1f}  " + " ".join(f"{t['organs'][o]:6.1f}" for o in ORGAN_IDS))


def save_csv(result: dict, path: str) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["age", "overall"] + ORGAN_IDS)
        for t in result["timeline"]:
            w.writerow([t["age"], t["overall"]] + [t["organs"][o] for o in ORGAN_IDS])


def save_plot(result: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ages = [t["age"] for t in result["timeline"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    for o in ORGAN_IDS:
        ax.plot(ages, [t["organs"][o] for t in result["timeline"]], lw=1, alpha=0.7, label=o)
    ax.plot(ages, [t["overall"] for t in result["timeline"]], "k-", lw=3, label="OVERALL")
    ax.set(xlabel="Age", ylabel="Health score (0-100)", ylim=(0, 105),
           title="Simulated health profile, age 20-80 (illustrative)")
    ax.legend(ncol=3, fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sex", default="female")
    p.add_argument("--sleep", type=float, default=7.5)
    p.add_argument("--exercise", type=float, default=150)
    p.add_argument("--smoking", default="never")
    p.add_argument("--diet", type=float, default=3)
    p.add_argument("--step", type=int, default=5)
    p.add_argument("--json"), p.add_argument("--csv"), p.add_argument("--plot")
    a = p.parse_args()
    res = age_progression(a.sex, a.sleep, a.exercise, a.smoking, a.diet, step=a.step)
    print_table(res)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=2)
    if a.csv:
        save_csv(res, a.csv)
    if a.plot:
        save_plot(res, a.plot)
