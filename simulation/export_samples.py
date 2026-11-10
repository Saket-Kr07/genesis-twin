"""Writes example outputs as JSON files, so teammates can build and test without running Python.

Run:  python export_samples.py
Creates the folder sample_output/ (commit it, then tell Rakhi, Rudraksh and Shambhavi).
All values are sample values for a demo. Research and education only, not medical advice.
"""
import json
import os

from fitting import fit_pathogen
from pathogen import (describe_profile, list_pathogens, load_band, model_info, simulate_custom,
                      simulate_pathogen, simulate_timeline)
from tropism import tropism_from_expression

OUT = "sample_output"
ADULT = {"sex": "male", "age": 30, "height_cm": 175, "weight_kg": 70}
CHILD = {"sex": "female", "age": 8, "height_cm": 128, "weight_kg": 26,
         "baseline_vitals": {"heart_rate": 92, "breathing_rate": 22}}
OLDER = {"sex": "male", "age": 78, "height_cm": 170, "weight_kg": 72}

os.makedirs(OUT, exist_ok=True)


def save(name, data):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(data, f, indent=1)
    print("wrote", name)


save("pathogens.json", list_pathogens())
save("simulate_adult_day6.json", simulate_pathogen("respiratory_virus", 6, 0.3))
save("simulate_child_day6.json", simulate_pathogen("respiratory_virus", 6, 0.3, profile=CHILD))
save("timeline_older_late_treatment.json", simulate_timeline("respiratory_virus", 0.5, 2, OLDER))
save("load_band.json", load_band("respiratory_virus", 0.3))
save("profile_summary_child.json", describe_profile(CHILD))

with open("sample_data/example_pathogen.csv") as f:
    fit = fit_pathogen(f.read())
save("fit_good_file.json", fit)
save("fit_bad_file.json", fit_pathogen("day,load\n0,1\n1,-3\n2,\n3,abc\n4,2"))
save("simulate_uploaded_day6.json", simulate_custom(fit["parameters"], fit["target_organs"], 6, 0.0))

with open("sample_data/example_expression_SYNTHETIC.tsv") as f:
    expression = tropism_from_expression(f.read(), gene="EXAMPLEGENE",
                                         source="SYNTHETIC example, not real Human Protein Atlas data")
save("tropism_example_SYNTHETIC.json", expression)
save("simulate_uploaded_with_tropism_day6.json",
     simulate_custom(fit["parameters"], [], 6, 0.0, tropism=expression["tropism"]))
save("model_info.json", model_info())

with open(os.path.join(OUT, "README.txt"), "w") as f:
    f.write("""Example outputs of the pathogen lab (sample values, research and education only).

pathogens.json                     GET /pathogens
simulate_adult_day6.json           POST /pathogens/simulate, reference adult, day 6, treatment 30 percent
simulate_child_day6.json           same, with a child profile and face-scan baseline vitals
timeline_older_late_treatment.json all days in one call (times, load, scores, days). For sliders and animation.
load_band.json                     uncertainty band around the load curve
profile_summary_child.json         summary for the profile form (BMI, age group, assumptions)
fit_good_file.json                 POST /pathogens/upload with a good CSV
fit_bad_file.json                  POST /pathogens/upload with a bad CSV (plain-language errors)
simulate_uploaded_day6.json        simulating the uploaded pathogen
tropism_example_SYNTHETIC.json     tropism from a receptor expression table (SYNTHETIC numbers, shape only)
simulate_uploaded_with_tropism_day6.json   the uploaded pathogen using that tropism
model_info.json                    model version, settings and preset parameters
""")
print("wrote README.txt")
