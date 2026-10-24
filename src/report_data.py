"""Loads every analysis result used by the weekly reports, plus formatting helpers and shared tables."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DOCS_DIR, MODEL_DIR, RAW_DIR, TABLE_DIR, load_json  # noqa: E402

AUTHOR = "Juluru Akshay"
REPO_URL = "https://github.com/AJ1206/healthcare-readmission-analytics"

src = load_json(RAW_DIR / "SOURCE_METADATA.json")
clean = load_json(TABLE_DIR / "cleaning_summary.json")
eda = load_json(TABLE_DIR / "eda_summary.json")
st = load_json(TABLE_DIR / "stats_summary.json")
mdl = load_json(MODEL_DIR / "model_metrics.json")


def T(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLE_DIR / name)


qc, issues, rules = T("data_quality_before_after.csv"), T("data_quality_issue_log.csv"), T("data_quality_validation_rules.csv")
tlog = pd.read_csv(DOCS_DIR / "transformation_log.csv")
chi, mw, two, ors, sp = (T("stats_chi_square_tests.csv"), T("stats_mann_whitney_tests.csv"),
                         T("stats_two_group_comparisons.csv"), T("stats_logistic_regression_or.csv"),
                         T("stats_spearman_pairs.csv"))
tune, test, thr, dec, sub, imp = (T("model_tuning_and_validation.csv"), T("model_test_metrics.csv"),
                                  T("model_threshold_comparison.csv"), T("model_risk_deciles.csv"),
                                  T("model_subgroup_performance.csv"), T("model_permutation_importance.csv"))
by_dis, by_ip, by_diag, util = (T("eda_readmission_by_discharge.csv"), T("eda_readmission_by_prior_inpatient.csv"),
                                T("eda_readmission_by_diagnosis.csv"), T("eda_utilisation_by_diagnosis.csv"))
miss = T("data_quality_missing_by_column_raw.csv").set_index("column")["missing_pct_raw"]
qcs = qc.set_index("metric")
RAW, CLEANED, COHORT = qc.columns[1], qc.columns[2], qc.columns[3]
ACCESS_DATE = src["accessed_utc"][:10]


def pct(x, d=1):
    return f"{100 * float(x):.{d}f}%"


def num(x, d=0):
    return f"{float(x):,.{d}f}"


def pval(p):
    p = float(p)
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def two_row(label):
    return two[two["comparison"].str.startswith(label)].iloc[0]


ov = st["overall_readmit30"]
best = mdl["selected_model"]
m20 = mdl["test_metrics_top20"]
cal = mdl["calibration"]
tm = test.set_index("model")
base_ip = tm.loc["Baseline: prior inpatient count (1-variable LR)"]
orr = ors.set_index("term")
inter = st["a1c_by_diagnosis_interaction"]
ip, fac, a1c, los7, old = (two_row("≥1 prior"), two_row("Discharged to a care facility"), two_row("HbA1c measured"),
                           two_row("LOS ≥ 7"), two_row("Age ≥ 60"))
dis = by_dis.set_index("discharge_group")
OR_REHAB = orr.loc["discharge_group = Other inpatient / rehab facility", "odds_ratio"]
OR_SNF = orr.loc["discharge_group = Skilled nursing / ICF", "odds_ratio"]
OR_IP = orr.loc["number_inpatient", "odds_ratio"]

# ------------------------------------------------------------------ shared tables
RISKS = pd.DataFrame([
    ["RK1", "Chosen dataset becomes inaccessible or licence changes", 1, 3, "Download early; keep checksummed raw copy; record licence", "Switch to verified alternative (CMS HRRP, hospital-level redesign)", "Analyst"],
    ["RK2", "Data quality too poor for the objectives", 2, 3, "Profile in Week 2 before committing to analyses", "Narrow scope; drop unusable fields; document", "Analyst"],
    ["RK3", "Target leakage inflates model performance", 2, 3, "Exclude outcome-derived fields; pipelines; patient-level split", "Re-run with stricter feature set; external review", "Analyst / reviewer"],
    ["RK4", "Repeated encounters violate independence", 3, 2, "One index encounter per patient", "Grouped cross-validation by patient", "Analyst"],
    ["RK5", "Associations misread as causes", 2, 3, "Explicit causal caveats; alternative explanations", "Clinical review before dissemination", "Analyst / supervisor"],
    ["RK6", "Model used for individual clinical decisions", 1, 3, "'Educational use' labels; deployment conditions", "Withdraw artefact; escalate to governance", "Supervisor"],
    ["RK7", "Bias against patient subgroups", 2, 3, "Exclude race/payer as predictors; subgroup audit", "Re-weighting or adjusted thresholds after review", "Ethics committee"],
    ["RK8", "Privacy breach or re-identification", 1, 3, "Aggregates only; small-cell suppression; no linkage", "Incident response; notify data protection officer", "Data protection officer"],
    ["RK9", "Tool unavailable (e.g. Power BI licence)", 2, 2, "Open-source alternatives identified in advance", "HTML dashboard + Power BI build pack", "Analyst"],
    ["RK10", "Schedule overrun", 2, 2, "Weekly milestones; scripted pipeline", "Drop optional analyses (extra models)", "Intern / supervisor"],
    ["RK11", "Results not reproducible", 1, 3, "Fixed seeds; pinned packages; scripted steps", "Re-run from raw; compare checksums", "Reviewer"],
], columns=["ID", "Risk", "Likelihood (1-3)", "Impact (1-3)", "Mitigation (preventive)", "Contingency (if it occurs)", "Owner"])
RISKS.insert(4, "Score", RISKS["Likelihood (1-3)"] * RISKS["Impact (1-3)"])
RISK_POINTS = [(r.ID, int(r["Likelihood (1-3)"]), int(r["Impact (1-3)"])) for _, r in RISKS.iterrows()]

KPIS = pd.DataFrame([
    ["30-day readmission rate", "Readmissions < 30 days ÷ eligible index discharges", "Quality outcome", pct(ov["rate"])],
    ["Any-time readmission rate", "Readmissions (any time) ÷ eligible discharges", "Outcome", pct(eda["readmit_any_rate_cohort"])],
    ["In-hospital mortality (encounters)", "Expired dispositions ÷ all encounters", "Outcome", pct(eda["expired_all_encounters"] / eda["all_encounters_n"], 2)],
    ["Average length of stay", "Σ inpatient days ÷ patients", "Utilisation", f"{eda['mean_los']:.2f} days"],
    ["Total bed-days", "Σ inpatient days", "Utilisation", num(eda["total_bed_days_cohort"])],
    ["Medications per stay", "Σ distinct medications ÷ patients", "Utilisation", f"{eda['mean_meds']:.1f}"],
    ["Laboratory procedures per stay", "Σ lab procedures ÷ patients", "Utilisation", f"{eda['mean_labs']:.1f}"],
    ["HbA1c testing rate", "Patients with HbA1c measured ÷ patients", "Care process", pct(eda["a1c_measured_rate"])],
    ["Discharge-to-home rate", "Discharged home (± home health) ÷ patients", "Patient flow", pct(eda["discharged_home_pct"])],
    ["Prior-year inpatient share", "Patients with ≥ 1 prior admission ÷ patients", "Risk mix", pct(eda["prior_inpatient_rate"])],
    ["Facility-discharge readmission rate", "Readmissions < 30 d among facility discharges ÷ those discharges", "Quality", pct(fac["rate_1"])],
    ["Data completeness", "Non-missing cells ÷ all cells", "Data quality", f"{qcs.loc['completeness_pct_cells', CLEANED]:.1f}%"],
    ["Model discrimination (ROC-AUC)", "Area under ROC curve on held-out patients", "Model", f"{mdl['test_roc_auc']:.3f}"],
    ["Readmissions captured (top 20% risk)", "True positives ÷ all readmissions at threshold", "Model", pct(m20["recall_sensitivity"])],
], columns=["KPI", "Formula", "Type", "Baseline value (from project data)"])

REFS = {
    "clore": "Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). Diabetes 130-US hospitals for years 1999–2008 [Data set]. UCI Machine Learning Repository. https://doi.org/10.24432/C5230J",
    "strack": "Strack, B., DeShazo, J. P., Gennings, C., Olmo, J. L., Ventura, S., Cios, K. J., & Clore, J. N. (2014). Impact of HbA1c measurement on hospital readmission rates: Analysis of 70,000 clinical database patient records. BioMed Research International, 2014, 781670. https://doi.org/10.1155/2014/781670",
    "cms": "Centers for Medicare & Medicaid Services. (2026). Hospital Readmissions Reduction Program [Data set]. Provider Data Catalog. https://data.cms.gov/provider-data/dataset/9n3s-kdb3",
    "jencks": "Jencks, S. F., Williams, M. V., & Coleman, E. A. (2009). Rehospitalizations among patients in the Medicare fee-for-service program. New England Journal of Medicine, 360(14), 1418–1428. https://doi.org/10.1056/NEJMsa0803563",
    "raghupathi": "Raghupathi, W., & Raghupathi, V. (2014). Big data analytics in healthcare: Promise and potential. Health Information Science and Systems, 2, 3. https://doi.org/10.1186/2047-2501-2-3",
    "wirth": "Wirth, R., & Hipp, J. (2000). CRISP-DM: Towards a standard process model for data mining. In Proceedings of the 4th International Conference on the Practical Applications of Knowledge Discovery and Data Mining (pp. 29–39).",
    "kahn": "Kahn, M. G., Callahan, T. J., Barnard, J., Bauck, A. E., Brown, J., Davidson, B. N., Estiri, H., Goerg, C., Holve, E., Johnson, S. G., Liaw, S.-T., Hamilton-Lopez, M., Meeker, D., Ong, T. C., Ryan, P., Shang, N., Weiskopf, N. G., Weng, C., Zozus, M. N., & Schilling, L. (2016). A harmonized data quality assessment terminology and framework for the secondary use of electronic health record data. eGEMs, 4(1), 1244. https://doi.org/10.13063/2327-9214.1244",
    "weiskopf": "Weiskopf, N. G., & Weng, C. (2013). Methods and dimensions of electronic health record data quality assessment: Enabling reuse for clinical research. Journal of the American Medical Informatics Association, 20(1), 144–151. https://doi.org/10.1136/amiajnl-2011-000681",
    "wang": "Wang, R. Y., & Strong, D. M. (1996). Beyond accuracy: What data quality means to data consumers. Journal of Management Information Systems, 12(4), 5–33. https://doi.org/10.1080/07421222.1996.11518099",
    "rubin": "Rubin, D. B. (1976). Inference and missing data. Biometrika, 63(3), 581–592. https://doi.org/10.1093/biomet/63.3.581",
    "white": "White, I. R., Royston, P., & Wood, A. M. (2011). Multiple imputation using chained equations: Issues and guidance for practice. Statistics in Medicine, 30(4), 377–399. https://doi.org/10.1002/sim.4067",
    "hhs": "U.S. Department of Health and Human Services. (2012). Guidance regarding methods for de-identification of protected health information in accordance with the Health Insurance Portability and Accountability Act (HIPAA) Privacy Rule. https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html",
    "meity": "Ministry of Electronics and Information Technology. (2025). Digital Personal Data Protection Rules, 2025 (notified 14 November 2025). Government of India. https://www.meity.gov.in/",
    "nha": "National Health Authority. (2020). Health data management policy: Ayushman Bharat Digital Mission. Government of India. https://abdm.gov.in/",
    "icmr": "Indian Council of Medical Research. (2023). Ethical guidelines for application of artificial intelligence in biomedical research and healthcare. https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare",
    "who": "World Health Organization. (2021). Ethics and governance of artificial intelligence for health: WHO guidance. https://www.who.int/publications/i/item/9789240029200",
    "tripod": "Collins, G. S., Moons, K. G. M., Dhiman, P., Riley, R. D., Beam, A. L., Van Calster, B., Ghassemi, M., Liu, X., Reitsma, J. B., van Smeden, M., Boulesteix, A.-L., Camaradou, J. C., Celi, L. A., Denaxas, S., Denniston, A. K., Glocker, B., Golub, R. M., Harvey, H., Heinze, G., … Logullo, P. (2024). TRIPOD+AI statement: Updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ, 385, e078378. https://doi.org/10.1136/bmj-2023-078378",
    "vancalster": "Van Calster, B., McLernon, D. J., van Smeden, M., Wynants, L., & Steyerberg, E. W. (2019). Calibration: The Achilles heel of predictive analytics. BMC Medicine, 17, 230. https://doi.org/10.1186/s12916-019-1466-7",
    "steyerberg": "Steyerberg, E. W. (2019). Clinical prediction models: A practical approach to development, validation, and updating (2nd ed.). Springer. https://doi.org/10.1007/978-3-030-16399-0",
    "hastie": "Hastie, T., Tibshirani, R., & Friedman, J. (2009). The elements of statistical learning: Data mining, inference, and prediction (2nd ed.). Springer. https://doi.org/10.1007/978-0-387-84858-7",
    "kaufman": "Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in data mining: Formulation, detection, and avoidance. ACM Transactions on Knowledge Discovery from Data, 6(4), 1–21. https://doi.org/10.1145/2382577.2382579",
    "vickers": "Vickers, A. J., & Elkin, E. B. (2006). Decision curve analysis: A novel method for evaluating prediction models. Medical Decision Making, 26(6), 565–574. https://doi.org/10.1177/0272989X06295361",
    "obermeyer": "Obermeyer, Z., Powers, B., Vogeli, C., & Mullainathan, S. (2019). Dissecting racial bias in an algorithm used to manage the health of populations. Science, 366(6464), 447–453. https://doi.org/10.1126/science.aax2342",
    "rajkomar": "Rajkomar, A., Hardt, M., Howell, M. D., Corrado, G., & Chin, M. H. (2018). Ensuring fairness in machine learning to advance health equity. Annals of Internal Medicine, 169(12), 866–872. https://doi.org/10.7326/M18-1990",
    "saito": "Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLOS ONE, 10(3), e0118432. https://doi.org/10.1371/journal.pone.0118432",
    "holm": "Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65–70.",
    "kansagara": "Kansagara, D., Englander, H., Salanitro, A., Kagen, D., Theobald, C., Freeman, M., & Kripalani, S. (2011). Risk prediction models for hospital readmission: A systematic review. JAMA, 306(15), 1688–1698. https://doi.org/10.1001/jama.2011.1515",
    "jack": "Jack, B. W., Chetty, V. K., Anthony, D., Greenwald, J. L., Sanchez, G. M., Johnson, A. E., Forsythe, S. R., O'Donnell, J. K., Paasche-Orlow, M. K., Manasseh, C., Martin, S., & Culpepper, L. (2009). A reengineered hospital discharge program to decrease rehospitalization: A randomized trial. Annals of Internal Medicine, 150(3), 178–187. https://doi.org/10.7326/0003-4819-150-3-200902030-00007",
    "leppin": "Leppin, A. L., Gionfriddo, M. R., Kessler, M., Brito, J. P., Mair, F. S., Gallacher, K., Wang, Z., Erwin, P. J., Sylvester, T., Boehmer, K., Ting, H. H., Murad, M. H., Shippee, N. D., & Montori, V. M. (2014). Preventing 30-day hospital readmissions: A systematic review and meta-analysis of randomized trials. JAMA Internal Medicine, 174(7), 1095–1107. https://doi.org/10.1001/jamainternmed.2014.1608",
    "naylor": "Naylor, M. D., Brooten, D., Campbell, R., Jacobsen, B. S., Mezey, M. D., Pauly, M. V., & Schwartz, J. S. (1999). Comprehensive discharge planning and home follow-up of hospitalized elders: A randomized clinical trial. JAMA, 281(7), 613–620. https://doi.org/10.1001/jama.281.7.613",
    "cleveland": "Cleveland, W. S., & McGill, R. (1984). Graphical perception: Theory, experimentation, and application to the development of graphical methods. Journal of the American Statistical Association, 79(387), 531–554. https://doi.org/10.1080/01621459.1984.10478080",
    "tufte": "Tufte, E. R. (2001). The visual display of quantitative information (2nd ed.). Graphics Press.",
    "knaflic": "Knaflic, C. N. (2015). Storytelling with data: A data visualization guide for business professionals. Wiley.",
    "wcag": "World Wide Web Consortium. (2023). Web Content Accessibility Guidelines (WCAG) 2.2 (W3C Recommendation). https://www.w3.org/TR/WCAG22/",
    "mckinney": "McKinney, W. (2010). Data structures for statistical computing in Python. In S. van der Walt & J. Millman (Eds.), Proceedings of the 9th Python in Science Conference (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a",
    "pedregosa": "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
    "wilson": "Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22(158), 209–212. https://doi.org/10.1080/01621459.1927.10502953",
}
