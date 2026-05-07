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

    df = pd.read_csv(BASE_DIR / "features.csv")
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

    X = df[cat_cols + num_cols].copy()
    X_prepared = preprocessor.transform(X)

    df["anomaly_flag"] = iso.predict(X_prepared)
    df["anomaly_score"] = iso.decision_function(X_prepared)

    predictions: list[dict[str, object]] = []
    for _, row in df.tail(50).iterrows():
        ts_value = row.get("timestamp", "")
        normalized_ts = str(ts_value) if str(ts_value).strip() else datetime.now(timezone.utc).isoformat()
        predictions.append(
            {
                "timestamp": normalized_ts,
                "src_ip": str(row.get("src_ip", "unknown")),
                "dst_ip": str(row.get("dst_ip", "unknown")),
                "dst_port": int(row["dst_port"]),
                "proto": str(row.get("proto", "UNKNOWN")),
                "action": str(row.get("action", "pass")),
                "signature": str(row.get("signature", ""))[:120],
                "anomaly_score": round(float(row["anomaly_score"]), 4),
                "anomaly_flag": int(row["anomaly_flag"]),
            }
        )

    (BASE_DIR / "predictions.json").write_text(json.dumps(list(reversed(predictions))), encoding="utf-8")
    print(f"Inference done. {len(predictions)} predictions written.")


if __name__ == "__main__":
    main()