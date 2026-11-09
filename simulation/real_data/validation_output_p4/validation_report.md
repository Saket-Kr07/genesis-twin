# Validation against published data

**Source:** Viloria Winnett et al 2022, Caltech COVID-19 Study, CaltechDATA DOI 10.22002/D1.20049, participant 4
**Preset checked:** Sample respiratory virus (`respiratory_virus`), untreated reference adult
**Published points used:** 28

Rise-and-fall curve fitted to the published data: R squared 0.6252.

| Quantity | Published (95% range) | Our preset | Ratio preset / published | Agrees (inside range or within 30%) |
|---|---|---|---|---|
| growth rate | 1.0663 (0.0 to 2.2313) | 2.3595 | 2.213 | no |
| decay rate | 20.0 (0.0 to 7784.9228) | 0.6446 | 0.032 | yes |

Shape after shifting our curve by 8.50 days: normalised RMSE 0.260 (not a good match, limit 0.10).

**Verdict: our sample preset partly agrees with this published time series.**

Notes on the published fit: The fit is weak (R squared 0.63). Check the data or add more time points.

What to change in the preset:
- The rise differs. In pathogen.py change beta or prod for this preset (they set the growth rate): lower them.

Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is called day 0; the shift in days is only used for the shape comparison.
