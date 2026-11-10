"""Draws pictures of the model so you can check it and use them in the report.

Run:  python demo_plot.py
Creates: curves.png, organs_day6.png, fit.png, late_treatment.png and body_profiles.png here.
"""
import csv
import json

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

from fitting import fit_pathogen
from pathogen import ORGAN_IDS, list_pathogens, load_band, simulate_pathogen, simulate_timeline

# Picture 1: smooth load curves with three treatment strengths, plus an uncertainty band
fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
for ax, item in zip(axes, list_pathogens()):
    band = load_band(item["id"], 0.0)
    ax.fill_between(band["times"], band["low"], band["high"], alpha=0.2, label="uncertainty band (no treatment)")
    for treatment, style in [(0.0, "-"), (0.5, "--"), (1.0, ":")]:
        curve = simulate_pathogen(item["id"], 0, treatment)["curve_smooth"]
        ax.plot([p["day"] for p in curve], [p["load"] for p in curve], style,
                linewidth=2, label="treatment %.0f%%" % (treatment * 100))
    ax.set_title(item["name"], fontsize=10)
    ax.set_xlabel("day")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("pathogen load (1 = untreated peak)")
axes[0].legend(fontsize=7)
fig.tight_layout()
fig.savefig("curves.png", dpi=140)

# Picture 2: organ health on day 6 for the respiratory virus, untreated vs treated
fig2, ax2 = plt.subplots(figsize=(8, 4))
width = 0.4
x = range(len(ORGAN_IDS))
for offset, treatment, label in [(-width / 2, 0.0, "no treatment"), (width / 2, 0.6, "treatment 60%")]:
    organs = simulate_pathogen("respiratory_virus", 6, treatment)["organs"]
    ax2.bar([i + offset for i in x], [organs[o]["score"] for o in ORGAN_IDS], width, label=label)
ax2.set_xticks(list(x))
ax2.set_xticklabels(ORGAN_IDS, rotation=45, ha="right")
ax2.set_ylabel("organ health score (100 = healthy)")
ax2.set_title("Sample respiratory virus, day 6")
ax2.legend()
fig2.tight_layout()
fig2.savefig("organs_day6.png", dpi=140)

# Picture 3: fit the example CSV (synthetic data) and show the curve with its numbers
with open("sample_data/example_pathogen.csv") as f:
    text = f.read()
fit = fit_pathogen(text)
rows = list(csv.DictReader(text.splitlines()))
fig3, ax3 = plt.subplots(figsize=(6, 3.8))
ax3.plot([float(r["day"]) for r in rows], [float(r["load"]) for r in rows], "o", label="uploaded data")
ax3.plot([p["day"] for p in fit["fitted_curve"]], [p["load"] for p in fit["fitted_curve"]], "-", label="fitted curve")
g, dcy = fit["parameters"]["growth_rate"], fit["parameters"]["decay_rate"]
ax3.set_title("growth %.2f/day (%.2f to %.2f), decay %.2f/day" % (g["value"], g["low"], g["high"], dcy["value"]), fontsize=9)
ax3.set_xlabel("day")
ax3.set_ylabel("load")
ax3.legend()
ax3.grid(alpha=0.3)
fig3.tight_layout()
fig3.savefig("fit.png", dpi=140)

# Picture 4: what starting treatment late does (respiratory virus, treatment 80%)
fig4, (ax4, ax5) = plt.subplots(1, 2, figsize=(10, 3.6))
for start in (0, 2, 4, 6):
    tl = simulate_timeline("respiratory_virus", 0.8, start)
    ax4.plot(tl["times"], tl["load"], linewidth=2, label="treatment starts day %d" % start)
    ax5.plot(tl["times"], tl["scores"]["lungs"], linewidth=2)
none = simulate_timeline("respiratory_virus", 0.0)
ax4.plot(none["times"], none["load"], "k--", label="no treatment")
ax5.plot(none["times"], none["scores"]["lungs"], "k--")
ax4.set_title("pathogen load")
ax5.set_title("lung health score")
for a in (ax4, ax5):
    a.set_xlabel("day")
    a.grid(alpha=0.3)
ax4.legend(fontsize=8)
fig4.tight_layout()
fig4.savefig("late_treatment.png", dpi=140)

# Picture 5: the same infection in different bodies (child, adult woman, adult man, older man, large body)
people = {
    "child, 8 y, 128 cm": {"sex": "female", "age": 8, "height_cm": 128, "weight_kg": 26},
    "woman, 30 y, 165 cm": {"sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60},
    "man, 30 y, 175 cm": {"sex": "male", "age": 30, "height_cm": 175, "weight_kg": 70},
    "older man, 78 y": {"sex": "male", "age": 78, "height_cm": 170, "weight_kg": 72},
    "man, 40 y, 115 kg": {"sex": "male", "age": 40, "height_cm": 175, "weight_kg": 115},
}
fig5, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13, 3.6))
for label, profile in people.items():
    tl = simulate_timeline("respiratory_virus", 0.0, 0, profile)
    a1.plot(tl["times"], tl["scores"]["lungs"], linewidth=2, label=label)
    a2.plot(tl["times"], tl["load"], linewidth=2)
    a3.bar(label.split(",")[0] + "\n" + label.split(",")[-1].strip()[:12],
           simulate_pathogen("respiratory_virus", 0, 0.0, profile=profile)["organs"]["lungs"]["vitals"]["lung_capacity"])
a1.set_title("lung health score")
a2.set_title("pathogen load")
a3.set_title("resting lung capacity (L)")
for a in (a1, a2):
    a.set_xlabel("day")
    a.grid(alpha=0.3)
a3.tick_params(axis="x", labelsize=6)
a1.legend(fontsize=7)
fig5.tight_layout()
fig5.savefig("body_profiles.png", dpi=140)

# What the backend receives (lungs only, to keep the print short)
sample = simulate_pathogen("respiratory_virus", 6, 0.0)
print(json.dumps({"load": sample["load"], "lungs": sample["organs"]["lungs"]}, indent=2))
print("Saved curves.png, organs_day6.png, fit.png, late_treatment.png and body_profiles.png")
