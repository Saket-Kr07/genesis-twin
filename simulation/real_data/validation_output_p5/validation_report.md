# Validation against published data

**Source:** Viloria Winnett et al 2022, Caltech COVID-19 Study, CaltechDATA DOI 10.22002/D1.20049, participant 5
**Preset checked:** Sample respiratory virus (`respiratory_virus`), untreated reference adult
**Published points used:** 27

Rise-and-fall curve fitted to the published data: R squared 0.6744.

| Quantity | Published (95% range) | Our preset | Ratio preset / published | Agrees (inside range or within 30%) |
|---|---|---|---|---|
| growth rate | 0.9338 (0.1804 to 1.6873) | 2.3595 | 2.527 | no |
| decay rate | 10.7394 (0.0 to 165.235) | 0.6446 | 0.06 | yes |

Shape after shifting our curve by 1.25 days: normalised RMSE 0.215 (not a good match, limit 0.10).

**Verdict: our sample preset partly agrees with this published time series.**

Notes on the published fit: The fit is weak (R squared 0.67). Check the data or add more time points.

What to change in the preset:
- The rise differs. In pathogen.py change beta or prod for this preset (they set the growth rate): lower them.

Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is called day 0; the shift in days is only used for the shape comparison.
