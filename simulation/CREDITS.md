# Credits and licences (Part D: pathogen lab, simulation/)

Genesis Twin is a research and education simulation. It is not medical advice and not a diagnostic tool.
All preset pathogen parameters and the generation simulator use sample assumptions, not real outbreak, clinical or family data.

## Data

**Longitudinal SARS-CoV-2 viral loads (used to check the pathogen model)**
- Viloria Winnett et al. 2022, Caltech COVID-19 Study. CaltechDATA, DOI 10.22002/D1.20049, https://data.caltech.edu/records/pmm08-6q581
- File 20220228_DataTables_Final.xlsx, sheet FIG1A&1C, nasal swab samples from participants A, B, E, G and F.
- Licence: CC0 (public domain), as listed on the CaltechDATA record.
- Processing: values marked ND (not detected) removed; days shifted so the first sample is day 0. See real_data/SOURCE.txt.
- The accompanying paper was a medRxiv preprint (not peer reviewed). Replace it with the peer-reviewed reference if one exists.

**Human Protein Atlas (RNA consensus tissue expression, used for the receptor-based tropism table)**
- Credit: Human Protein Atlas, proteinatlas.org
- Data used: RNA consensus tissue expression (nTPM), gene ACE2, file rna_tissue_consensus.tsv, available from v25.proteinatlas.org (version 25.1). Accessed 9 November 2026.
- Primary publications cited:
  - Uhlén M et al., Tissue-based map of the human proteome. Science (2015). PubMed 25613900, DOI 10.1126/science.1260419
  - Karlsson M et al., A single-cell type transcriptomics map of human tissues. Sci Adv (2021). PubMed 34321199, DOI 10.1126/sciadv.abh2169
- Licence: Creative Commons Attribution-ShareAlike 4.0 International. Anything we derive from the data (real_data/tropism_ACE2.json) and publish should carry the same licence and credit.
- Rule from the Atlas: its content must never be displayed without this citation. Any screen that shows the tropism table needs the credit next to it.
- The consensus data combines Human Protein Atlas and GTEx (Genotype-Tissue Expression project) data. GTEx is listed by the Atlas as "User terms": https://gtexportal.org. Gene identifiers are Ensembl IDs (Ensembl, "User terms"). Action: read the GTEx and Ensembl terms of use and follow them. Credit GTEx wherever the tropism table is shown.
- The large source file is not stored in the repository (hpa_raw/ is ignored by Git).
- Limit: receptor expression for one gene only approximates where a virus attacks. For ACE2 the lung value is low, so it does not show lung infection risk.

## Software
- Python, NumPy, SciPy (ODE solver solve_ivp, curve fitting with curve_fit), pytest. See requirements.txt.
- Code: simulation/pathogen.py, fitting.py, tropism.py, validate_published.py, fit_and_record.py, check_contract.py, generations.py (Saket).

## For the team to add
Other parts add their own credits here or in the app credits page: 3D models (Z-Anatomy, BodyParts3D, share-alike licences), NHANES, paper sources (Europe PMC, PubMed, bioRxiv and medRxiv) and any other library or dataset.
