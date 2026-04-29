from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path("~/lab/ml").expanduser()


def main() -> None:
    preprocessor = joblib.load(BASE_DIR / "preprocessor.joblib")
    iso = joblib.load(BASE_DIR / "isolation_forest.joblib")

    clf_path = BASE_DIR / "random_forest_pipeline.joblib"
    classifier = joblib.load(clf_path) if clf_path.exists() else None

    df = pd.read_csv(BASE_DIR / "features.csv")
    cat_cols = ["src_ip", "dst_ip", "proto", "action", "signature"]
    num_cols = ["dst_port", "severity"]

    severity_map = {"high": 1, "medium": 2, "low": 3, "unknown": 2}
    df["severity"] = df["severity"].map(severity_map).fillna(2)

    X = df[cat_cols + num_cols].copy()
    X_prepared = preprocessor.transform(X)

    df["anomaly_flag"] = iso.predict(X_prepared)
    df["anomaly_score"] = iso.decision_function(X_prepared)

    if classifier is not None:
        df["predicted_class"] = classifier.predict(X)
        probabilities = classifier.predict_proba(X)
        df["confidence"] = probabilities.max(axis=1)
    else:
        df["predicted_class"] = "unknown"
        df["confidence"] = 0.0

    predictions: list[dict[str, object]] = []
    for _, row in df.tail(50).iterrows():
        predictions.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "src_ip": str(row.get("src_ip", "unknown")),
                "dst_ip": str(row.get("dst_ip", "unknown")),
                "dst_port": int(row["dst_port"]),
                "anomaly_score": round(float(row["anomaly_score"]), 4),
                "anomaly_flag": int(row["anomaly_flag"]),
                "predicted_class": str(row["predicted_class"]),
                "confidence": round(float(row["confidence"]), 4),
            }
        )

    (BASE_DIR / "predictions.json").write_text(json.dumps(list(reversed(predictions))), encoding="utf-8")
    print(f"Inference done. {len(predictions)} predictions written.")


if __name__ == "__main__":
    main()