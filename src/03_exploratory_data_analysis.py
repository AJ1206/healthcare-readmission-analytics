"""Step 3 - Exploratory data analysis: descriptive tables and figures.

All figures are computed from the cleaned data. The analysis cohort (one index
encounter per patient, excluding deaths and hospice discharges) is used unless a
figure states otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN_CSV, FIG_DIR, INDEX_COHORT_CSV, TABLE_DIR, get_logger, save_json  # noqa: E402
from viz_style import (BASE, HIGHLIGHT, INK_2, MUTED, NEUTRAL_BAR, ORDINAL_BLUE, SERIES, SEQUENTIAL,  # noqa: E402
                       DIVERGING, finish, rate_barh, rate_table, subtitle)

log = get_logger("eda")

NUMERIC = ["age_mid", "time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
           "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses",
           "n_diabetes_meds", "n_med_dose_changes"]
CATEGORICAL = ["age_group", "gender", "race", "admission_type_grp", "admission_source_grp", "discharge_group",
               "diag_1_group", "A1C_result", "glucose_serum", "insulin", "change", "diabetesMed",
               "medical_specialty_grp", "payer_code", "readmitted"]
AGE_ORDER = ["0–10", "10–20", "20–30", "30–40", "40–50", "50–60", "60–70", "70–80", "80–90", "90–100"]


def descriptive_tables(cohort: pd.DataFrame, full: pd.DataFrame) -> dict:
    desc = cohort[NUMERIC].describe(percentiles=[0.25, 0.5, 0.75]).T
    desc["skew"] = cohort[NUMERIC].skew()
    desc.round(3).to_csv(TABLE_DIR / "eda_numeric_descriptives.csv")

    freq = []
    for col in CATEGORICAL:
        vc = cohort[col].value_counts()
        for lvl, n in vc.items():
            freq.append({"variable": col, "level": lvl, "n": int(n), "pct": round(100 * n / len(cohort), 2)})
    pd.DataFrame(freq).to_csv(TABLE_DIR / "eda_categorical_frequencies.csv", index=False)

    by_outcome = cohort.groupby("readmit_30")[NUMERIC].agg(["mean", "median"]).T.round(3)
    by_outcome.columns = ["Not readmitted <30d", "Readmitted <30d"]
    by_outcome.to_csv(TABLE_DIR / "eda_numeric_by_outcome.csv")

    summary = {
        "cohort_n": len(cohort), "all_encounters_n": len(full), "patients_all": int(full["patient_nbr"].nunique()),
        "readmit30_rate_cohort": float(cohort["readmit_30"].mean()),
        "readmit_any_rate_cohort": float(cohort["readmit_any"].mean()),
        "readmit30_rate_all_encounters": float(full["readmit_30"].mean()),
        "mean_los": float(cohort["time_in_hospital"].mean()), "median_los": float(cohort["time_in_hospital"].median()),
        "total_bed_days_cohort": int(cohort["time_in_hospital"].sum()),
        "mean_meds": float(cohort["num_medications"].mean()), "mean_labs": float(cohort["num_lab_procedures"].mean()),
        "a1c_measured_rate": float(cohort["A1C_measured"].mean()),
        "glucose_measured_rate": float((cohort["glucose_serum"] != "Not measured").mean()),
        "prior_inpatient_rate": float(cohort["any_prior_inpatient"].mean()),
        "female_pct": float((cohort["gender"] == "Female").mean()),
        "age_60plus_pct": float((cohort["age_mid"] >= 65).mean()),
        "medication_change_rate": float((cohort["change"] == "Ch").mean()),
        "diabetes_med_rate": float((cohort["diabetesMed"] == "Yes").mean()),
        "insulin_rate": float((cohort["insulin"] != "No").mean()),
        "discharged_home_pct": float(cohort["discharge_group"].isin(["Home", "Home with health service"]).mean()),
        "expired_all_encounters": int((full["discharge_group"] == "Expired").sum()),
        "hospice_all_encounters": int((full["discharge_group"] == "Hospice").sum()),
        "encounters_per_patient_mean": float(len(full) / full["patient_nbr"].nunique()),
        "max_encounters_one_patient": int(full.groupby("patient_nbr").size().max()),
        "readmit30_rate_repeat_encounters": float(full.loc[full["encounter_seq"] > 1, "readmit_30"].mean()),
        "emergency_admission_pct": float((cohort["admission_type_grp"] == "Emergency").mean()),
    }
    save_json(summary, TABLE_DIR / "eda_summary.json")
    return summary


# ------------------------------------------------------------------ figures
def fig_missingness() -> None:
    m = pd.read_csv(TABLE_DIR / "data_quality_missing_by_column_raw.csv")
    m = m[m["missing_pct_raw"] > 0].sort_values("missing_pct_raw", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = [HIGHLIGHT if v > 40 else BASE for v in m["missing_pct_raw"]]
    ax.barh(m["column"], m["missing_pct_raw"], color=colors, height=0.6)
    for y, v in enumerate(m["missing_pct_raw"]):
        ax.text(v + 1, y, f"{v:.1f}%", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(40, color=INK_2, lw=1, ls=(0, (1, 2)))
    ax.text(40.5, len(m) - 0.6, "40% acceptance threshold", fontsize=8, color=INK_2)
    ax.set_xlim(0, 110)
    ax.set_xlabel("Share of encounters missing or missing-coded (%)")
    ax.grid(axis="y", visible=False)
    ax.set_title("Missing data by column in the raw dataset")
    subtitle(ax, "Columns with any missing value; weight and medical specialty exceed the 40% threshold")
    finish(fig, FIG_DIR / "fig01_missing_by_column.png", source="Source: UCI Diabetes 130-US Hospitals, raw file "
           "(n = 101,766 encounters). Missing = '?', 'Unknown/Invalid', or NULL/Not Available/Not Mapped codes.")


def fig_missing_pattern() -> None:
    s = pd.read_csv(TABLE_DIR / "missing_pattern_sample.csv")
    s = s.loc[:, s.mean() > 0]
    s = s[s.mean().sort_values(ascending=False).index]
    s = s.sort_values(list(s.columns)).astype(int)
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.imshow(s.T.values, aspect="auto", cmap=plt.matplotlib.colors.ListedColormap(["#eef4fc", "#1c5cab"]),
              interpolation="nearest")
    ax.set_yticks(range(s.shape[1]), s.columns, fontsize=8.5)
    ax.set_xlabel("Encounters (random sample of 2,000, sorted by missingness pattern)")
    ax.set_xticks([])
    ax.grid(False)
    ax.set_title("Missing-data pattern")
    subtitle(ax, "Dark = missing. Weight is almost always missing; payer and specialty gaps co-occur only partly")
    finish(fig, FIG_DIR / "fig02_missing_pattern.png", source="Source: UCI Diabetes 130-US Hospitals, raw file; "
           "random sample (seed = 1).")


def fig_outcome(cohort: pd.DataFrame, full: pd.DataFrame) -> None:
    order = ["NO", "<30", ">30"]
    labels = {"NO": "Not readmitted", "<30": "Readmitted within 30 days", ">30": "Readmitted after 30 days"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2), sharex=True)
    for ax, (name, d) in zip(axes, [("Analysis cohort (index encounters)", cohort), ("All encounters", full)]):
        vc = d["readmitted"].value_counts(normalize=True).reindex(order)
        colors = [NEUTRAL_BAR, HIGHLIGHT, BASE]
        ax.barh([labels[o] for o in order], vc.values, color=colors, height=0.6)
        for y, v in enumerate(vc.values):
            ax.text(v + 0.01, y, f"{v:.1%}", va="center", fontsize=9, color=INK_2)
        ax.invert_yaxis()
        ax.set_xlim(0, 0.85)
        ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.grid(axis="y", visible=False)
        ax.set_title(f"{name}, n = {len(d):,}", fontsize=10.5)
    axes[1].set_yticklabels([])
    fig.suptitle("Readmission outcome distribution", x=0.0, ha="left", fontsize=12, fontweight="bold", y=1.13)
    finish(fig, FIG_DIR / "fig03_outcome_distribution.png")


def fig_age(cohort: pd.DataFrame, overall: float) -> None:
    tbl = rate_table(cohort, "age_band", order=AGE_ORDER)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    ax = axes[0]
    ax.bar(tbl.index, tbl["n"], color=BASE, width=0.7)
    ax.set_title("Patients by age band")
    ax.set_ylabel("Patients (index encounters)")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax = axes[1]
    x = np.arange(len(tbl))
    ax.errorbar(x, tbl["rate"], yerr=[tbl["rate"] - tbl["ci_low"], tbl["ci_high"] - tbl["rate"]], fmt="o-",
                color=BASE, ecolor=INK_2, elinewidth=1, capsize=2.5, lw=2, ms=6)
    ax.axhline(overall, color=INK_2, lw=1, ls=(0, (1, 2)))
    ax.text(0, overall + 0.003, f"overall {overall:.1%}", fontsize=8, color=INK_2)
    ax.set_xticks(x, tbl.index, rotation=45)
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("30-day readmission rate (95% CI)")
    ax.set_title("30-day readmission rate by age band")
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Age band (years); bands under 30 years are small, so intervals are wide")
    axes[0].set_xlabel("Age band (years)")
    finish(fig, FIG_DIR / "fig04_age_distribution_readmission.png")


def fig_by_group(cohort, overall, col, title, sub, fname, highlight=None, min_n=100) -> pd.DataFrame:
    tbl = rate_table(cohort, col, min_n=min_n).sort_values("rate", ascending=False)
    fig, ax = plt.subplots(figsize=(8.5, 0.42 * len(tbl) + 1.4))
    rate_barh(ax, tbl, overall=overall, highlight=highlight)
    ax.set_title(title)
    subtitle(ax, sub)
    finish(fig, FIG_DIR / fname)
    return tbl


def fig_los(cohort: pd.DataFrame, overall: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    ax = axes[0]
    counts = cohort["time_in_hospital"].value_counts().sort_index()
    ax.bar(counts.index, counts.values, color=BASE, width=0.75)
    ax.axvline(cohort["time_in_hospital"].mean(), color=HIGHLIGHT, lw=1.5)
    ax.text(cohort["time_in_hospital"].mean() + 0.2, counts.max() * 0.95,
            f"mean {cohort['time_in_hospital'].mean():.2f} days\nmedian {cohort['time_in_hospital'].median():.0f} days",
            fontsize=8.5, color=INK_2, va="top")
    ax.set_xlabel("Length of stay (days)")
    ax.set_ylabel("Patients")
    ax.set_xticks(range(1, 15))
    ax.set_title("Length-of-stay distribution")
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax = axes[1]
    tbl = rate_table(cohort, "time_in_hospital")
    ax.errorbar(tbl.index, tbl["rate"], yerr=[tbl["rate"] - tbl["ci_low"], tbl["ci_high"] - tbl["rate"]],
                fmt="o-", color=BASE, ecolor=INK_2, elinewidth=1, capsize=2.5, lw=2, ms=6)
    ax.axhline(overall, color=INK_2, lw=1, ls=(0, (1, 2)))
    ax.set_xticks(range(1, 15))
    ax.set_xlabel("Length of stay (days)")
    ax.set_ylabel("30-day readmission rate (95% CI)")
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_title("Readmission rate by length of stay")
    ax.grid(axis="x", visible=False)
    finish(fig, FIG_DIR / "fig06_length_of_stay.png")


def fig_prior_inpatient(cohort: pd.DataFrame, overall: float) -> pd.DataFrame:
    d = cohort.assign(prior_ip=cohort["number_inpatient"].clip(upper=5).map(lambda v: "5+" if v == 5 else str(v)))
    tbl = rate_table(d, "prior_ip", order=["0", "1", "2", "3", "4", "5+"])
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    x = np.arange(len(tbl))
    ax.bar(x, tbl["rate"], color=ORDINAL_BLUE + [ORDINAL_BLUE[-1]], width=0.62)
    ax.errorbar(x, tbl["rate"], yerr=[tbl["rate"] - tbl["ci_low"], tbl["ci_high"] - tbl["rate"]], fmt="none",
                ecolor=INK_2, elinewidth=1, capsize=3)
    for xi, (_, r) in zip(x, tbl.iterrows()):
        ax.text(xi, r["ci_high"] + 0.006, f"{r['rate']:.1%}\nn={int(r['n']):,}", ha="center", fontsize=8.5,
                color=INK_2)
    ax.axhline(overall, color=INK_2, lw=1, ls=(0, (1, 2)))
    ax.set_xticks(x, tbl.index)
    ax.set_xlabel("Inpatient admissions in the year before the index encounter")
    ax.set_ylabel("30-day readmission rate (95% CI)")
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, tbl["ci_high"].max() * 1.3)
    ax.grid(axis="x", visible=False)
    ax.set_title("Prior inpatient use and 30-day readmission")
    subtitle(ax, "Readmission risk rises steadily with the number of prior-year admissions")
    finish(fig, FIG_DIR / "fig07_prior_inpatient.png")
    return tbl


def fig_a1c(cohort: pd.DataFrame, overall: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    t = cohort.groupby("diag_1_group")["A1C_measured"].agg(["mean", "count"]).sort_values("mean")
    t = t[t["count"] >= 100]
    ax.barh(t.index, t["mean"], color=BASE, height=0.6)
    for y, (idx, r) in enumerate(t.iterrows()):
        ax.text(r["mean"] + 0.005, y, f"{r['mean']:.1%}", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(cohort["A1C_measured"].mean(), color=INK_2, lw=1, ls=(0, (1, 2)))
    ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, t["mean"].max() * 1.25)
    ax.set_xlabel("Share of patients with HbA1c measured")
    ax.grid(axis="y", visible=False)
    ax.set_title("HbA1c testing rate by primary diagnosis")
    ax = axes[1]
    tbl = rate_table(cohort, "A1C_result", order=["Not measured", "Norm", ">7", ">8"])
    rate_barh(ax, tbl, overall=overall)
    ax.set_title("30-day readmission by HbA1c result")
    finish(fig, FIG_DIR / "fig09_hba1c.png")


def fig_correlation(cohort: pd.DataFrame) -> pd.DataFrame:
    cols = NUMERIC + ["readmit_30"]
    corr = cohort[cols].corr(method="spearman")
    corr.round(3).to_csv(TABLE_DIR / "eda_spearman_correlation.csv")
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    fig, ax = plt.subplots(figsize=(8.5, 7))
    sns.heatmap(corr, mask=mask, cmap=DIVERGING, vmin=-1, vmax=1, center=0, annot=True, fmt=".2f",
                annot_kws={"fontsize": 7.5}, linewidths=1.5, linecolor="#fcfcfb", square=True,
                cbar_kws={"shrink": 0.7, "label": "Spearman ρ"}, ax=ax)
    ax.grid(False)
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    ax.set_title("Spearman correlations among numeric variables and the outcome")
    finish(fig, FIG_DIR / "fig10_correlation_heatmap.png")
    return corr


def fig_utilisation(cohort: pd.DataFrame) -> pd.DataFrame:
    grp = cohort.groupby("diag_1_group").agg(patients=("encounter_id", "size"),
                                             mean_los=("time_in_hospital", "mean"),
                                             median_los=("time_in_hospital", "median"),
                                             bed_days=("time_in_hospital", "sum"),
                                             mean_labs=("num_lab_procedures", "mean"),
                                             mean_meds=("num_medications", "mean"),
                                             mean_procedures=("num_procedures", "mean"),
                                             readmit30_rate=("readmit_30", "mean"))
    grp["bed_day_share"] = grp["bed_days"] / grp["bed_days"].sum()
    grp = grp[grp["patients"] >= 100]  # suppress tiny groups (e.g. missing diagnosis)
    grp = grp.sort_values("bed_days", ascending=False)
    grp.round(4).to_csv(TABLE_DIR / "eda_utilisation_by_diagnosis.csv")

    order = grp.index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axes[0]
    ax.barh(order, grp["bed_day_share"], color=BASE, height=0.6)
    for y, v in enumerate(grp["bed_day_share"]):
        ax.text(v + 0.004, y, f"{v:.1%}", va="center", fontsize=8.5, color=INK_2)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlim(0, grp["bed_day_share"].max() * 1.2)
    ax.set_xlabel("Share of total bed-days")
    ax.grid(axis="y", visible=False)
    ax.set_title("Bed-day consumption by primary diagnosis")
    ax = axes[1]
    sns.boxplot(data=cohort[cohort["diag_1_group"].isin(order)], y="diag_1_group", x="time_in_hospital", order=order, color="#b7d3f6",
                linewidth=1, fliersize=0, width=0.55, medianprops={"color": "#104281", "linewidth": 2},
                whiskerprops={"color": INK_2}, capprops={"color": INK_2}, boxprops={"edgecolor": INK_2}, ax=ax)
    ax.scatter(grp["mean_los"], range(len(order)), color=HIGHLIGHT, zorder=3, s=28, label="Mean")
    ax.set_ylabel("")
    ax.set_yticklabels([])
    ax.set_xlabel("Length of stay (days)")
    ax.set_title("Length of stay by primary diagnosis")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="y", visible=False)
    finish(fig, FIG_DIR / "fig11_utilisation_by_diagnosis.png")
    return grp


def fig_demographics(cohort: pd.DataFrame, overall: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.6), gridspec_kw={"width_ratios": [1.4, 1]})
    rate_barh(axes[0], rate_table(cohort, "race").sort_values("rate", ascending=False), overall=overall)
    axes[0].set_title("By recorded race")
    rate_barh(axes[1], rate_table(cohort, "gender"), overall=overall)
    axes[1].set_title("By gender")
    fig.suptitle("30-day readmission across demographic subgroups", x=0.0, ha="left", fontsize=12,
                 fontweight="bold", y=1.13)
    finish(fig, FIG_DIR / "fig12_demographic_subgroups.png")


def main() -> None:
    full = pd.read_csv(CLEAN_CSV, low_memory=False)
    cohort = pd.read_csv(INDEX_COHORT_CSV, low_memory=False)
    summary = descriptive_tables(cohort, full)
    overall = summary["readmit30_rate_cohort"]

    fig_missingness()
    fig_missing_pattern()
    fig_outcome(cohort, full)
    fig_age(cohort, overall)
    t_diag = fig_by_group(cohort, overall, "diag_1_group", "30-day readmission by primary diagnosis group",
                          "ICD-9 groups; bars show Wilson 95% confidence intervals",
                          "fig05_readmission_by_diagnosis.png")
    fig_los(cohort, overall)
    t_ip = fig_prior_inpatient(cohort, overall)
    t_dis = fig_by_group(cohort, overall, "discharge_group", "30-day readmission by discharge destination",
                         "Groups with at least 100 patients; transfers to facilities carry the highest risk",
                         "fig08_readmission_by_discharge.png")
    fig_a1c(cohort, overall)
    fig_correlation(cohort)
    fig_utilisation(cohort)
    fig_demographics(cohort, overall)

    for name, t in [("diagnosis", t_diag), ("prior_inpatient", t_ip), ("discharge", t_dis)]:
        t.round(4).to_csv(TABLE_DIR / f"eda_readmission_by_{name}.csv")
    for col in ["age_band", "age_group", "race", "gender", "admission_type_grp", "admission_source_grp",
                "A1C_result", "medical_specialty_grp", "payer_code", "insulin", "change", "time_in_hospital"]:
        rate_table(cohort, col).round(4).to_csv(TABLE_DIR / f"eda_readmission_by_{col}.csv")
    log.info("EDA complete. Cohort 30-day rate %.4f", overall)


if __name__ == "__main__":
    main()
