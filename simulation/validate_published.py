"""Check a preset pathogen against a REAL published time series (Part D, Saket).

You supply a CSV with the columns  day  and  load  taken from a published paper
(a supplementary table, or a figure read with a free tool such as WebPlotDigitizer), and the citation.
The script then:
  1. fits the rise-and-fall curve to the published data (fitting.py),
  2. fits the same curve to our preset's untreated curve,
  3. compares the growth rate and the decay rate (they do not depend on which day you call day 0),
  4. compares the overall shape after the best shift in days,
  5. writes validation.png, validation_report.json and validation_report.md.

Run:
  python validate_published.py --csv data.csv --pathogen respiratory_virus --label "Author Year, DOI 10.xxxx/xxxx"
Options:
  --log10      the load column is in log10 units (for example log10 copies per mL); it is converted first
  --tolerance  how close counts as agreeing (default 0.3 = within 30 percent)
  --out        output folder (default validation_output)

Only use real data that you can cite. Values at or below the detection limit should be removed or set to 0.
A match on one dataset checks the SHAPE of our sample pathogen against that one paper. It does not prove
the model is correct in general. Research and education only, not medical advice.
"""
import argparse
import csv
import io
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt
import numpy as np

from fitting import fit_pathogen
from pathogen import PRESETS, simulate_pathogen

SHAPE_LIMIT = 0.10   # normalised RMSE at or below this counts as a good shape match


def _convert_log10(csv_text):
    """Turn a log10 load column into plain numbers. Cells that are not numbers are left for fit_pathogen to report."""
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows or "load" not in [h.strip().lower() for h in rows[0]]:
        return csv_text
    li = [h.strip().lower() for h in rows[0]].index("load")
    for row in rows[1:]:
        if li < len(row):
            try:
                row[li] = repr(10.0 ** float(row[li]))
            except (ValueError, OverflowError):
                pass
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(rows)
    return out.getvalue()


def _preset_csv(pathogen_id):
    curve = simulate_pathogen(pathogen_id, 0, 0.0)["curve"]
    return "day,load\n" + "\n".join("%d,%.6f" % (p["day"], p["load"]) for p in curve)


def _rate(name, published, preset_value, tolerance):
    ratio = preset_value / published["value"] if published["value"] else float("nan")
    inside = published["low"] is not None and published["low"] <= preset_value <= published["high"]
    return {"name": name, "published": published, "preset": round(preset_value, 4),
            "ratio_preset_to_published": round(ratio, 3), "inside_published_range": bool(inside),
            "agrees": bool(inside or abs(ratio - 1.0) <= tolerance)}


def _shape(days, loads, pathogen_id):
    """Best shift in days and the normalised RMSE between the published data and our preset curve."""
    y = np.asarray(loads, dtype=float)
    y = y / y.max()
    smooth = simulate_pathogen(pathogen_id, 0, 0.0)["curve_smooth"]
    t = np.array([p["day"] for p in smooth])
    v = np.array([p["load"] for p in smooth])
    v = v / v.max()
    d = np.asarray(days, dtype=float)
    best_offset, best_rmse = 0.0, float("inf")
    for offset in np.arange(-10.0, 10.01, 0.25):
        model = np.interp(d + offset, t, v, left=0.0, right=0.0)
        rmse = float(np.sqrt(np.mean((model - y) ** 2)))
        if rmse < best_rmse:
            best_offset, best_rmse = float(offset), rmse
    return best_offset, best_rmse, t, v


