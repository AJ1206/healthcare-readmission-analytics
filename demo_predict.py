"""Demo: score patients from the held-out test set with the trained model.

Run after the pipeline:  python demo_predict.py [number_of_patients]
Educational use only - not for clinical decisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from common import INDEX_COHORT_CSV, MODEL_DIR, RANDOM_STATE  # noqa: E402


def main(n: int = 8) -> None:
    bundle = joblib.load(MODEL_DIR / "readmission_model.joblib")
    model, threshold, features = bundle["model"], bundle["threshold_top20"], bundle["features"]
    cohort = pd.read_csv(INDEX_COHORT_CSV, low_memory=False)

    # Recreate the exact held-out test split used in 05_predictive_modeling.py (never seen during training)
    _, test = train_test_split(cohort, test_size=0.20, stratify=cohort["readmit_30"], random_state=RANDOM_STATE)
    sample = pd.concat([test[test["readmit_30"] == 1].sample(n // 2, random_state=7),
                        test[test["readmit_30"] == 0].sample(n - n // 2, random_state=7)])
    sample["risk"] = model.predict_proba(sample[features])[:, 1]
    sample = sample.sort_values("risk", ascending=False)

    print(f"\nModel: {type(model.named_steps['clf']).__name__} | flag threshold (top 20% risk): {threshold:.1%}")
    print(f"Average 30-day readmission rate in the data: {cohort['readmit_30'].mean():.1%}\n")
    cols = {"age_band": "Age", "gender": "Sex", "diag_1_group": "Main diagnosis", "discharge_group": "Discharged to",
            "number_inpatient": "Prior admits", "time_in_hospital": "Days"}
    view = sample[list(cols)].rename(columns=cols)
    view["Predicted risk"] = sample["risk"].map("{:.1%}".format)
    view["Flagged?"] = (sample["risk"] > threshold).map({True: "YES - follow up", False: "no"})
    view["Actually readmitted?"] = sample["readmit_30"].map({1: "yes", 0: "no"})
    with pd.option_context("display.width", 200, "display.max_colwidth", 32):
        print(view.to_string(index=False))
    print("\nNote: the model ranks risk; it does not decide. About 1 in 6 flagged patients is actually readmitted.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
