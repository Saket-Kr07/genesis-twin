"""Checks that the pathogen lab output has the shape agreed in Section 9 of the plan.
Run:  python check_contract.py
Prints PASS or a list of problems. Research and education only."""
import sys
from pathogen import list_pathogens, simulate_pathogen, ORGAN_IDS

problems = []


def need(cond, msg):
    if not cond:
        problems.append(msg)


presets = list_pathogens()
need(len(presets) >= 3, "list_pathogens should return at least 3 pathogens")
for p in presets:
    need(all(k in p for k in ("id", "name", "kind")), "list_pathogens entry missing id, name or kind: %s" % p)

for p in presets:
    for day, treat in ((0, 0.0), (10, 0.5), (30, 1.0)):
        tag = "%s day=%s treatment=%s" % (p["id"], day, treat)
        r = simulate_pathogen(p["id"], day, treat)
        need(isinstance(r.get("load"), (int, float)) and 0 <= r["load"] <= 1, tag + ": load must be a number from 0 to 1")
        need(isinstance(r.get("curve"), list) and len(r["curve"]) > 0, tag + ": curve must be a non-empty list")
        for pt in r.get("curve", []):
            need("day" in pt and "load" in pt, tag + ": curve points need day and load")
            break
        organs = r.get("organs", {})
        need(sorted(organs) == sorted(ORGAN_IDS), tag + ": organs must contain exactly the 12 organ ids")
        for oid, o in organs.items():
            need(0 <= o.get("score", -1) <= 100, "%s: %s score must be 0 to 100" % (tag, oid))
            need(isinstance(o.get("vitals"), dict) and o["vitals"], "%s: %s needs vitals" % (tag, oid))

# an unknown pathogen id should give a plain error; out-of-range day or treatment is clamped by design
try:
    simulate_pathogen("nope", 5, 0.5)
    problems.append("an unknown pathogen id should raise ValueError")
except ValueError:
    pass
r = simulate_pathogen("respiratory_virus", 99, 5)
need(r["day"] == 30 and r["treatment"] == 1.0, "day and treatment should be limited to 0-30 and 0-1")

if problems:
    print("PROBLEMS:")
    for m in problems:
        print(" -", m)
    sys.exit(1)
print("PASS: output matches the contract for %d pathogens." % len(presets))