def validate(csv_text, pathogen_id, label, log10=False, tolerance=0.3, outdir="validation_output"):
    """Run the whole check. Returns the report dictionary (also written to outdir)."""
    if pathogen_id not in PRESETS:
        raise ValueError("Unknown pathogen_id: %s" % pathogen_id)
    if not str(label or "").strip():
        raise ValueError("Please give the citation of the published data (label), for example 'Author Year, DOI ...'")
    text = _convert_log10(csv_text) if log10 else csv_text

    published = fit_pathogen(text)
    if published["validation_errors"]:
        return {"ok": False, "label": label, "validation_errors": published["validation_errors"]}
    preset = fit_pathogen(_preset_csv(pathogen_id))

    rows = list(csv.DictReader(io.StringIO(text)))
    rows = [r for r in rows if r.get("day", "").strip() != ""]
    pairs = sorted((float(r["day"]), float(r["load"])) for r in rows)
    days = [p[0] for p in pairs]
    loads = [p[1] for p in pairs]

    growth = _rate("growth_rate", published["parameters"]["growth_rate"], preset["parameters"]["growth_rate"]["value"], tolerance)
    decay = _rate("decay_rate", published["parameters"]["decay_rate"], preset["parameters"]["decay_rate"]["value"], tolerance)
    offset, rmse, t, v = _shape(days, loads, pathogen_id)
    shape_good = rmse <= SHAPE_LIMIT

    n_agree = int(growth["agrees"]) + int(decay["agrees"]) + int(shape_good)
    verdict = "agrees" if n_agree == 3 else ("partly agrees" if n_agree >= 1 else "does not agree")

    advice = []
    if not growth["agrees"]:
        advice.append("The rise differs. In pathogen.py change beta or prod for this preset (they set the growth rate): "
                      "%s." % ("raise them" if growth["ratio_preset_to_published"] < 1 else "lower them"))
    if not decay["agrees"]:
        advice.append("The fall differs. Change clear, delta or kill for this preset (they set the decay rate): "
                      "%s." % ("raise them" if decay["ratio_preset_to_published"] < 1 else "lower them"))

    report = {
        "ok": True, "label": label, "pathogen_id": pathogen_id, "preset_name": PRESETS[pathogen_id]["name"],
        "points": len(days), "log10": bool(log10), "tolerance": tolerance,
        "published_fit": {"r_squared": published["fit"]["r_squared"], "warnings": published["warnings"],
                          "parameters": published["parameters"]},
        "preset_fit": {"r_squared": preset["fit"]["r_squared"], "parameters": preset["parameters"]},
        "growth_rate": growth, "decay_rate": decay,
        "shape": {"best_offset_days": round(offset, 2), "normalised_rmse": round(rmse, 4),
                  "good_match": bool(shape_good), "limit": SHAPE_LIMIT},
        "verdict": verdict, "advice": advice,
    }

    os.makedirs(outdir, exist_ok=True)
    _plot(report, days, loads, t, v, published, offset, os.path.join(outdir, "validation.png"))
    with open(os.path.join(outdir, "validation_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(outdir, "validation_report.md"), "w") as f:
        f.write(_markdown(report))
    return report


def _plot(report, days, loads, t, v, published, offset, path):
    y = np.asarray(loads, dtype=float)
    y = y / y.max()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
    a1.plot(days, y, "o", label="published data")
    fitted = published["fitted_curve"]
    top = max(p["load"] for p in fitted)
    a1.plot([p["day"] for p in fitted], [p["load"] / top for p in fitted], "-", label="curve fitted to the data")
    a1.plot(t - offset, v, "--", label="our preset (shifted %.2f days)" % offset)
    a1.set_xlim(min(days) - 1, max(days) + 1)
    a1.set_xlabel("day (as in the paper)")
    a1.set_ylabel("load (1 = highest value)")
    a1.set_title("shape, RMSE %.3f" % report["shape"]["normalised_rmse"], fontsize=10)
    a1.legend(fontsize=7)
    a1.grid(alpha=0.3)
    labels, pub_v, pre_v, err = [], [], [], [[], []]
    for key in ("growth_rate", "decay_rate"):
        p = report[key]["published"]
        labels.append(key.replace("_", " "))
        pub_v.append(p["value"])
        pre_v.append(report[key]["preset"])
        lo = p["low"] if p["low"] is not None else p["value"]
        hi = p["high"] if p["high"] is not None else p["value"]
        err[0].append(p["value"] - lo)
        err[1].append(hi - p["value"])
    x = np.arange(2)
    a2.bar(x - 0.2, pub_v, 0.4, yerr=err, capsize=4, label="published (95% range)")
    a2.bar(x + 0.2, pre_v, 0.4, label="our preset")
    a2.set_xticks(x)
    a2.set_xticklabels(labels)
    a2.set_ylabel("per day")
    a2.set_title("verdict: %s" % report["verdict"], fontsize=10)
    a2.legend(fontsize=8)
    fig.suptitle(report["label"], fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _markdown(r):
    def line(k):
        p = r[k]["published"]
        rng = "%s to %s" % (p["low"], p["high"]) if p["low"] is not None else "not available"
        return "| %s | %s (%s) | %s | %s | %s |" % (k.replace("_", " "), p["value"], rng, r[k]["preset"],
                                                  r[k]["ratio_preset_to_published"], "yes" if r[k]["agrees"] else "no")
    lines = [
        "# Validation against published data",
        "",
        "**Source:** %s" % r["label"],
        "**Preset checked:** %s (`%s`), untreated reference adult" % (r["preset_name"], r["pathogen_id"]),
        "**Published points used:** %d%s" % (r["points"], " (converted from log10)" if r["log10"] else ""),
        "",
        "Rise-and-fall curve fitted to the published data: R squared %s." % r["published_fit"]["r_squared"],
        "",
        "| Quantity | Published (95%% range) | Our preset | Ratio preset / published | Agrees (inside range or within %.0f%%) |" % (r["tolerance"] * 100),
        "|---|---|---|---|---|",
        line("growth_rate"),
        line("decay_rate"),
        "",
        "Shape after shifting our curve by %.2f days: normalised RMSE %.3f (%s, limit %.2f)." % (
            r["shape"]["best_offset_days"], r["shape"]["normalised_rmse"],
            "good match" if r["shape"]["good_match"] else "not a good match", r["shape"]["limit"]),
        "",
        "**Verdict: our sample preset %s with this published time series.**" % r["verdict"],
        "",
    ]
    if r["published_fit"]["warnings"]:
        lines += ["Notes on the published fit: " + " ".join(r["published_fit"]["warnings"]), ""]
    if r["advice"]:
        lines += ["What to change in the preset:"] + ["- " + a for a in r["advice"]] + [""]
    lines += [
        "Limits: this compares the shape of our sample pathogen with one published time series. It is not proof that the model "
        "is correct in general, and the preset parameters remain sample values. Growth and decay rates do not depend on which day is "
        "called day 0; the shift in days is only used for the shape comparison.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check a preset pathogen against published data.")
    ap.add_argument("--csv", required=True, help="CSV with columns day and load")
    ap.add_argument("--pathogen", default="respiratory_virus", choices=sorted(PRESETS))
    ap.add_argument("--label", required=True, help="citation of the published data, for example 'Author Year, DOI ...'")
    ap.add_argument("--log10", action="store_true", help="the load column is in log10 units")
    ap.add_argument("--tolerance", type=float, default=0.3)
    ap.add_argument("--out", default="validation_output")
    args = ap.parse_args(argv)
    with open(args.csv, encoding="utf-8-sig") as f:
        report = validate(f.read(), args.pathogen, args.label, args.log10, args.tolerance, args.out)
    if not report["ok"]:
        print("The file has problems:")
        for e in report["validation_errors"]:
            print(" -", e)
        return 1
    print("Verdict: %s" % report["verdict"])
    print("Growth rate: published %.3f, preset %.3f" % (report["growth_rate"]["published"]["value"], report["growth_rate"]["preset"]))
    print("Decay rate:  published %.3f, preset %.3f" % (report["decay_rate"]["published"]["value"], report["decay_rate"]["preset"]))
    print("Shape RMSE: %.3f at a shift of %.2f days" % (report["shape"]["normalised_rmse"], report["shape"]["best_offset_days"]))
    print("Wrote %s/validation.png, validation_report.json and validation_report.md" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
