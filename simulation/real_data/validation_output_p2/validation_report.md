# Validation against published data

**Source:** Viloria Winnett et al 2022, Caltech COVID-19 Study, CaltechDATA DOI 10.22002/D1.20049, participant 2
**Preset checked:** Sample respiratory virus (`respiratory_virus`), untreated reference adult
**Published points used:** 31

Rise-and-fall curve fitted to the published data: R squared 0.9734.

| Quantity | Published (95% range) | Our preset | Ratio preset / published | Agrees (inside range or within 30%) |
|---|---|---|---|---|
| growth rate | 20.0 (0.0 to 88491.8537) | 2.3595 | 0.118 | yes |
| decay rate | 6.8021 (0.0 to 84.296) | 0.6446 | 0.095 | yes |

Shape after shifting our curve by 10.00 days: normalised RMSE 0.182 (not a good match, limit 0.10).

**Verdict: our sample preset partly agrees with this published time series.**

Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is called day 0; the shift in days is only used for the shape comparison.
