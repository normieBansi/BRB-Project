from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path("~/lab/ml").expanduser()
FEATURES_PATH = BASE_DIR / "features.csv"


def main() -> None:
    df = pd.read_csv(FEATURES_PATH)
    if df.empty:
        raise SystemExit("features.csv is empty")

    cat_cols = ["event_source", "src_ip", "dst_ip", "proto", "action", "signature", "rule_label", "direction"]
    num_cols = ["dst_port", "priority"]

    for col in cat_cols:
        if col not in df.columns:
            df[col] = "unknown"
        df[col] = df[col].astype(str).fillna("unknown")
    for col in num_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    feature_cols = cat_cols + num_cols
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]),
                num_cols,
            ),
            (
                "cat",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                cat_cols,
            ),
        ]
    )

    X = df[feature_cols].copy()
    X_prepared = preprocessor.fit_transform(X)

    iso = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
    iso.fit(X_prepared)
    df["anomaly_flag"] = iso.predict(X_prepared)
    df["anomaly_score"] = iso.decision_function(X_prepared)

    joblib.dump(preprocessor, BASE_DIR / "preprocessor.joblib")
    joblib.dump(iso, BASE_DIR / "isolation_forest.joblib")

    # This pipeline now runs in anomaly-only mode.
    proto_distribution = (
        {str(proto): int(count) for proto, count in df["proto"].astype(str).value_counts().items()}
        if "proto" in df.columns
        else {}
    )

    results = {
        "total_scored": int(len(df)),
        "anomaly_pct": str(round((df["anomaly_flag"] == -1).mean() * 100, 1)),
        "top_class": "anomaly_only",
        "distribution": proto_distribution,
        "trend": [],
    }
    (BASE_DIR / "latest_results.json").write_text(json.dumps(results), encoding="utf-8")
    print("Training complete in anomaly-only mode (Isolation Forest + preprocessor).")


if __name__ == "__main__":
    main()