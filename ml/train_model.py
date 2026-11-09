"""
Train one small RandomForest per biomarker:
    (age, sex, sleep, exercise, smoking, diet)  ->  blood pressure, ALT, glucose, ...
Saves everything in a single joblib file: models/health_model.joblib

Run:  python train_model.py            (after prepare_data.py)
"""
import sys
from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "processed" / "nhanes_2017_2018.csv"
OUT = HERE / "models" / "health_model.joblib"

FEATURES = ["age", "sex_male", "sleep_hours", "exercise_min_week", "smoking", "diet_score"]
TARGETS = ["sbp", "dbp", "pulse", "alt", "ast", "bilirubin", "creatinine", "glucose", "hba1c"]


def main(data_path: Path = DATA, out_path: Path = OUT) -> None:
    if not data_path.exists():
        sys.exit(f"{data_path} not found - run prepare_data.py first.")
    df = pd.read_csv(data_path)
    models, metrics = {}, {}
    for t in TARGETS:
        d = df.dropna(subset=[t])                     # each biomarker has its own sample size
        X_tr, X_te, y_tr, y_te = train_test_split(d[FEATURES], d[t], test_size=0.2, random_state=42)
        # min_samples_leaf keeps the forest smooth instead of memorising people
        m = RandomForestRegressor(n_estimators=300, min_samples_leaf=20, random_state=42, n_jobs=-1)
        m.fit(X_tr, y_tr)
        pred = m.predict(X_te)
        base_mae = mean_absolute_error(y_te, [y_tr.mean()] * len(y_te))
        metrics[t] = {"n": int(len(d)), "r2": round(r2_score(y_te, pred), 3),
                      "mae": round(mean_absolute_error(y_te, pred), 3),
                      "mae_if_always_predicting_mean": round(base_mae, 3)}
        models[t] = m
        print(f"{t:11s} n={len(d):5d}  R2={metrics[t]['r2']:6.3f}  MAE={metrics[t]['mae']:7.3f}  (mean-baseline MAE {base_mae:.3f})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "features": FEATURES, "metrics": metrics,
                 "trained_on": "NHANES 2017-2018 adults"}, out_path)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
