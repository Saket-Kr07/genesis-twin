# Validation against published data

**Source:** Viloria Winnett et al 2022, Caltech COVID-19 Study, CaltechDATA DOI 10.22002/D1.20049, participant 1
**Preset checked:** Sample respiratory virus (`respiratory_virus`), untreated reference adult
**Published points used:** 37

Rise-and-fall curve fitted to the published data: R squared 0.9751.

| Quantity | Published (95% range) | Our preset | Ratio preset / published | Agrees (inside range or within 30%) |
|---|---|---|---|---|
| growth rate | 4.3436 (2.4298 to 6.2574) | 2.3595 | 0.543 | no |
| decay rate | 4.2039 (1.5104 to 6.8974) | 0.6446 | 0.153 | no |

Shape after shifting our curve by 8.25 days: normalised RMSE 0.175 (not a good match, limit 0.10).

**Verdict: our sample preset does not agree with this published time series.**

What to change in the preset:
- The rise differs. In pathogen.py change beta or prod for this preset (they set the growth rate): raise them.
- The fall differs. Change clear, delta or kill for this preset (they set the decay rate): raise them.

Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is called day 0; the shift in days is only used for the shape comparison.
