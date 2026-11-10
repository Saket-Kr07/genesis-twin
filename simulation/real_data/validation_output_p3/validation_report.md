# Validation against published data

**Source:** Viloria Winnett et al 2022, Caltech COVID-19 Study, CaltechDATA DOI 10.22002/D1.20049, participant 3
**Preset checked:** Sample respiratory virus (`respiratory_virus`), untreated reference adult
**Published points used:** 31

Rise-and-fall curve fitted to the published data: R squared 0.9038.

| Quantity | Published (95% range) | Our preset | Ratio preset / published | Agrees (inside range or within 30%) |
|---|---|---|---|---|
| growth rate | 0.01 (0.0 to 44958492223.6871) | 2.3595 | 235.95 | yes |
| decay rate | 20.0 (0.0 to 919357231.8921) | 0.6446 | 0.032 | yes |

Shape after shifting our curve by 5.50 days: normalised RMSE 0.130 (not a good match, limit 0.10).

**Verdict: our sample preset partly agrees with this published time series.**

Notes on the published fit: The highest load is at the first or last time point, so the rise or the fall is not fully covered. The growth and decay estimates are uncertain.

Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is called day 0; the shift in days is only used for the shape comparison.
