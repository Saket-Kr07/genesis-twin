"""Organ tropism from receptor expression data (Part D, Saket).

Tropism says how strongly a pathogen attacks each organ (0 = never, 1 = fully). For a real pathogen, a good
starting point is where its entry receptor is expressed in the body. This module turns an expression table in the
style of the Human Protein Atlas (HPA) into the {organ_id: 0 to 1} dictionary that simulate_custom() accepts.

How to use it with real data
  1. Download the HPA table for your receptor yourself (for example the normal tissue or RNA tissue file) and
     keep the rows of your gene, for example ACE2. Check the file's licence and citation rules.
  2. python tropism.py --file normal_tissue.tsv --gene ACE2 --label "Human Protein Atlas, version X, gene ACE2"
  3. Pass result["tropism"] to simulate_custom(..., tropism=...).

Accepted values (use one kind only):
  - levels:  Not detected, Low, Medium, High   (becomes 0, 0.3, 0.6, 0.9)
  - numbers: for example nTPM; scaled so the highest tissue is 0.9
Rows marked "Not representative" are ignored. Check the column names and level words of the file you download.

Rules of the mapping (documented, not hidden):
  - Tissue names map to the 12 organ ids with fitting.tissue_to_organ (for example "cerebral cortex" to brain,
    "lymph node" to spleen, adrenal gland to thyroid, gallbladder to liver). Tissues with no organ are listed in
    "unmapped_tissues" (for example skeletal muscle).
  - If several rows map to one organ, the highest value is used.
  - Organs with no data get a small default (0.05) and are listed in "no_data_organs". "Not detected" counts as data (0).

The presets in pathogen.py stay hand-set SAMPLE values. This module is how real data would replace them.
Research and education only, not medical advice.
"""
import argparse
import csv
import io
import json
import math
import sys

from fitting import tissue_to_organ
from pathogen import ORGAN_IDS

LEVELS = {"not detected": 0.0, "low": 0.3, "medium": 0.6, "high": 0.9}
IGNORED_LEVELS = {"not representative"}
NUMERIC_TOP = 0.9
DEFAULT_NO_DATA = 0.05
VALUE_COLUMNS = ("level", "ntpm", "value", "expression")


