"""
Download NHANES 2017-2018 files from the CDC and build ONE adult-only table
with the 6 model inputs (features) and the measured biomarkers (targets).

Run (needs internet):   python prepare_data.py
Output:                 data/processed/nhanes_2017_2018.csv

If a download fails, fetch the .XPT files manually from
https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2017
and drop them in data/raw/ -- the script reuses files that already exist.
"""
from pathlib import Path
import requests
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "data" / "processed" / "nhanes_2017_2018.csv"
URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/{}.xpt"

# file -> what we take from it
FILES = ["DEMO_J", "SLQ_J", "PAQ_J", "SMQ_J", "DBQ_J", "BPX_J", "BIOPRO_J", "GLU_J", "GHB_J"]


def download(name: str) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{name}.XPT"
    if not path.exists():
        print(f"downloading {name} ...")
        r = requests.get(URL.format(name), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def load(name: str) -> pd.DataFrame:
    return pd.read_sas(download(name), format="xport", encoding="utf-8")


def clean_codes(s: pd.Series) -> pd.Series:
    """NHANES uses 7/77/777/7777 = refused and 9/99/999/9999 = don't know."""
    return s.where(~s.isin([7, 9, 77, 99, 777, 999, 7777, 9999]))


def main() -> None:
    d = {n: load(n) for n in FILES}
    df = d["DEMO_J"][["SEQN", "RIDAGEYR", "RIAGENDR"]]
    for n in FILES[1:]:
        df = df.merge(d[n], on="SEQN", how="left")

    df = df[df["RIDAGEYR"] >= 18].copy()          # adults only (age 80 = "80 and over")

    out = pd.DataFrame({"SEQN": df["SEQN"]})
    # ---- FEATURES (what the user types in) ----
    out["age"] = df["RIDAGEYR"]
    out["sex_male"] = (df["RIAGENDR"] == 1).astype(int)
    out["sleep_hours"] = df["SLD012"]                       # weekday sleep hours

    def weekly(yes, days, mins):                            # recreational activity, min/week
        t = clean_codes(df[days]) * clean_codes(df[mins])
        return np.where(df[yes] == 2, 0, t)                 # said "no" -> 0 minutes
    moderate = weekly("PAQ665", "PAQ670", "PAD675")
    vigorous = weekly("PAQ650", "PAQ655", "PAD660")
    out["exercise_min_week"] = moderate + 2 * vigorous      # WHO "moderate-equivalent" minutes

    ever, now = df["SMQ020"], df["SMQ040"]                  # 0 never, 1 former, 2 current
    smoking = pd.Series(np.nan, index=df.index)
    smoking[ever == 2] = 0
    smoking[(ever == 1) & (now == 3)] = 1
    smoking[(ever == 1) & now.isin([1, 2])] = 2
    out["smoking"] = smoking

    out["diet_score"] = 6 - clean_codes(df["DBQ700"])       # 1 = poor ... 5 = excellent

    # ---- TARGETS (measured in the NHANES exam / lab) ----
    def mean_cols(prefix):                                  # average of repeat BP readings
        cols = [c for c in df.columns if c.startswith(prefix) and c[-1].isdigit()]
        return df[cols].replace(0, np.nan).mean(axis=1)
    out["sbp"] = mean_cols("BPXSY")
    out["dbp"] = mean_cols("BPXDI")
    out["pulse"] = df["BPXPLS"]
    out["alt"] = df["LBXSATSI"]
    out["ast"] = df["LBXSASSI"]
    out["bilirubin"] = df["LBXSTB"]
    out["creatinine"] = df["LBXSCR"]
    out["glucose"] = df["LBXGLU"]                           # fasting subsample only
    out["hba1c"] = df["LBXGH"]

    feats = ["age", "sex_male", "sleep_hours", "exercise_min_week", "smoking", "diet_score"]
    out = out.dropna(subset=feats)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"saved {len(out)} adults -> {OUT}")
    print(out.describe().T[["count", "mean", "min", "max"]].round(2))


if __name__ == "__main__":
    main()
