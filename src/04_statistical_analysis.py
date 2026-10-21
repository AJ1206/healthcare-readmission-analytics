"""Step 4 - Inferential statistics on the analysis cohort.

Tests are chosen for the data types involved:
  * categorical x binary outcome  -> Pearson chi-square test of independence, Cramer's V
  * numeric (skewed counts) x binary outcome -> Mann-Whitney U, rank-biserial r, Welch CI for mean difference
  * LOS across >2 diagnosis groups -> Kruskal-Wallis H, epsilon-squared
  * Adjusted associations -> multivariable logistic regression (odds ratios, 95% CI)
Holm's method controls the family-wise error rate within each family of tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FIG_DIR, INDEX_COHORT_CSV, TABLE_DIR, get_logger, save_json  # noqa: E402
from viz_style import BASE, HIGHLIGHT, INK_2, MUTED, finish, subtitle  # noqa: E402

log = get_logger("statistics")

CAT_VARS = ["age_group", "gender", "race", "admission_type_grp", "admission_source_grp", "discharge_group",
            "diag_1_group", "A1C_result", "glucose_serum", "insulin", "change", "diabetesMed",
            "medical_specialty_grp", "payer_code"]
NUM_VARS = ["time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications", "number_outpatient",
            "number_emergency", "number_inpatient", "number_diagnoses", "age_mid", "n_med_dose_changes"]


def cramers_v(table: np.ndarray) -> float:
    chi2 = stats.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    r, k = table.shape
    return float(np.sqrt(chi2 / (n * (min(r, k) - 1))))


def chi_square_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for var in CAT_VARS:
        ct = pd.crosstab(df[var], df["readmit_30"])
        chi2, p, dof, expected = stats.chi2_contingency(ct.values, correction=False)
        rates = ct[1] / ct.sum(axis=1)
        rows.append({"variable": var, "levels": ct.shape[0], "chi2": chi2, "dof": dof, "p_value": p,
                     "cramers_v": cramers_v(ct.values),
                     "min_expected_count": float(expected.min()),
                     "pct_cells_expected_lt5": float((expected < 5).mean() * 100),
                     "lowest_rate_level": f"{rates.idxmin()} ({rates.min():.1%})",
                     "highest_rate_level": f"{rates.idxmax()} ({rates.max():.1%})"})
    out = pd.DataFrame(rows)
    out["p_holm"] = multipletests(out["p_value"], method="holm")[1]
    out["significant_holm_0.05"] = out["p_holm"] < 0.05
    return out.sort_values("cramers_v", ascending=False)


def numeric_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = df["readmit_30"] == 1
    for var in NUM_VARS:
        a, b = df.loc[y, var], df.loc[~y, var]
        u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
        r_rb = 1 - 2 * u / (len(a) * len(b))  # rank-biserial: P(b>a) - P(a>b), sign flipped below
        r_rb = -r_rb
        diff = a.mean() - b.mean()
        se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
        dof = se ** 4 / ((a.var(ddof=1) / len(a)) ** 2 / (len(a) - 1) + (b.var(ddof=1) / len(b)) ** 2 / (len(b) - 1))
        tcrit = stats.t.ppf(0.975, dof)
        pooled_sd = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
        rows.append({"variable": var, "mean_readmitted": a.mean(), "mean_not_readmitted": b.mean(),
                     "median_readmitted": a.median(), "median_not_readmitted": b.median(),
                     "mean_diff": diff, "mean_diff_ci_low": diff - tcrit * se, "mean_diff_ci_high": diff + tcrit * se,
                     "cohens_d": diff / pooled_sd, "mann_whitney_U": u, "p_value": p, "rank_biserial_r": r_rb})
    out = pd.DataFrame(rows)
    out["p_holm"] = multipletests(out["p_value"], method="holm")[1]
    out["significant_holm_0.05"] = out["p_holm"] < 0.05
    return out.sort_values("rank_biserial_r", key=np.abs, ascending=False)


def two_group_rates(df: pd.DataFrame, flag: str, label_1: str, label_0: str) -> dict:
    g1, g0 = df[df[flag] == 1], df[df[flag] == 0]
    e1, n1, e0, n0 = int(g1["readmit_30"].sum()), len(g1), int(g0["readmit_30"].sum()), len(g0)
    p1, p0 = e1 / n1, e0 / n0
    ci1 = proportion_confint(e1, n1, method="wilson")
    ci0 = proportion_confint(e0, n0, method="wilson")
    rd = p1 - p0
    se_rd = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    rr = p1 / p0
    se_log_rr = np.sqrt(1 / e1 - 1 / n1 + 1 / e0 - 1 / n0)
    odds = (e1 * (n0 - e0)) / ((n1 - e1) * e0)
    se_log_or = np.sqrt(1 / e1 + 1 / (n1 - e1) + 1 / e0 + 1 / (n0 - e0))
    z = rd / np.sqrt(((e1 + e0) / (n1 + n0)) * (1 - (e1 + e0) / (n1 + n0)) * (1 / n1 + 1 / n0))
    f = float
    return {"comparison": f"{label_1} vs {label_0}", "n_1": n1, "rate_1": p1, "rate_1_ci_low": f(ci1[0]),
            "rate_1_ci_high": f(ci1[1]), "n_0": n0, "rate_0": p0, "rate_0_ci_low": f(ci0[0]),
            "rate_0_ci_high": f(ci0[1]), "risk_difference": rd, "rd_ci_low": f(rd - 1.96 * se_rd),
            "rd_ci_high": f(rd + 1.96 * se_rd), "risk_ratio": rr,
            "rr_ci_low": f(np.exp(np.log(rr) - 1.96 * se_log_rr)), "rr_ci_high": f(np.exp(np.log(rr) + 1.96 * se_log_rr)),
            "odds_ratio": odds, "or_ci_low": f(np.exp(np.log(odds) - 1.96 * se_log_or)),
            "or_ci_high": f(np.exp(np.log(odds) + 1.96 * se_log_or)),
            "z": f(z), "p_value": f(2 * stats.norm.sf(abs(z)))}


def kruskal_los(df: pd.DataFrame) -> dict:
    groups = [g["time_in_hospital"].values for _, g in df.groupby("diag_1_group") if len(g) >= 100]
    h, p = stats.kruskal(*groups)
    n, k = sum(len(g) for g in groups), len(groups)
    return {"test": "Kruskal-Wallis: LOS across primary diagnosis groups", "H": h, "dof": k - 1, "p_value": p,
            "epsilon_squared": (h - k + 1) / (n - k), "groups": k, "n": n}


def spearman_key_pairs(df: pd.DataFrame) -> pd.DataFrame:
    pairs = [("time_in_hospital", "num_medications"), ("time_in_hospital", "num_lab_procedures"),
             ("time_in_hospital", "num_procedures"), ("num_medications", "num_procedures"),
             ("number_inpatient", "number_emergency"), ("age_mid", "number_diagnoses"),
             ("number_inpatient", "readmit_30"), ("time_in_hospital", "readmit_30")]
    rows = []
    for a, b in pairs:
        rho, p = stats.spearmanr(df[a], df[b])
        rows.append({"var_1": a, "var_2": b, "spearman_rho": rho, "p_value": p})
    out = pd.DataFrame(rows)
    out["p_holm"] = multipletests(out["p_value"], method="holm")[1]
    return out


def logistic_regression(df: pd.DataFrame):
    d = df.copy()
    d["race_grp"] = d["race"].where(d["race"].isin(["Caucasian", "AfricanAmerican", "Unknown"]), "Other")
    formula = ("readmit_30 ~ C(A1C_result, Treatment('Not measured')) + C(diag_1_group, Treatment('Other'))"
               " + C(age_group, Treatment('40–59')) + C(gender) + C(race_grp, Treatment('Caucasian'))"
               " + C(discharge_group, Treatment('Home')) + C(admission_source_grp, Treatment('Emergency room'))"
               " + time_in_hospital + num_medications + num_lab_procedures + number_diagnoses"
               " + number_inpatient + number_emergency + number_outpatient + C(change)")
    d = d[d["diag_1_group"] != "Missing"]
    model = smf.logit(formula, data=d).fit(disp=False, maxiter=200)
    ci = model.conf_int()
    res = pd.DataFrame({"term": model.params.index, "coef": model.params.values,
                        "odds_ratio": np.exp(model.params.values), "or_ci_low": np.exp(ci[0].values),
                        "or_ci_high": np.exp(ci[1].values), "p_value": model.pvalues.values})
    res = res[res["term"] != "Intercept"]
    res["term"] = (res["term"].str.replace(r"C\((\w+)(, Treatment\('[^']+'\))?\)\[T\.", r"\1 = ", regex=True)
                   .str.replace("]", "", regex=False))

    # Effect modification: does the A1C-readmission association differ by primary diagnosis? (Strack et al.)
    d["a1c_measured"] = d["A1C_measured"]
    base_f = formula.replace("C(A1C_result, Treatment('Not measured'))", "a1c_measured")
    m0 = smf.logit(base_f, data=d).fit(disp=False, maxiter=200)
    m1 = smf.logit(base_f + " + a1c_measured:C(diag_1_group, Treatment('Other'))", data=d).fit(disp=False,
                                                                                                 maxiter=200)
    lr = 2 * (m1.llf - m0.llf)
    df_diff = m1.df_model - m0.df_model
    interaction = {"LR_chi2": lr, "dof": df_diff, "p_value": stats.chi2.sf(lr, df_diff),
                   "a1c_measured_OR_main_model": float(np.exp(m0.params["a1c_measured"])),
                   "a1c_measured_OR_ci": tuple(np.exp(m0.conf_int().loc["a1c_measured"]).tolist()),
                   "a1c_measured_p": float(m0.pvalues["a1c_measured"])}
    fit = {"n": int(model.nobs), "events": int(d["readmit_30"].sum()), "pseudo_r2_mcfadden": model.prsquared,
           "llr_p_value": model.llr_pvalue, "aic": model.aic, "converged": bool(model.mle_retvals["converged"]),
           "max_vif_note": "Numeric predictors checked with VIF below"}
    num = ["time_in_hospital", "num_medications", "num_lab_procedures", "number_diagnoses", "number_inpatient",
           "number_emergency", "number_outpatient"]
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    X = d[num].assign(const=1.0).values
    fit["vif"] = {c: float(variance_inflation_factor(X, i)) for i, c in enumerate(num)}
    return res, fit, interaction


def fig_forest(res: pd.DataFrame) -> None:
    keep = res[~res["term"].str.startswith(("race_grp", "admission_source_grp", "change"))].copy()
    keep = keep.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(keep) + 1.5))
    y = np.arange(len(keep))
    sig = keep["p_value"] < 0.05
    ax.errorbar(keep["odds_ratio"], y, xerr=[keep["odds_ratio"] - keep["or_ci_low"],
                                              keep["or_ci_high"] - keep["odds_ratio"]],
                fmt="none", ecolor=INK_2, elinewidth=1, capsize=2)
    ax.scatter(keep["odds_ratio"], y, color=np.where(sig, HIGHLIGHT, BASE), s=36, zorder=3)
    ax.axvline(1, color=INK_2, lw=1)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2, 3], ["0.5", "0.75", "1", "1.5", "2", "3"])
    ax.set_yticks(y, keep["term"], fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Adjusted odds ratio for 30-day readmission (log scale, 95% CI)")
    ax.set_title("Multivariable logistic regression: adjusted odds ratios")
    subtitle(ax, "Orange = p < 0.05. Numeric terms are per one-unit increase. Race, admission source and "
                 "medication change also adjusted (Appendix D)")
    finish(fig, FIG_DIR / "fig13_logistic_regression_forest.png")


def main() -> None:
    df = pd.read_csv(INDEX_COHORT_CSV, low_memory=False)
    n, e = len(df), int(df["readmit_30"].sum())
    lo, hi = proportion_confint(e, n, method="wilson")
    overall = {"n": n, "events": e, "rate": e / n, "ci_low": lo, "ci_high": hi}

    chi = chi_square_tests(df)
    chi.to_csv(TABLE_DIR / "stats_chi_square_tests.csv", index=False)
    num = numeric_tests(df)
    num.to_csv(TABLE_DIR / "stats_mann_whitney_tests.csv", index=False)
    rates = [two_group_rates(df, "any_prior_inpatient", "≥1 prior inpatient admission", "none"),
             two_group_rates(df, "A1C_measured", "HbA1c measured", "not measured"),
             two_group_rates(df.assign(facility=df["discharge_group"].isin(
                 ["Skilled nursing / ICF", "Other inpatient / rehab facility"]).astype(int)),
                 "facility", "Discharged to a care facility", "all other destinations"),
             two_group_rates(df.assign(long_stay=(df["time_in_hospital"] >= 7).astype(int)), "long_stay",
                             "LOS ≥ 7 days", "LOS < 7 days"),
             two_group_rates(df.assign(older=(df["age_mid"] >= 65).astype(int)), "older", "Age ≥ 60",
                             "Age < 60")]
    rates_df = pd.DataFrame(rates)
    rates_df["p_holm"] = multipletests(rates_df["p_value"], method="holm")[1]
    rates_df.to_csv(TABLE_DIR / "stats_two_group_comparisons.csv", index=False)
    kw = kruskal_los(df)
    sp = spearman_key_pairs(df)
    sp.to_csv(TABLE_DIR / "stats_spearman_pairs.csv", index=False)
    res, fit, interaction = logistic_regression(df)
    res.to_csv(TABLE_DIR / "stats_logistic_regression_or.csv", index=False)
    fig_forest(res)

    save_json({"overall_readmit30": overall, "kruskal_los": kw, "logit_fit": fit,
               "a1c_by_diagnosis_interaction": interaction,
               "two_group": {r["comparison"]: r for r in rates}}, TABLE_DIR / "stats_summary.json")
    log.info("Overall 30-day rate %.4f (%.4f-%.4f)", e / n, lo, hi)
    log.info("Chi-square:\n%s", chi[["variable", "cramers_v", "p_holm"]].to_string())
    log.info("Mann-Whitney:\n%s", num[["variable", "mean_readmitted", "mean_not_readmitted", "rank_biserial_r",
                                       "p_holm"]].to_string())
    log.info("Two-group:\n%s", rates_df[["comparison", "rate_1", "rate_0", "risk_ratio", "p_holm"]].to_string())
    log.info("KW %s", kw)
    log.info("Logit fit %s", fit)
    log.info("Interaction %s", interaction)
    log.info("ORs:\n%s", res[["term", "odds_ratio", "or_ci_low", "or_ci_high", "p_value"]].round(3).to_string())


if __name__ == "__main__":
    main()
