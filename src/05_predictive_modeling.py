"""Step 5 - Predictive modelling of 30-day readmission.

Prediction target : readmit_30 (readmitted < 30 days after discharge)
Prediction time   : at discharge from the index encounter (all predictors are known by then)
Unit of analysis  : patient (index encounter; one row per patient, so a stratified split is also a
                    patient-grouped split and no patient appears in two partitions)
Split             : 60% train / 20% validation / 20% untouched test, stratified on the outcome
Tuning            : randomised search with 5-fold stratified CV on the training set only
Selection         : best validation ROC-AUC; logistic regression preferred if within 0.005 (parsimony)
Threshold         : flag the 20% highest-risk patients (cut-off fixed on validation predictions)

EDUCATIONAL USE ONLY - this model has not been clinically validated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import loguniform, randint, uniform
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FIG_DIR, INDEX_COHORT_CSV, MODEL_DIR, RANDOM_STATE, TABLE_DIR, get_logger, save_json  # noqa: E402
from viz_style import BASE, HIGHLIGHT, INK, INK_2, MUTED, SERIES, SURFACE, finish, subtitle  # noqa: E402

log = get_logger("modeling")

NUMERIC = ["age_mid", "time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
           "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses", "n_diabetes_meds",
           "n_med_dose_changes"]
CATEGORICAL = ["gender", "admission_type_grp", "admission_source_grp", "discharge_group", "diag_1_group",
               "diag_2_group", "diag_3_group", "A1C_result", "glucose_serum", "insulin", "metformin", "change",
               "diabetesMed", "medical_specialty_grp"]
EXCLUDED = {
    "encounter_id, patient_nbr": "Identifiers - no predictive meaning; risk of memorisation",
    "readmitted, readmit_any": "Outcome information (target leakage)",
    "encounter_seq, is_index_encounter, expired_or_hospice": "Constant within the analysis cohort",
    "race": "Excluded as a predictor to avoid encoding structural inequities; used only for fairness audit",
    "payer_code": "Socio-economic proxy with 40% missing; excluded for fairness and data-quality reasons",
    "diag_1/2/3 raw ICD-9 codes": "700+ sparse levels; replaced by clinical groups",
    "raw ID columns (admission/discharge/source)": "Replaced by grouped labels",
}
TOP_SHARE = 0.20


def make_preprocessor(scale: bool) -> ColumnTransformer:
    num = StandardScaler() if scale else "passthrough"
    return ColumnTransformer([
        ("num", num, NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50, sparse_output=False),
         CATEGORICAL),
    ])


def candidates() -> dict:
    return {
        "Logistic regression (L2)": (
            Pipeline([("prep", make_preprocessor(True)),
                      ("clf", LogisticRegression(max_iter=3000, solver="lbfgs"))]),
            {"clf__C": loguniform(1e-3, 10)}, 12),
        "Random forest": (
            Pipeline([("prep", make_preprocessor(False)),
                      ("clf", RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=RANDOM_STATE))]),
            {"clf__max_depth": [6, 8, 10, 14, None], "clf__min_samples_leaf": randint(5, 80),
             "clf__max_features": ["sqrt", 0.2, 0.35]}, 10),
        "Gradient boosting (HistGB)": (
            Pipeline([("prep", make_preprocessor(False)),
                      ("clf", HistGradientBoostingClassifier(random_state=RANDOM_STATE, early_stopping=True,
                                                             validation_fraction=0.15, n_iter_no_change=20,
                                                             max_iter=600))]),
            {"clf__learning_rate": loguniform(0.02, 0.2), "clf__max_leaf_nodes": randint(8, 48),
             "clf__min_samples_leaf": randint(20, 200), "clf__l2_regularization": uniform(0, 2)}, 14),
    }


def metrics_at(y, p, thr) -> dict:
    pred = (p > thr).astype(int)  # strict: tied scores at the cut-off are not flagged
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"threshold": float(thr), "flagged_share": float(pred.mean()),
            "accuracy": accuracy_score(y, pred), "precision_ppv": precision_score(y, pred, zero_division=0),
            "recall_sensitivity": recall_score(y, pred), "specificity": tn / (tn + fp),
            "npv": tn / (tn + fn) if (tn + fn) else np.nan, "f1": f1_score(y, pred),
            "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)}


def calibration_stats(y, p) -> dict:
    import statsmodels.api as sm
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    slope_m = sm.Logit(y, sm.add_constant(lp)).fit(disp=False)
    int_m = sm.GLM(y, np.ones_like(lp), family=sm.families.Binomial(), offset=lp).fit()
    return {"calibration_slope": float(slope_m.params[1]), "calibration_in_the_large": float(int_m.params[0]),
            "mean_predicted": float(p.mean()), "observed_rate": float(np.mean(y))}


def bootstrap_ci(y, p, fn, n_boot=1000, seed=RANDOM_STATE) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        vals.append(fn(y[idx], p[idx]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def evaluate(name, y, p, thr) -> dict:
    out = {"model": name, "roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p),
           "brier": brier_score_loss(y, p)}
    out["brier_skill_vs_prevalence"] = 1 - out["brier"] / brier_score_loss(y, np.full_like(p, np.mean(y)))
    out.update(metrics_at(y, p, thr))
    return out


# ------------------------------------------------------------------ figures
def fig_roc_pr(y_test, preds: dict, prevalence: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    colors = {name: SERIES[i] for i, name in enumerate(preds)}
    for name, p in preds.items():
        fpr, tpr, _ = roc_curve(y_test, p)
        axes[0].plot(fpr, tpr, color=colors[name], lw=2, label=f"{name} (AUC {roc_auc_score(y_test, p):.3f})")
        prec, rec, _ = precision_recall_curve(y_test, p)
        axes[1].plot(rec, prec, color=colors[name], lw=2,
                     label=f"{name} (AP {average_precision_score(y_test, p):.3f})")
    axes[0].plot([0, 1], [0, 1], color=MUTED, lw=1)
    axes[0].text(0.62, 0.55, "chance", color=MUTED, fontsize=8, rotation=38)
    axes[0].set_xlabel("False-positive rate (1 − specificity)")
    axes[0].set_ylabel("True-positive rate (sensitivity)")
    axes[0].set_title("ROC curves (test set)")
    axes[0].legend(loc="lower right", fontsize=8)
    axes[1].axhline(prevalence, color=MUTED, lw=1)
    axes[1].text(0.7, prevalence + 0.008, f"prevalence {prevalence:.1%}", color=MUTED, fontsize=8)
    axes[1].set_xlabel("Recall (sensitivity)")
    axes[1].set_ylabel("Precision (positive predictive value)")
    axes[1].set_title("Precision–recall curves (test set)")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_ylim(0, 0.5)
    finish(fig, FIG_DIR / "fig14_roc_pr_curves.png", source="Source: UCI Diabetes 130-US Hospitals; held-out "
           "test set (20% of patients). Educational model, not clinically validated.")


def fig_calibration(y_test, preds: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 5))
    for i, (name, p) in enumerate(preds.items()):
        frac_pos, mean_pred = calibration_curve(y_test, p, n_bins=10, strategy="quantile")
        ax.plot(mean_pred, frac_pos, "o-", color=SERIES[i], lw=2, ms=6, label=name)
    lim = 0.35
    ax.plot([0, lim], [0, lim], color=MUTED, lw=1)
    ax.text(0.25, 0.235, "perfect calibration", color=MUTED, fontsize=8, rotation=38)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("Mean predicted risk (decile)")
    ax.set_ylabel("Observed 30-day readmission rate")
    ax.set_title("Calibration (test set, risk deciles)")
    ax.legend(loc="upper left", fontsize=8)
    finish(fig, FIG_DIR / "fig15_calibration.png", source="Source: held-out test set; quantile bins.")


def fig_confusion(cm: np.ndarray, name: str, m: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    labels = [["True negative", "False positive"], ["False negative", "True positive"]]
    shades = [["#cde2fb", "#fde3d6"], ["#fde3d6", "#9ec5f4"]]
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j, 1 - i), 0.97, 0.97, color=shades[i][j]))
            ax.text(j + 0.485, 1 - i + 0.55, f"{cm[i, j]:,}", ha="center", va="center", fontsize=17,
                    color=INK, fontweight="bold")
            ax.text(j + 0.485, 1 - i + 0.3, f"{labels[i][j]}\n{cm[i, j] / cm.sum():.1%} of patients", ha="center",
                    va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_xticks([0.485, 1.485], ["Predicted: not flagged", "Predicted: high risk"])
    ax.set_yticks([1.485, 0.485], ["Actual: not\nreadmitted", "Actual:\nreadmitted"])
    ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f"Confusion matrix — {name}")
    subtitle(ax, f"Top {TOP_SHARE:.0%} risk flagged · sensitivity {m['recall_sensitivity']:.1%} · "
                 f"PPV {m['precision_ppv']:.1%} · specificity {m['specificity']:.1%}")
    finish(fig, FIG_DIR / "fig16_confusion_matrix.png", source="Source: held-out test set.")


def fig_importance(imp: pd.DataFrame, name: str) -> None:
    top = imp.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    y = np.arange(len(top))
    ax.barh(y, top["importance_mean"], xerr=top["importance_std"], color=BASE, height=0.62,
            error_kw={"ecolor": INK_2, "elinewidth": 1, "capsize": 2})
    ax.set_yticks(y, top["feature"])
    ax.axvline(0, color=INK_2, lw=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Mean decrease in ROC-AUC when the feature is shuffled (validation set, 10 repeats)")
    ax.set_title(f"Permutation feature importance — {name}")
    subtitle(ax, "Importance reflects predictive contribution, not causal effect")
    finish(fig, FIG_DIR / "fig17_feature_importance.png", source="Source: validation set (20% of patients).")


def fig_subgroups(sub: pd.DataFrame, overall_auc: float) -> None:
    sub = sub[sub["n"] >= 300].copy()
    sub["label"] = sub["attribute"] + ": " + sub["group"].astype(str) + "  (n=" + sub["n"].map("{:,}".format) + ")"
    sub = sub.iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(12, 0.36 * len(sub) + 1.6), sharey=True)
    y = np.arange(len(sub))
    axes[0].errorbar(sub["roc_auc"], y, xerr=[sub["roc_auc"] - sub["auc_ci_low"], sub["auc_ci_high"] - sub["roc_auc"]],
                     fmt="o", color=BASE, ecolor=INK_2, elinewidth=1, capsize=2, ms=6)
    axes[0].axvline(overall_auc, color=INK_2, lw=1, ls=(0, (1, 2)))
    axes[0].set_yticks(y, sub["label"], fontsize=8.5)
    axes[0].set_xlabel("ROC-AUC (95% bootstrap CI)")
    axes[0].set_title("Discrimination by subgroup")
    axes[0].grid(axis="y", visible=False)
    axes[1].scatter(sub["recall_sensitivity"], y, color=BASE, s=36, label="Sensitivity", zorder=3)
    axes[1].scatter(sub["flagged_share"], y, color=HIGHLIGHT, s=36, marker="D", label="Share flagged", zorder=3)
    axes[1].xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    axes[1].set_xlabel("Rate at the top-20% threshold")
    axes[1].set_title("Sensitivity and flag rate by subgroup")
    axes[1].legend(loc="lower right", fontsize=8)
    axes[1].grid(axis="y", visible=False)
    finish(fig, FIG_DIR / "fig18_subgroup_performance.png", source="Source: held-out test set; subgroups with "
           "n ≥ 300 shown. Race was not a model input.")


def main() -> None:
    df = pd.read_csv(INDEX_COHORT_CSV, low_memory=False)
    X, y = df[NUMERIC + CATEGORICAL + ["race"]], df["readmit_30"].values
    X_tmp, X_test, y_tmp, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE)
    X_train, X_val, y_train, y_val = train_test_split(X_tmp, y_tmp, test_size=0.25, stratify=y_tmp,
                                                      random_state=RANDOM_STATE)
    race_test = X_test["race"].values
    X_train, X_val, X_test = (d.drop(columns="race") for d in (X_train, X_val, X_test))
    split = {"train": len(X_train), "validation": len(X_val), "test": len(X_test),
             "train_rate": float(y_train.mean()), "validation_rate": float(y_val.mean()),
             "test_rate": float(y_test.mean())}
    log.info("Split %s", split)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    fitted, cv_rows, val_preds = {}, [], {}
    for name, (pipe, grid, n_iter) in candidates().items():
        log.info("Tuning %s", name)
        search = RandomizedSearchCV(pipe, grid, n_iter=n_iter, scoring="roc_auc", cv=cv, n_jobs=-1,
                                    random_state=RANDOM_STATE, refit=True)
        search.fit(X_train, y_train)
        fitted[name] = search.best_estimator_
        val_preds[name] = search.best_estimator_.predict_proba(X_val)[:, 1]
        cv_rows.append({"model": name, "cv_roc_auc_mean": search.best_score_,
                        "cv_roc_auc_sd": float(search.cv_results_["std_test_score"][search.best_index_]),
                        "best_params": {k.replace("clf__", ""): (round(v, 5) if isinstance(v, float) else v)
                                        for k, v in search.best_params_.items()},
                        "val_roc_auc": roc_auc_score(y_val, val_preds[name]),
                        "val_pr_auc": average_precision_score(y_val, val_preds[name])})
        log.info("%s CV AUC %.4f | val AUC %.4f", name, search.best_score_, cv_rows[-1]["val_roc_auc"])

    # Baselines
    dummy = DummyClassifier(strategy="prior").fit(X_train, y_train)
    simple = Pipeline([("prep", ColumnTransformer([("num", StandardScaler(), ["number_inpatient"])])),
                       ("clf", LogisticRegression())]).fit(X_train, y_train)
    fitted["Baseline: prevalence only"] = dummy
    fitted["Baseline: prior inpatient count (1-variable LR)"] = simple
    for name in ["Baseline: prevalence only", "Baseline: prior inpatient count (1-variable LR)"]:
        val_preds[name] = fitted[name].predict_proba(X_val)[:, 1]
        cv_rows.append({"model": name, "cv_roc_auc_mean": np.nan, "cv_roc_auc_sd": np.nan, "best_params": {},
                        "val_roc_auc": roc_auc_score(y_val, val_preds[name]),
                        "val_pr_auc": average_precision_score(y_val, val_preds[name])})
    cv_df = pd.DataFrame(cv_rows)
    cv_df.to_csv(TABLE_DIR / "model_tuning_and_validation.csv", index=False)

    # Selection on validation data only
    cand = cv_df[~cv_df["model"].str.startswith("Baseline")].set_index("model")
    best = cand["val_roc_auc"].idxmax()
    lr_name = "Logistic regression (L2)"
    if best != lr_name and cand.loc[best, "val_roc_auc"] - cand.loc[lr_name, "val_roc_auc"] < 0.005:
        selection_note = (f"{best} had the highest validation AUC but {lr_name} was within 0.005, so the "
                          "simpler, more interpretable model was selected")
        best = lr_name
    else:
        selection_note = f"{best} had the highest validation ROC-AUC"
    thr = float(np.quantile(val_preds[best], 1 - TOP_SHARE))
    f1_thr_grid = np.quantile(val_preds[best], np.linspace(0.5, 0.99, 100))
    f1_thr = float(max(f1_thr_grid, key=lambda t: f1_score(y_val, (val_preds[best] > t).astype(int))))
    log.info("Selected %s; top-20%% threshold %.4f; max-F1 threshold %.4f", best, thr, f1_thr)

    # Final, single evaluation on the untouched test set
    test_preds = {n: m.predict_proba(X_test)[:, 1] for n, m in fitted.items()}
    rows = []
    for name, p in test_preds.items():
        model_thr = thr if name == best else float(np.quantile(val_preds[name], 1 - TOP_SHARE)) \
            if not name.startswith("Baseline: prevalence") else 0.5
        rows.append(evaluate(name, y_test, p, model_thr))
    test_df = pd.DataFrame(rows)
    test_df.to_csv(TABLE_DIR / "model_test_metrics.csv", index=False)

    p_best = test_preds[best]
    auc_ci = bootstrap_ci(y_test, p_best, roc_auc_score)
    ap_ci = bootstrap_ci(y_test, p_best, average_precision_score)
    calib = calibration_stats(y_test, p_best)
    thresholds = pd.DataFrame([
        {"rule": "Default 0.5 cut-off", **metrics_at(y_test, p_best, 0.5)},
        {"rule": f"Top {TOP_SHARE:.0%} highest risk (validation-derived)", **metrics_at(y_test, p_best, thr)},
        {"rule": "Max-F1 on validation", **metrics_at(y_test, p_best, f1_thr)},
        {"rule": "Flag nobody (always predict 'no readmission')", **metrics_at(y_test, p_best, 1.01)},
    ])
    thresholds.to_csv(TABLE_DIR / "model_threshold_comparison.csv", index=False)

    # Risk deciles (lift)
    dec = pd.DataFrame({"y": y_test, "p": p_best})
    dec["decile"] = pd.qcut(dec["p"].rank(method="first"), 10, labels=range(10, 0, -1)).astype(int)
    lift = dec.groupby("decile").agg(patients=("y", "size"), readmissions=("y", "sum"), mean_pred=("p", "mean"),
                                     observed_rate=("y", "mean")).sort_index()
    lift["capture_cumulative"] = lift["readmissions"].cumsum() / lift["readmissions"].sum()
    lift["lift"] = lift["observed_rate"] / y_test.mean()
    lift.to_csv(TABLE_DIR / "model_risk_deciles.csv")

    # Subgroup performance (fairness audit)
    sub_rows = []
    attrs = {"Gender": X_test["gender"].values, "Race": race_test,
             "Age group": pd.cut(X_test["age_mid"], [0, 40, 60, 80, 100], labels=["<40", "40–59", "60–79", "80+"]).astype(str).values}
    for attr, vals in attrs.items():
        for g in pd.unique(vals):
            mask = vals == g
            if mask.sum() < 50 or y_test[mask].sum() < 5:
                continue
            m = metrics_at(y_test[mask], p_best[mask], thr)
            lo, hi = bootstrap_ci(y_test[mask], p_best[mask], roc_auc_score, n_boot=500)
            sub_rows.append({"attribute": attr, "group": g, "n": int(mask.sum()),
                             "events": int(y_test[mask].sum()), "observed_rate": float(y_test[mask].mean()),
                             "mean_predicted": float(p_best[mask].mean()),
                             "roc_auc": roc_auc_score(y_test[mask], p_best[mask]), "auc_ci_low": lo,
                             "auc_ci_high": hi, **m})
    sub = pd.DataFrame(sub_rows)
    sub.to_csv(TABLE_DIR / "model_subgroup_performance.csv", index=False)

    # Interpretability: permutation importance on validation set
    pi = permutation_importance(fitted[best], X_val, y_val, scoring="roc_auc", n_repeats=10,
                                random_state=RANDOM_STATE, n_jobs=-1)
    imp = pd.DataFrame({"feature": X_val.columns, "importance_mean": pi.importances_mean,
                        "importance_std": pi.importances_std}).sort_values("importance_mean", ascending=False)
    imp.to_csv(TABLE_DIR / "model_permutation_importance.csv", index=False)
    # Logistic coefficients are saved regardless of selection, as a transparent reference model.
    lr = fitted[lr_name]
    names = lr.named_steps["prep"].get_feature_names_out()
    coefs = pd.DataFrame({"feature": names, "coef_standardised": lr.named_steps["clf"].coef_[0]})
    coefs["odds_ratio"] = np.exp(coefs["coef_standardised"])
    coefs.sort_values("coef_standardised", key=np.abs, ascending=False).to_csv(
        TABLE_DIR / "model_logistic_coefficients.csv", index=False)

    # Figures
    plot_models = [best] + [n for n in cand.index if n != best] + ["Baseline: prior inpatient count (1-variable LR)"]
    fig_roc_pr(y_test, {n: test_preds[n] for n in plot_models}, float(y_test.mean()))
    fig_calibration(y_test, {n: test_preds[n] for n in plot_models[:3]})
    best_m = metrics_at(y_test, p_best, thr)
    fig_confusion(np.array([[best_m["tn"], best_m["fp"]], [best_m["fn"], best_m["tp"]]]), best, best_m)
    fig_importance(imp, best)
    fig_subgroups(sub, roc_auc_score(y_test, p_best))

    # Artifacts
    joblib.dump({"model": fitted[best], "threshold_top20": thr, "features": NUMERIC + CATEGORICAL,
                 "sklearn_version": sklearn.__version__,
                 "notice": "Educational model. Not validated for clinical use."}, MODEL_DIR / "readmission_model.joblib")
    summary = {"selected_model": best, "selection_note": selection_note, "split": split,
               "threshold_top20": thr, "threshold_max_f1": f1_thr, "test_roc_auc": roc_auc_score(y_test, p_best),
               "test_roc_auc_ci": auc_ci, "test_pr_auc": average_precision_score(y_test, p_best),
               "test_pr_auc_ci": ap_ci, "test_brier": brier_score_loss(y_test, p_best), "calibration": calib,
               "test_metrics_top20": best_m, "excluded_features": EXCLUDED, "features_numeric": NUMERIC,
               "features_categorical": CATEGORICAL, "sklearn_version": sklearn.__version__,
               "top_decile_capture": float(lift.loc[1, "capture_cumulative"]),
               "top2_decile_capture": float(lift.loc[2, "capture_cumulative"]),
               "top_decile_rate": float(lift.loc[1, "observed_rate"]),
               "bottom_decile_rate": float(lift.loc[10, "observed_rate"])}
    save_json(summary, MODEL_DIR / "model_metrics.json")
    log.info("TEST %s AUC %.4f (%.4f-%.4f) AP %.4f Brier %.4f calib %s", best, summary["test_roc_auc"], *auc_ci,
             summary["test_pr_auc"], summary["test_brier"], calib)
    log.info("\n%s", test_df[["model", "roc_auc", "pr_auc", "brier", "accuracy", "precision_ppv",
                              "recall_sensitivity", "specificity", "f1"]].round(4).to_string())
    log.info("\n%s", thresholds[["rule", "accuracy", "precision_ppv", "recall_sensitivity", "specificity", "f1",
                                 "flagged_share"]].round(4).to_string())
    log.info("\n%s", sub[["attribute", "group", "n", "roc_auc", "recall_sensitivity", "flagged_share"]].round(3).to_string())
    log.info("\n%s", imp.head(10).round(4).to_string())


if __name__ == "__main__":
    main()
