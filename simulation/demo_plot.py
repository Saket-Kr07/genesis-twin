"""Draws pictures of the model so you can check it and use them in the report.

Run:  python demo_plot.py
Creates: curves.png, organs_day6.png and fit.png in this folder.
"""
import csv
import json

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

from fitting import fit_pathogen
from pathogen import ORGAN_IDS, list_pathogens, simulate_pathogen

# Picture 1: pathogen load over time, with three treatment strengths
fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
for ax, item in zip(axes, list_pathogens()):
    for treatment, style in [(0.0, "-"), (0.5, "--"), (1.0, ":")]:
        curve = simulate_pathogen(item["id"], 0, treatment)["curve"]
        ax.plot([p["day"] for p in curve], [p["load"] for p in curve], style,
                linewidth=2, label="treatment %.0f%%" % (treatment * 100))
    ax.set_title(item["name"], fontsize=10)
    ax.set_xlabel("day")
    ax.grid(alpha=0.3)
axes[0].set_ylabel("pathogen load (1 = untreated peak)")
axes[0].legend()
fig.tight_layout()
fig.savefig("curves.png", dpi=140)

# Picture 2: organ health on day 6 for virus A, untreated vs treated
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

# What the backend receives (lungs only, to keep the print short)
sample = simulate_pathogen("respiratory_virus", 6, 0.0)
print(json.dumps({"load": sample["load"], "lungs": sample["organs"]["lungs"]}, indent=2))
print("Saved curves.png, organs_day6.png and fit.png")