def read_expression_table(text, gene=None):
    """Read a tab, comma or semicolon separated table. Returns a list of (tissue, value) pairs.

    Needs a Tissue column and one of Level, nTPM, Value, Expression. If gene is given, only rows of that gene
    (matched on the 'Gene name' or 'Gene' column, ignoring case) are used."""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig", errors="replace")
    text = (text or "").lstrip("\ufeff")
    if not text.strip():
        raise ValueError("The expression table is empty.")
    first = text.splitlines()[0]
    delimiter = max(["\t", ",", ";"], key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header = [h.strip().lower() for h in rows[0]]
    if "tissue" not in header:
        raise ValueError("The table must have a Tissue column.")
    value_col = next((c for c in VALUE_COLUMNS if c in header), None)
    if value_col is None:
        raise ValueError("The table must have one of these columns: Level, nTPM, Value, Expression.")
    ti, vi = header.index("tissue"), header.index(value_col)
    gene_cols = [header.index(c) for c in ("gene name", "gene") if c in header]
    if gene and not gene_cols:
        raise ValueError("A gene was given but the table has no 'Gene name' or 'Gene' column.")

    pairs = []
    for row in rows[1:]:
        if not any(c.strip() for c in row) or max(ti, vi) >= len(row):
            continue
        if gene and not any(gc < len(row) and row[gc].strip().lower() == gene.strip().lower() for gc in gene_cols):
            continue
        pairs.append((row[ti].strip(), row[vi].strip()))
    if not pairs:
        raise ValueError("No rows found%s." % (" for gene %s" % gene if gene else ""))
    return pairs


def _to_pairs(data, gene):
    if isinstance(data, (str, bytes)):
        return read_expression_table(data, gene)
    if isinstance(data, dict):
        return list(data.items())
    try:
        return [(t, v) for t, v in data]
    except (TypeError, ValueError):
        raise ValueError("Give a table as text, a {tissue: value} dictionary or a list of (tissue, value) pairs.")


def _convert(pairs):
    """Turn raw values into numbers. Returns [(tissue, raw, number_or_None_if_ignored)] and whether numbers were used."""
    kinds, out = set(), []
    for tissue, raw in pairs:
        if isinstance(raw, str) and raw.strip().lower() in IGNORED_LEVELS:
            continue
        if isinstance(raw, str) and raw.strip().lower() in LEVELS:
            kinds.add("level")
            out.append((tissue, raw.strip(), LEVELS[raw.strip().lower()]))
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            raise ValueError("Unknown expression level '%s'. Use Not detected, Low, Medium, High, or a number." % raw)
        if not math.isfinite(number) or number < 0:
            raise ValueError("Expression values cannot be negative or missing (found '%s')." % raw)
        kinds.add("number")
        out.append((tissue, str(raw).strip(), number))
    if len(kinds) > 1:
        raise ValueError("Use either levels (Low, Medium, High) or numbers, not both in one table.")
    if not out:
        raise ValueError("No usable rows (all rows were 'Not representative').")
    if "number" in kinds:
        top = max(n for _, _, n in out)
        out = [(t, r, (NUMERIC_TOP * n / top) if top > 0 else 0.0) for t, r, n in out]
    return out


def tropism_from_expression(data, gene=None, source=None, default=DEFAULT_NO_DATA):
    """Convert an expression table into organ tropism.

    data:    table text (HPA style), a {tissue: value} dictionary, or a list of (tissue, value) pairs
    gene:    only for table text: keep the rows of this gene
    source:  citation text, echoed in the result (always give it for real data)
    default: tropism for organs with no data in the table

    Returns {"tropism": {organ_id: 0 to 1 for all 12}, "organs_from_data", "no_data_organs",
             "unmapped_tissues", "evidence": {organ: {"tissue", "value", "tropism"}}, "source"}.
    """
    converted = _convert(_to_pairs(data, gene))
    best, unmapped = {}, []
    for tissue, raw, number in converted:
        organ = tissue_to_organ(tissue)
        if organ is None:
            if tissue not in unmapped:
                unmapped.append(tissue)
            continue
        if organ not in best or number > best[organ]["tropism"]:
            best[organ] = {"tissue": tissue, "value": raw, "tropism": round(number, 4)}
    tropism = {o: (best[o]["tropism"] if o in best else float(default)) for o in ORGAN_IDS}
    return {"tropism": tropism,
            "organs_from_data": [o for o in ORGAN_IDS if o in best],
            "no_data_organs": [o for o in ORGAN_IDS if o not in best],
            "unmapped_tissues": unmapped, "evidence": best, "source": source}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Turn a receptor expression table into organ tropism.")
    ap.add_argument("--file", required=True, help="expression table (tab, comma or semicolon separated)")
    ap.add_argument("--gene", help="keep only the rows of this gene, for example ACE2")
    ap.add_argument("--label", required=True, help="citation of the data, for example 'Human Protein Atlas, version X, gene ACE2'")
    ap.add_argument("--out", help="write the result to this JSON file")
    args = ap.parse_args(argv)
    with open(args.file, "rb") as f:
        result = tropism_from_expression(f.read(), gene=args.gene, source=args.label)
    print("Source:", args.label)
    for organ in ORGAN_IDS:
        e = result["evidence"].get(organ)
        print("  %-13s %.2f  %s" % (organ, result["tropism"][organ],
                                    ("from %s (%s)" % (e["tissue"], e["value"])) if e else "no data (default)"))
    if result["unmapped_tissues"]:
        print("Tissues with no organ (ignored):", ", ".join(result["unmapped_tissues"]))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=1)
        print("Wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
