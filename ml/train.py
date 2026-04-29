from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


BASE_DIR = Path("~/lab/ml").expanduser()
FEATURES_PATH = BASE_DIR / "features.csv"


def main() -> None:
    df = pd.read_csv(FEATURES_PATH)
    if df.empty:
        raise SystemExit("features.csv is empty")

    cat_cols = ["src_ip", "dst_ip", "proto", "action", "signature"]
    num_cols = ["dst_port", "severity"]

    severity_map = {"high": 1, "medium": 2, "low": 3, "unknown": 2}
    df["severity"] = df["severity"].map(severity_map).fillna(2)

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

    if "label" in df.columns and df["label"].nunique() > 1 and not (df["label"] == "unknown").all():
        labeled = df[df["label"] != "unknown"].copy()
        y = labeled["label"]
        X_labeled = labeled[feature_cols]
        X_train, X_test, y_train, y_test = train_test_split(
            X_labeled, y, test_size=0.2, random_state=42, stratify=y
        )
        clf = Pipeline(
            [
                ("preprocessor", preprocessor),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=16,
                        class_weight="balanced",
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        )
        clf.fit(X_train, y_train)
        predictions = clf.predict(X_test)
        print(classification_report(y_test, predictions))
        joblib.dump(clf, BASE_DIR / "random_forest_pipeline.joblib")
    else:
        print("Skipping Random Forest: no labeled data or only one class.")

    results = {
        "total_scored": len(df),
        "anomaly_pct": str(round((df["anomaly_flag"] == -1).mean() * 100, 1)),
        "top_class": df.get("label", pd.Series(dtype=str)).mode().iloc[0] if "label" in df and not df["label"].empty else "unknown",
        "distribution": dict(df.get("label", pd.Series(dtype=str)).value_counts()),
        "trend": [],
    }
    (BASE_DIR / "latest_results.json").write_text(json.dumps(results), encoding="utf-8")


if __name__ == "__main__":
    main()