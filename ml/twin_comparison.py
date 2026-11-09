"""
Compare two twins (health profiles): overall score, 12 organ scores, shared vitals.

    python twin_comparison.py \
      --a '{"age":40,"sex":"male","sleep":6,"exercise":30,"smoking":"current","diet":2}' \
      --b '{"age":40,"sex":"male","sleep":8,"exercise":200,"smoking":"never","diet":5}'
"""
import argparse
import json
from predict import predict_health, ORGAN_IDS

KEYS = ("age", "sex", "sleep", "exercise", "smoking", "diet")


def compare_twins(profile_a: dict, profile_b: dict, name_a="Twin A", name_b="Twin B") -> dict:
    ra = predict_health(**{k: profile_a[k] for k in KEYS})
    rb = predict_health(**{k: profile_b[k] for k in KEYS})

    def row(a, b):
        d = round(b - a, 1)
        return {name_a: a, name_b: b, "difference": d,
                "better": name_b if d > 0 else name_a if d < 0 else "tie"}

    organs = {o: row(ra["organs"][o]["score"], rb["organs"][o]["score"]) for o in ORGAN_IDS}
    vitals = {}
    for o in ORGAN_IDS:
        for k, va in ra["organs"][o]["vitals"].items():
            vb = rb["organs"][o]["vitals"].get(k)
            if vb and isinstance(va["value"], (int, float)) and isinstance(vb["value"], (int, float)):
                vitals[f"{o}.{k}"] = {name_a: va["value"], name_b: vb["value"],
                                      "difference": round(vb["value"] - va["value"], 2),
                                      "unit": va["unit"], "label": va["label"]}
    top = sorted(organs, key=lambda o: abs(organs[o]["difference"]), reverse=True)[:3]
    return {
        "profiles": {name_a: profile_a, name_b: profile_b},
        "overall": row(ra["overall_health"]["score"], rb["overall_health"]["score"]),
        "organs": organs,
        "vitals": vitals,
        "biggest_organ_differences": top,
        "model_mode": ra["model_info"]["mode"],
        "disclaimer": ra["disclaimer"],
    }


def print_report(c: dict) -> None:
    names = list(c["profiles"])
    na, nb = names
    print(f"Mode: {c['model_mode']}")
    print(f"{'':14s}{na:>10s}{nb:>10s}{'diff':>9s}")
    o = c["overall"]
    print(f"{'OVERALL':14s}{o[na]:10.1f}{o[nb]:10.1f}{o['difference']:+9.1f}")
    for organ, r in c["organs"].items():
        print(f"{organ:14s}{r[na]:10.1f}{r[nb]:10.1f}{r['difference']:+9.1f}")
    print("\nBiggest organ differences:", ", ".join(c["biggest_organ_differences"]))
    print("\nVitals:")
    for k, r in c["vitals"].items():
        print(f"  {k:28s}{r[na]:9.1f}{r[nb]:9.1f}{r['difference']:+9.1f} {r['unit']}  [{r['label']}]")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--a", default='{"age":40,"sex":"male","sleep":6,"exercise":30,"smoking":"current","diet":2}')
    p.add_argument("--b", default='{"age":40,"sex":"male","sleep":8,"exercise":200,"smoking":"never","diet":5}')
    p.add_argument("--json", help="save full comparison to this file")
    a = p.parse_args()
    result = compare_twins(json.loads(a.a), json.loads(a.b))
    print_report(result)
    if a.json:
        json.dump(result, open(a.json, "w"), indent=2)
