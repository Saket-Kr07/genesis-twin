# Credits and licences (Part D: pathogen lab, simulation/)

Genesis Twin is a research and education simulation. It is not medical advice and not a diagnostic tool.
All preset pathogen parameters and the generation simulator use sample assumptions, not real outbreak, clinical or family data.

## Data

**Longitudinal SARS-CoV-2 viral loads (used to check the pathogen model)**
- Viloria Winnett et al. 2022, Caltech COVID-19 Study. CaltechDATA, DOI 10.22002/D1.20049, https://data.caltech.edu/records/pmm08-6q581
- File 20220228_DataTables_Final.xlsx, sheet FIG1A&1C, nasal swab samples from participants A, B, E, G and F.
- Licence: CC0 (public domain), as listed on the CaltechDATA record.
- Processing: values marked ND (not detected) removed; days shifted so the first sample is day 0. See real_data/SOURCE.txt and real_data/SOURCE_extra.txt.
- The accompanying paper was a medRxiv preprint (not peer reviewed). Replace it with the peer-reviewed reference if one exists.

**Human Protein Atlas (RNA consensus tissue expression, used for the receptor-based tropism table)**
- Human Protein Atlas version 25.1, file rna_tissue_consensus.tsv, gene ACE2 (nTPM). https://www.proteinatlas.org
- Image and data credit: Human Protein Atlas.
- Licence: Creative Commons Attribution-ShareAlike 4.0 International. Share-alike means anything we derive from the data (real_data/tropism_ACE2.json) and publish should carry the same licence and credit.
- Citation: copy the current citations from https://www.proteinatlas.org/about/licence, including the primary publications listed there (for example Karlsson M et al., 2021, Sci Adv, DOI 10.1126/sciadv.abh2169). Content must not be shown without the citation.
- The large source file is not stored in the repository (hpa_raw/ is ignored by Git).
- Limit: receptor expression for one gene only approximates where a virus attacks. For ACE2 the lung value is low, so it does not show lung infection risk.

## Software
- Python, NumPy, SciPy (ODE solver solve_ivp, curve fitting with curve_fit), pytest. See requirements.txt.
- Code: simulation/pathogen.py, fitting.py, tropism.py, validate_published.py, generations.py (Saket).

## For the team to add
Other parts add their own credits here or in the app credits page: 3D models (Z-Anatomy, BodyParts3D, share-alike licences), NHANES, paper sources (Europe PMC, PubMed, bioRxiv and medRxiv) and any other library or dataset.
