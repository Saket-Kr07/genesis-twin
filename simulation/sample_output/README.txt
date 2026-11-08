Example outputs of the pathogen lab (sample values, research and education only).

pathogens.json                     GET /pathogens
simulate_adult_day6.json           POST /pathogens/simulate, reference adult, day 6, treatment 30 percent
simulate_child_day6.json           same, with a child profile and face-scan baseline vitals
timeline_older_late_treatment.json all days in one call (times, load, scores, days). For sliders and animation.
load_band.json                     uncertainty band around the load curve
profile_summary_child.json         summary for the profile form (BMI, age group, assumptions)
fit_good_file.json                 POST /pathogens/upload with a good CSV
fit_bad_file.json                  POST /pathogens/upload with a bad CSV (plain-language errors)
simulate_uploaded_day6.json        simulating the uploaded pathogen
