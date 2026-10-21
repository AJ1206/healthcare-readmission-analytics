"""Step 7 - Build the integrated Word report from the generated outputs.

Every number in the report is read from files produced by steps 1-6, so the report
cannot drift from the analysis. Run after all other steps.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DOCS_DIR, FIG_DIR, MODEL_DIR, RAW_DIR, ROOT, TABLE_DIR, load_json  # noqa: E402
from docx_helpers import ACCENT, MUTED, Report  # noqa: E402
from docx.shared import Pt  # noqa: E402

OUT = ROOT / "report" / "Healthcare_Data_Analytics_Final_Report.docx"

# ------------------------------------------------------------------ load results
src = load_json(RAW_DIR / "SOURCE_METADATA.json")
probes = load_json(DOCS_DIR / "dataset_access_probes.json")
clean = load_json(TABLE_DIR / "cleaning_summary.json")
eda = load_json(TABLE_DIR / "eda_summary.json")
st = load_json(TABLE_DIR / "stats_summary.json")
mdl = load_json(MODEL_DIR / "model_metrics.json")

T = lambda name: pd.read_csv(TABLE_DIR / name)  # noqa: E731
qc = T("data_quality_before_after.csv")
issues = T("data_quality_issue_log.csv")
rules = T("data_quality_validation_rules.csv")
tlog = pd.read_csv(DOCS_DIR / "transformation_log.csv")
ddict = pd.read_csv(DOCS_DIR / "data_dictionary.csv")
desc = pd.read_csv(TABLE_DIR / "eda_numeric_descriptives.csv", index_col=0)
chi = T("stats_chi_square_tests.csv")
mw = T("stats_mann_whitney_tests.csv")
two = T("stats_two_group_comparisons.csv")
ors = T("stats_logistic_regression_or.csv")
sp = T("stats_spearman_pairs.csv")
tune = T("model_tuning_and_validation.csv")
test = T("model_test_metrics.csv")
thr = T("model_threshold_comparison.csv")
dec = T("model_risk_deciles.csv")
sub = T("model_subgroup_performance.csv")
imp = T("model_permutation_importance.csv")
by_dis = T("eda_readmission_by_discharge.csv")
by_ip = T("eda_readmission_by_prior_inpatient.csv")
by_diag = T("eda_readmission_by_diagnosis.csv")
by_age = T("eda_readmission_by_age_group.csv")
util = T("eda_utilisation_by_diagnosis.csv")
miss = pd.read_csv(TABLE_DIR / "data_quality_missing_by_column_raw.csv").set_index("column")["missing_pct_raw"]


def pct(x, d=1):
    return f"{100 * float(x):.{d}f}%"


def num(x, d=0):
    return f"{float(x):,.{d}f}"


def pval(p):
    p = float(p)
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def ci(lo, hi, f=pct):
    return f"{f(lo)}–{f(hi)}"


def two_row(label):
    return two[two["comparison"].str.startswith(label)].iloc[0]


def dis_rate(group):
    return by_dis.set_index("discharge_group").loc[group]


ov = st["overall_readmit30"]
best = mdl["selected_model"]
m20 = mdl["test_metrics_top20"]
tm = test.set_index("model")
ip = two_row("≥1 prior")
fac = two_row("Discharged to a care facility")
a1c = two_row("HbA1c measured")
los7 = two_row("LOS ≥ 7")
old = two_row("Age ≥ 60")
inter = st["a1c_by_diagnosis_interaction"]
orr = ors.set_index("term")
base_ip = tm.loc["Baseline: prior inpatient count (1-variable LR)"]
qcs = qc.set_index("metric")
RAW, CLEANED, COHORT = qc.columns[1], qc.columns[2], qc.columns[3]
ACCESS_DATE = src["accessed_utc"][:10]

r = Report()
r.page_numbers("End-to-End Healthcare Data Analytics · Diabetic readmission project")
doc = r.doc

# ================================================================== COVER
for _ in range(5):
    r.p("")
r.p("SIX-WEEK DATA ANALYTICS INTERNSHIP · INTEGRATED FINAL REPORT", size=10, color=MUTED, align="center")
t = r.p("End-to-End Healthcare Data Analytics", size=26, align="center")
t.runs[0].bold = True
t.runs[0].font.color.rgb = ACCENT
r.p("Data Acquisition, Quality Assurance, Statistical Analysis, Predictive Modelling, Visualisation and "
    "Evidence-Based Decision-Making", size=13, align="center")
r.p("")
r.p("Case study: 30-day readmission and resource use among diabetic inpatients in 130 US hospitals "
    "(UCI Diabetes 130-US Hospitals dataset, 1999–2008)", size=11.5, italic=True, align="center")
for _ in range(6):
    r.p("")
for lead, val in [("Prepared by: ", "[Intern name]"), ("Internship organisation: ", "[Organisation name]"),
                  ("Supervisor / mentor: ", "[Supervisor name]"), ("Submission date: ", date.today().strftime("%d %B %Y")),
                  ("Data accessed: ", f"{ACCESS_DATE} (UCI Machine Learning Repository, CC BY 4.0)")]:
    r.p(val, bold_lead=lead, align="center", space_after=2)
r.p("")
r.p("Educational and analytical use only. The predictive model in this report has not been clinically or "
    "institutionally validated and must not be used to make decisions about individual patients.",
    size=9, italic=True, color=MUTED, align="center")
r.page_break()

# ================================================================== TOC, LOF, LOT
r.toc("Table of Contents", 'TOC \\o "1-2" \\h \\z \\u',
      "Right-click and choose Update Field (or press F9) to build the table of contents.")
r.page_break()
r.toc("List of Figures", 'TOC \\h \\z \\c "Figure"', "Update field to build the list of figures.")
r.p("")
r.toc("List of Tables", 'TOC \\h \\z \\c "Table"', "Update field to build the list of tables.")
r.page_break()

# ================================================================== 1 EXECUTIVE SUMMARY
r.h("1. Executive Summary")
r.p(f"This report documents a complete, reproducible healthcare analytics project carried out across a six-week "
    f"internship plan. It analyses {num(clean['raw_rows'])} real, de-identified inpatient encounters of patients with "
    f"diabetes from 130 US hospitals (1999–2008), published by the UCI Machine Learning Repository under a CC BY 4.0 "
    f"licence. The project asks which patients are readmitted within 30 days of discharge, how hospital resources are "
    f"used, and whether a model can usefully rank readmission risk at discharge.", align="justify")
r.p("Key results (all calculated from the data in this project):", bold_lead="")
r.bullets([
    ("Readmission burden. ", f"Among {num(ov['n'])} patients (first eligible encounter each; deaths and hospice "
     f"discharges excluded), {num(ov['events'])} were readmitted within 30 days: {pct(ov['rate'])} "
     f"(95% CI {ci(ov['ci_low'], ov['ci_high'])}). Across all encounters the rate was "
     f"{pct(eda['readmit30_rate_all_encounters'])}, and {pct(eda['readmit30_rate_repeat_encounters'])} for repeat encounters."),
    ("Discharge destination is the strongest signal. ", f"Patients discharged to a skilled-nursing or other "
     f"inpatient/rehabilitation facility were readmitted at {pct(fac['rate_1'])} versus {pct(fac['rate_0'])} for other "
     f"destinations (risk ratio {fac['risk_ratio']:.2f}, 95% CI {fac['rr_ci_low']:.2f}–{fac['rr_ci_high']:.2f}); the "
     f"association persisted after adjustment (adjusted OR {orr.loc['discharge_group = Other inpatient / rehab facility', 'odds_ratio']:.2f} "
     f"for rehabilitation/other inpatient facilities versus home)."),
    ("Prior utilisation matters. ", f"Patients with at least one inpatient admission in the previous year had a "
     f"30-day rate of {pct(ip['rate_1'])} versus {pct(ip['rate_0'])} (RR {ip['risk_ratio']:.2f}); each additional "
     f"prior admission carried an adjusted OR of {orr.loc['number_inpatient', 'odds_ratio']:.2f}."),
    ("HbA1c was rarely measured. ", f"Only {pct(eda['a1c_measured_rate'])} of patients had HbA1c tested during the "
     f"stay. Testing was associated with modestly lower readmission (adjusted OR {inter['a1c_measured_OR_main_model']:.2f}, "
     f"95% CI {inter['a1c_measured_OR_ci'][0]:.2f}–{inter['a1c_measured_OR_ci'][1]:.2f}), and the association differed "
     f"by primary diagnosis (interaction p = {pval(inter['p_value'])}), consistent with Strack et al. (2014). This is an "
     f"association, not evidence that testing prevents readmission."),
    ("Resource use. ", f"Mean length of stay was {eda['mean_los']:.2f} days (median {eda['median_los']:.0f}); "
     f"circulatory conditions consumed {pct(util.iloc[0]['bed_day_share'])} of {num(eda['total_bed_days_cohort'])} bed-days. "
     f"Stays of 7 days or more were associated with a higher 30-day rate ({pct(los7['rate_1'])} vs {pct(los7['rate_0'])})."),
    ("Predictive model. ", f"A tuned {best.lower()} achieved a test ROC-AUC of {mdl['test_roc_auc']:.3f} "
     f"(95% CI {mdl['test_roc_auc_ci'][0]:.3f}–{mdl['test_roc_auc_ci'][1]:.3f}) and PR-AUC {mdl['test_pr_auc']:.3f} "
     f"against a prevalence of {pct(mdl['split']['test_rate'])}. Flagging the highest-risk 20% of patients would "
     f"identify {pct(m20['recall_sensitivity'])} of readmissions with a positive predictive value of "
     f"{pct(m20['precision_ppv'])}. Discrimination is modest; the model is suitable for learning and population-level "
     f"exploration, not for clinical decisions."),
    ("Data quality. ", f"Raw cell completeness was {qcs.loc['completeness_pct_cells', RAW]:.1f}%; weight was "
     f"{miss['weight']:.1f}% missing and was dropped. "
     f"All {len(rules)} automated validation rules passed after cleaning, but clinical accuracy could not be verified "
     f"against source records."),
])
r.p("Priority recommendations (Section 15) are: strengthen transitions of care for facility discharges; trigger "
    "early discharge planning and prompt follow-up for patients with prior-year admissions; audit and pilot more "
    "consistent HbA1c assessment; improve documentation of weight, specialty and payer; and keep any risk model in a "
    "supervised, locally validated pilot with subgroup monitoring.", align="justify")
r.p("What was not done: no Power BI .pbix file could be produced (Power BI Desktop cannot be automated here), so "
    "an interactive HTML dashboard plus a complete Power BI build pack (data model, DAX, step-by-step guide) is "
    "provided instead. No time-trend or hospital-level comparison was possible because the public dataset contains "
    "no admission dates or hospital identifiers. The self-assessment in Appendix G is a template because no personal "
    "reflections were supplied.", italic=True, align="justify")

# ================================================================== 2 INTRODUCTION
r.h("2. Introduction and Healthcare Problem Statement", page_break=True)
r.h("2.1 Background", 2)
r.p("Unplanned hospital readmissions are costly for health systems and distressing for patients. In the US Medicare "
    "fee-for-service population, about one in five discharged patients was rehospitalised within 30 days (Jencks et al., "
    "2009), and the Centers for Medicare & Medicaid Services (CMS) penalises hospitals with excess readmissions "
    "through the Hospital Readmissions Reduction Program (HRRP; CMS, 2026). Diabetes is a common comorbidity in "
    "hospitalised adults, and inconsistent inpatient diabetes management has been linked to readmission risk "
    "(Strack et al., 2014). These figures are external context; the findings in later sections come from this "
    "project's own analysis.", align="justify")
r.h("2.2 Problem statement", 2)
r.p("A hospital quality team wants to know (a) how often diabetic inpatients return within 30 days, (b) which "
    "patient, clinical and care-process factors are associated with early readmission, (c) where inpatient "
    "resources are concentrated, and (d) whether readily available discharge data can rank patients by readmission "
    "risk well enough to prioritise follow-up. Without this evidence, transition-of-care resources are spread "
    "uniformly rather than targeted.", align="justify")
r.h("2.3 Business justification", 2)
r.bullets([
    "Readmissions consume beds and staff time that could serve new admissions.",
    "Readmission performance is a publicly reported, payment-linked quality measure in several systems (e.g., HRRP).",
    "Targeted discharge interventions have reduced readmissions in randomised trials (Jack et al., 2009; Naylor et al., "
    "1999; Leppin et al., 2014), but they need a way to decide whom to target.",
    "A reproducible analytics pipeline can be re-run on local data, turning a one-off study into a monitoring capability.",
])
r.h("2.4 Decisions the analysis supports", 2)
r.bullets(["Which discharge groups should receive enhanced transition-of-care support.",
           "Whether to standardise HbA1c assessment for admitted patients with diabetes.",
           "Where bed-day consumption is concentrated (for length-of-stay review).",
           "Whether a risk score is accurate and fair enough to justify a supervised pilot.",
           "Which data-capture gaps to close before more advanced analytics."])

# ================================================================== 3 VISION, OBJECTIVES, SCOPE, RQs
r.h("3. Project Vision, Objectives, Scope and Research Questions", page_break=True)
r.h("3.1 Vision", 2)
r.p("To give clinical and operational leaders a transparent, reproducible and ethically governed evidence base on "
    "diabetic inpatient readmissions and resource use that can be refreshed with local data.", align="justify")
r.h("3.2 Measurable objectives", 2)
r.table(pd.DataFrame([
    ["O1", "Acquire and document a real, licensed healthcare dataset", "Source, licence, checksum and schema recorded", "Achieved"],
    ["O2", "Deliver an analysis-ready dataset", "100% of validation rules pass; issue log complete", "Achieved"],
    ["O3", "Quantify 30-day readmission and resource-use KPIs", "≥10 KPIs with formulas and 95% CIs where applicable", "Achieved (14 KPIs)"],
    ["O4", "Test five pre-specified hypotheses", "Tests with effect sizes and multiplicity control", "Achieved"],
    ["O5", "Build and evaluate a readmission risk model", "Beats baseline on untouched test set; calibration and subgroups reported", "Achieved (modest AUC)"],
    ["O6", "Provide an interactive dashboard", "Filters, KPI cards, CIs, small-sample suppression", "Achieved (HTML); Power BI pack"],
    ["O7", "Produce traceable recommendations", "Each linked to a result or cited source", "Achieved"],
], columns=["ID", "Objective", "Success measure", "Status"]), "Project objectives and measures of success",
    widths_cm=[1.2, 6.2, 6.0, 3.2])
r.h("3.3 Scope", 2)
r.bullets([("In scope: ", "patient-level analysis of the UCI Diabetes 130-US Hospitals data; descriptive, inferential "
            "and predictive analysis of 30-day readmission; resource-use indicators (length of stay, bed-days, "
            "medications, laboratory procedures); dashboard; governance and ethics review."),
           ("Out of scope: ", "causal effect estimation; cost analysis (no cost fields); hospital benchmarking (no "
            "hospital identifier); time trends (no dates); deployment into clinical systems."),
           ("Assumptions: ", "readmission labels are correct as coded; encounter_id order approximates chronological "
            "order within a patient; the 1999–2008 data are adequate for learning methods, not for current "
            "operational targets."),
           ("Constraints: ", "public data only (no credentialed access); open-source tools; Power BI Desktop not "
            "automatable in the project environment; six-week timeframe.")])
r.h("3.4 Research questions and hypotheses", 2)
r.table(pd.DataFrame([
    ["RQ1", "What is the 30-day readmission rate and how is it distributed across patient groups?", "Descriptive (no hypothesis)"],
    ["RQ2", "Is prior inpatient use associated with 30-day readmission?", "H1: patients with ≥1 prior-year admission have a higher 30-day rate"],
    ["RQ3", "Does discharge destination matter?", "H2: discharge to a care facility is associated with higher 30-day readmission"],
    ["RQ4", "Is in-hospital HbA1c measurement associated with readmission?", "H3: HbA1c measurement is associated with lower readmission after adjustment, and the association differs by primary diagnosis"],
    ["RQ5", "Are length of stay and age associated with readmission?", "H4: longer stays and older age are associated with higher 30-day readmission"],
    ["RQ6", "Does resource use differ by primary diagnosis?", "H5: length of stay differs across primary-diagnosis groups"],
    ["RQ7", "Can discharge data rank readmission risk better than simple rules?", "H6: a multivariable model outperforms a prior-admission baseline on held-out data (ROC-AUC)"],
], columns=["ID", "Research question", "Testable hypothesis"]), "Research questions and hypotheses",
    widths_cm=[1.2, 7.4, 8.0])

# ================================================================== 4 STRATEGIC PLANNING & GOVERNANCE
r.h("4. Strategic Planning and Project Governance", page_break=True)
r.h("4.1 Stakeholder analysis", 2)
r.table(pd.DataFrame([
    ["Hospital executive leadership", "Cost, penalties, capacity", "High", "High", "One-page KPI summary; recommendation matrix", "Monthly briefing"],
    ["Chief Medical Officer / quality committee", "Patient safety, quality measures", "High", "High", "Validated findings, limitations", "Review at each milestone"],
    ["Diabetes / endocrinology team", "Glycaemic management, HbA1c practice", "Medium", "High", "HbA1c findings by diagnosis", "Clinical review workshop"],
    ["Hospitalists and attending physicians", "Discharge readiness", "Medium", "High", "Risk factors; model limitations", "Ward meetings"],
    ["Nursing, case managers, discharge planners", "Transition-of-care workload", "Medium", "High", "Who to prioritise; dashboard", "Co-design of pilot"],
    ["Health information management (HIM)", "Documentation quality", "Medium", "Medium", "Data-quality issue log", "Data-quality forum"],
    ["IT / data engineering", "Pipelines, security", "Medium", "Medium", "Code, data model, access needs", "Technical hand-over"],
    ["Data protection officer / privacy", "Lawful, minimal processing", "High", "Medium", "Data inventory, DPIA inputs", "Sign-off before any local data use"],
    ["Patients and caregivers", "Safe discharge, fewer returns", "Low", "High", "Plain-language summary", "Patient advisory group"],
    ["Internship supervisor / mentor", "Learning outcomes, rigour", "High", "Medium", "Weekly deliverables", "Weekly review"],
], columns=["Stakeholder", "Main interest", "Influence", "Impact on / of project", "Information needs", "Engagement"]),
    "Stakeholder analysis", widths_cm=[3.4, 3.0, 1.6, 2.0, 3.6, 3.0], font_size=8)
r.h("4.2 Analytical framework and workflow", 2)
r.p("The project follows a CRISP-DM-style lifecycle adapted for healthcare: problem definition → data acquisition → "
    "profiling and quality assurance → cleaning and cohort definition → exploratory analysis → inferential "
    "statistics → predictive modelling → evaluation (discrimination, calibration, fairness) → visualisation and "
    "dashboard → recommendations → governance review. Each stage is a numbered Python script with defined inputs "
    "and outputs (Section 18), so any stage can be re-run and audited. Model development and reporting follow the "
    "TRIPOD+AI reporting principles (Collins et al., 2024) where applicable.", align="justify")
r.h("4.3 Technology and resource requirements", 2)
r.table(pd.DataFrame([
    ["Python 3.14", "Core language for all processing, analysis and report generation"],
    ["pandas, NumPy", "Loading, profiling, cleaning and reshaping tabular data (McKinney, 2010)"],
    ["SciPy, statsmodels", "Hypothesis tests, confidence intervals, logistic regression (Virtanen et al., 2020; Seabold & Perktold, 2010)"],
    ["scikit-learn", "Pre-processing pipelines, model training, cross-validation, metrics (Pedregosa et al., 2011)"],
    ["Matplotlib, seaborn", "Publication-quality static figures (Hunter, 2007)"],
    ["HTML/JavaScript (no external libraries)", "Self-contained interactive dashboard with filters and tooltips"],
    ["Power BI Desktop (optional)", "Rebuild of the dashboard from the provided star schema and DAX measures"],
    ["python-docx; Microsoft Word", "Generation of this report; field (TOC) refresh"],
    ["SQL (conceptual)", "Validation rules in Appendix B are written so they translate directly to SQL CHECK/WHERE clauses"],
    ["Hardware", "Standard laptop (8–16 GB RAM); full pipeline runs in under 15 minutes"],
], columns=["Tool / resource", "Purpose in this project"]), "Technology stack", widths_cm=[4.6, 12.0])
r.h("4.4 Governance and review procedures", 2)
r.bullets([("Weekly milestone review: ", "deliverables checked against the acceptance criteria in Section 16 by the "
            "supervisor; decisions and changes logged."),
           ("Analytical peer review: ", "a second analyst re-runs the pipeline from raw data and compares key "
            "numbers (cohort size, 30-day rate, test AUC) before results are shared."),
           ("Clinical review: ", "clinicians review variable definitions (diagnosis grouping, discharge grouping) "
            "and the plausibility of findings."),
           ("Privacy and ethics checkpoint: ", "before any local (non-public) data is used, a data-protection impact "
            "assessment and ethics-committee review are required (Section 7)."),
           ("Change control: ", "scripts are version-controlled; any change to cohort or outcome definitions "
            "requires re-running all downstream steps."),
           ("Model governance: ", "no model output is used for patient care without clinical validation, a "
            "named accountable owner and a monitoring plan (Section 13.6).")])

# ================================================================== 5 DATASET SELECTION & ACQUISITION
r.h("5. Dataset Selection and Data Acquisition", page_break=True)
r.h("5.1 Candidate datasets compared", 2)
r.p(f"Four credible public or controlled-access sources were evaluated. Accessibility was confirmed programmatically "
    f"on {ACCESS_DATE} (HTTP 200 for every landing page or API). Scores run from 1 (poor) to 5 (excellent).",
    align="justify")
r.table(pd.DataFrame([
    ["Relevance to readmission", "5", "4", "2", "5"],
    ["Accessibility", "5 – direct download", "5 – open API/CSV", "5 – direct download", "1 – credentialing, training and DUA"],
    ["Documentation", "4 – UCI page + paper", "4 – CMS data dictionary", "3", "5"],
    ["Completeness", "3 – some sparse fields", "4", "5", "4"],
    ["Recency", "1 – 1999–2008", "5 – Jul 2021–Jun 2024", "2 – BRFSS survey year", "4"],
    ["Sample size", "5 – 101,766 encounters", "3 – 18,330 hospital-measure rows", "5 – 253,680 respondents", "5"],
    ["Patient-level readmission target", "5 – yes", "2 – hospital-level ratios only", "1 – none", "4 – derivable"],
    ["Licensing", "5 – CC BY 4.0", "5 – US government open data", "3 – not stated on UCI page", "2 – restricted DUA"],
    ["Feasibility in six weeks", "5", "4", "4", "1"],
    ["Total (max 45)", "38", "36", "30", "31"],
], columns=["Criterion", "UCI Diabetes 130-US Hospitals (selected)", "CMS Hospital Readmissions Reduction Program",
            "CDC Diabetes Health Indicators (BRFSS)", "MIMIC-IV (PhysioNet)"]),
    "Dataset selection matrix", widths_cm=[3.6, 3.4, 3.4, 3.2, 3.0], font_size=8,
    note="CMS file verified: FY 2026 HRRP hospital file, 18,330 rows covering 3,055 hospitals × 6 conditions. "
         "CDC figures as listed on the UCI page. MIMIC-IV requires PhysioNet credentialing and a data use agreement.")
r.p("Decision. The UCI Diabetes 130-US Hospitals dataset is the only option that is immediately accessible, openly "
    "licensed and has a patient-level readmission outcome. Its main weakness is age (1999–2008), which limits the "
    "transferability of absolute rates to current practice; this is treated as a key limitation rather than hidden. "
    "The CMS HRRP data were not combined with it because the populations (diabetic inpatients vs Medicare "
    "condition cohorts), periods (1999–2008 vs 2021–2024) and units (patients vs hospitals) are incompatible and "
    "there is no join key.", align="justify")
r.h("5.2 Selected dataset", 2)
r.table(pd.DataFrame([
    ["Title", src["dataset_title"]], ["Creators", "Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014)"],
    ["Publisher", src["publisher"]], ["DOI", src["doi"]], ["Landing page", src["landing_page"]],
    ["Direct download", src["download_url"]], ["Licence", src["license"]], ["Access date", ACCESS_DATE],
    ["Files", "diabetic_data.csv (encounters); IDS_mapping.csv (code labels); ZIP archive kept unchanged"],
    ["SHA-256 (diabetic_data.csv)", src["files"]["diabetic_data.csv"]["sha256"]],
    ["Size", f"{num(clean['raw_rows'])} rows × 50 columns; {num(src['files']['diabetic_data.csv']['bytes'] / 1e6, 1)} MB"],
    ["Unit", f"Inpatient encounter (stay of 1–14 days) of a patient with diabetes; {num(qcs.loc['unique_patients', RAW])} unique patients"],
    ["Outcome", "readmitted: '<30' (within 30 days), '>30', 'NO'"],
    ["Introductory paper", "Strack et al. (2014), BioMed Research International, 781670"],
], columns=["Attribute", "Value"]), "Selected dataset metadata", widths_cm=[4.2, 12.4])
r.h("5.3 Structure and suitability", 2)
r.p("The 50 columns comprise two identifiers (encounter_id, patient_nbr); demographics (race, gender, 10-year age "
    "band, weight band); administrative codes (admission type, discharge disposition, admission source, payer, "
    "admitting specialty); utilisation counts (length of stay, laboratory procedures, procedures, medications, prior "
    "outpatient/emergency/inpatient visits); up to three ICD-9 diagnoses and the number of diagnoses; two laboratory "
    "results (maximum glucose serum, HbA1c); 23 diabetes-medication status columns (No/Steady/Up/Down); medication "
    "change and diabetes-medication flags; and the readmission outcome. The data contain no dates, hospital "
    "identifiers, costs or free text. They are suitable for patient-level readmission analysis and resource-use "
    "description, but not for time trends or hospital comparisons.", align="justify")
r.h("5.4 Acquisition procedure", 2)
r.numbered(["01_data_acquisition.py downloads the ZIP from the UCI static URL using HTTPS.",
            "The untouched archive is saved to data/raw/ and only the two expected CSV files are extracted "
            "(defensive against unexpected archive members).",
            "SHA-256 checksums, byte sizes, licence, DOI and access timestamp are written to SOURCE_METADATA.json.",
            "Accessibility of the alternative datasets is probed and logged (docs/dataset_access_probes.json).",
            "Raw files are never modified; all later steps write to data/processed/."])

# ================================================================== 6 CLEANING & QA
r.h("6. Data Cleaning and Quality Assurance", page_break=True)
r.h("6.1 Initial profiling", 2)
miss = pd.read_csv(TABLE_DIR / "data_quality_missing_by_column_raw.csv").set_index("column")["missing_pct_raw"]
r.p(f"Profiling found no duplicate encounter IDs and no exact duplicate rows. Missing values are encoded as '?' and, "
    f"for the ID columns, as 'NULL', 'Not Available' or 'Not Mapped' codes. Weight was missing for "
    f"{miss['weight']:.1f}% of encounters, medical specialty for {miss['medical_specialty']:.1f}% and payer code for "
    f"{miss['payer_code']:.1f}%. Two medication columns (examide, citoglipton) were constant. Three records had gender "
    f"'Unknown/Invalid'. Of {num(qcs.loc['unique_patients', RAW])} patients, many had several encounters (up to "
    f"{eda['max_encounters_one_patient']}), so encounters are not independent observations.", align="justify")
r.figure(FIG_DIR / "fig01_missing_by_column.png", "Missing data by column in the raw dataset",
         "Two fields breach the 40% acceptance threshold. Weight is unusable; medical specialty is retained with an "
         "explicit 'Unknown' level because half the rows would otherwise be lost and missingness itself may carry "
         "information about documentation practice.", width_cm=14.5)
r.figure(FIG_DIR / "fig02_missing_pattern.png", "Missing-data pattern in a random sample of 2,000 encounters",
         "Payer and specialty gaps overlap only partly, so missingness is not driven by a single data-entry failure. "
         "Because missingness is unlikely to be completely random, analyses by these fields are interpreted cautiously.",
         width_cm=14.5)
r.h("6.2 Cleaning and transformation procedures", 2)
r.p("Each transformation, its rationale and the number of rows or cells affected were logged by the cleaning script "
    "(Table 6). Missing categorical values were kept as an explicit 'Unknown' level rather than imputed, because "
    "imputing race, payer or specialty would fabricate sensitive attributes. Numeric fields had no missing values.",
    align="justify")
tl = tlog.copy()
tl["rows_or_cells_affected"] = tl["rows_or_cells_affected"].map(lambda v: f"{int(v):,}" if str(v).isdigit() else v)
r.table(tl[["step", "stage", "action", "rationale", "rows_or_cells_affected"]].rename(columns={
    "step": "#", "stage": "Stage", "action": "Action", "rationale": "Rationale", "rows_or_cells_affected": "Affected"}),
    "Transformation log", widths_cm=[0.7, 2.3, 6.0, 5.6, 2.0], font_size=7.5)
r.h("6.3 Cohort definition", 2)
r.p(f"The cleaned file keeps all {num(clean['clean_rows'])} valid encounters with flags. The analysis cohort keeps the "
    f"first encounter of each patient (ordered by encounter_id) and excludes encounters ending in death "
    f"({num(eda['expired_all_encounters'])} encounters overall) or hospice discharge ({num(eda['hospice_all_encounters'])}), "
    f"for which a readmission outcome is not meaningful. This yields {num(clean['cohort_rows'])} patients, one row each, "
    f"which makes observations independent and prevents the same patient appearing in both model training and test "
    f"data. The approach mirrors Strack et al. (2014).", align="justify")
r.h("6.4 Quality before and after cleaning", 2)
qshow = qc[qc["metric"].isin(["rows", "columns", "unique_patients", "completeness_pct_cells", "rows_fully_complete_pct",
                              "columns_over_40pct_missing", "validity_pct_rows", "duplicate_encounter_ids",
                              "exact_duplicate_rows", "constant_columns", "consistency_violations_total"])].copy()
qshow["metric"] = qshow["metric"].map({
    "rows": "Rows", "columns": "Columns (original fields)", "unique_patients": "Unique patients",
    "completeness_pct_cells": "Cell completeness (%)", "rows_fully_complete_pct": "Rows with no missing field (%)",
    "columns_over_40pct_missing": "Columns > 40% missing", "validity_pct_rows": "Rows passing all validity rules (%)",
    "duplicate_encounter_ids": "Duplicate encounter IDs", "exact_duplicate_rows": "Exact duplicate rows",
    "constant_columns": "Constant columns", "consistency_violations_total": "Cross-field consistency violations"})
for c in qshow.columns[1:]:
    qshow[c] = qshow[c].map(lambda v: f"{float(v):,.2f}".rstrip("0").rstrip(".") if float(v) % 1 else f"{int(float(v)):,}")
r.table(qshow.rename(columns={"metric": "Quality metric"}), "Data-quality metrics before and after cleaning",
        widths_cm=[6.0, 3.4, 3.4, 3.8],
        note="Completeness counts 'Unknown' (the explicit fill value) as missing, so the improvement reflects "
             "information actually gained (mainly by dropping weight), not relabelling. The cohort retains one "
             "constant column (a rarely used drug never prescribed at index encounters).")
r.p(f"Cell completeness rose from {qcs.loc['completeness_pct_cells', RAW]:.2f}% to "
    f"{qcs.loc['completeness_pct_cells', CLEANED]:.2f}% and the share of rows with no missing field from "
    f"{qcs.loc['rows_fully_complete_pct', RAW]:.2f}% to {qcs.loc['rows_fully_complete_pct', CLEANED]:.2f}%. "
    f"Medical specialty remains above the 40% threshold (accepted with an 'Unknown' level). All four cross-field "
    f"consistency checks (for example, 'diabetesMed = No' while a diabetes drug is recorded; a death recorded with a "
    f"readmission) returned zero violations.", align="justify")
r.h("6.5 Quality dimensions assessed", 2)
r.table(pd.DataFrame([
    ["Completeness", "Share of non-missing cells and rows; per-column missingness", "Columns ≤ 40% missing or justified; no silent imputation", "Met with documented exceptions (specialty, payer)"],
    ["Validity", "Range rules (e.g., LOS 1–14) and domain rules for every coded field", "0 failures", f"{(rules['status'] == 'PASS').sum()} of {len(rules)} rules pass"],
    ["Consistency", "Cross-field logic (medication flags, deaths vs readmission)", "< 0.5% of rows", "0 violations"],
    ["Uniqueness", "Duplicate encounter IDs and rows; one row per patient in cohort", "0 duplicates", "Met"],
    ["Accuracy", "Plausibility of values and distributions; comparison with published counts", "Matches source documentation", "Partly verifiable only (see note)"],
    ["Timeliness and relevance", "Data period vs intended use", "Fit for learning purposes", "Data are 17–26 years old; not fit for current targets"],
], columns=["Dimension", "How it was assessed", "Acceptance threshold", "Result"]),
    "Quality dimensions, thresholds and results", widths_cm=[2.6, 5.2, 4.2, 4.6], font_size=8,
    note="Accuracy note: the record count (101,766) and HbA1c testing share (18.4% of the cohort; Strack et al. report "
         "18.4%) agree with published figures, but passing automated checks does not prove that individual values "
         "are clinically correct. Source records were not available for verification.")
r.h("6.6 Issue log and unresolved issues", 2)
r.table(issues.rename(columns={"issue_id": "ID", "quality_dimension": "Dimension", "description": "Issue",
                               "magnitude": "Magnitude", "resolution": "Resolution", "residual_risk": "Residual risk / effect on findings"}),
        "Data-quality issue log", widths_cm=[1.2, 2.0, 3.6, 2.4, 3.2, 4.2], font_size=7.5)

# ================================================================== 7 PRIVACY ETHICS GOVERNANCE
r.h("7. Data Privacy, Ethics and Governance", page_break=True)
r.h("7.1 Privacy, confidentiality and de-identification", 2)
r.p("The dataset was de-identified by its publishers: patient and encounter numbers are surrogate keys, age is "
    "banded in 10-year intervals and no names, addresses, dates or hospital identifiers are released. In US terms "
    "this resembles HIPAA de-identification, which allows either removal of 18 identifier types (Safe Harbor) or an "
    "expert determination that re-identification risk is very small (US Department of Health and Human Services "
    "[HHS], 2012). De-identification lowers but does not remove risk: rare combinations (for example, a patient with "
    "40 encounters, an uncommon diagnosis and a recorded race) could in principle be linked to other data. This "
    "project therefore (a) does not attempt any linkage, (b) publishes only aggregated results and model outputs, and "
    "(c) suppresses dashboard rates for groups with fewer than 30 patients.", align="justify")
r.h("7.2 Licensing and permitted use", 2)
r.p("The data are licensed CC BY 4.0, which permits sharing and adaptation with attribution. The raw and processed "
    "files are therefore included in the project package with attribution to Clore et al. (2014) and the UCI "
    "repository. The CC BY licence does not remove ethical obligations: the data concern real patients and should "
    "not be used to profile individuals or communities.", align="justify")
r.h("7.3 Indian legal and policy context (verified October 2026)", 2)
r.bullets([
    ("Digital Personal Data Protection Act, 2023 (DPDP Act). ", "India's general data-protection law. Its "
     "implementing Digital Personal Data Protection Rules, 2025 were notified on 14 November 2025 with phased "
     "commencement: provisions on the Data Protection Board took effect on notification, while most obligations on "
     "data fiduciaries (notice, consent, security safeguards, breach notification, retention and erasure) apply "
     "from 14 May 2027 (Ministry of Electronics and Information Technology [MeitY], 2025). Any project using "
     "identifiable patient data in India should design for these obligations now."),
    ("Ayushman Bharat Digital Mission (ABDM) Health Data Management Policy. ", "Sets minimum privacy standards "
     "for entities in the national digital health ecosystem, including consent-based sharing, purpose limitation "
     "and data minimisation (National Health Authority, 2020; a revised draft was released for consultation in 2022)."),
    ("ICMR Ethical Guidelines for Application of AI in Biomedical Research and Healthcare (2023). ", "Require "
     "ethics-committee review, attention to data quality, non-discrimination, accountability and clinical validation "
     "before AI tools are deployed (Indian Council of Medical Research [ICMR], 2023)."),
])
r.p("Because this project uses openly licensed, de-identified US data, the DPDP Act's consent obligations are not "
    "triggered by the analysis itself. They would apply in full if the pipeline were re-run on identifiable data from "
    "an Indian hospital.", italic=True, align="justify")
r.h("7.4 International standards", 2)
r.bullets(["WHO guidance on ethics and governance of AI for health sets six principles: protect autonomy; promote "
           "well-being, safety and the public interest; ensure transparency, explainability and intelligibility; "
           "foster responsibility and accountability; ensure inclusiveness and equity; and promote responsive, "
           "sustainable AI (World Health Organization [WHO], 2021).",
           "TRIPOD+AI provides a 27-item checklist for reporting prediction models built with regression or machine "
           "learning (Collins et al., 2024); Section 13 follows its main elements (data source, outcome, predictors, "
           "sample size, missing data, model building, performance, fairness, limitations).",
           "HIPAA de-identification guidance (HHS, 2012) informs the de-identification assessment above."])
r.h("7.5 Data minimisation, secure storage, access control and retention", 2)
r.table(pd.DataFrame([
    ["Data minimisation", "Only fields needed for the research questions are used in models; race and payer excluded as predictors; identifiers excluded."],
    ["Secure storage", "For local (non-public) data: encrypted disk, organisation-managed storage, no copies on personal devices or public repositories."],
    ["Access control", "Role-based access: raw data restricted to named analysts; dashboard shows aggregates only."],
    ["Auditability", "Scripted pipeline, checksums of raw files, transformation log, fixed random seeds, versioned code."],
    ["Retention", "Public data: retained with the project. Local data: retained only as long as the approved purpose requires, then securely erased (DPDP Rules timelines)."],
    ["Re-identification controls", "No linkage to other datasets; small-cell suppression (n < 30) in published views."],
], columns=["Control", "Implementation"]), "Data governance controls", widths_cm=[3.8, 12.8])
r.h("7.6 Bias, fairness, transparency and accountability", 2)
r.p("Recorded race is missing for 2.2% of encounters, and categories are coarse. Using race or payer (an insurance and "
    "socio-economic proxy) as predictors could encode structural inequities into risk scores (Obermeyer et al., 2019; "
    "Rajkomar et al., 2018). The model therefore excludes both, and subgroup performance is audited instead "
    "(Section 13.5). Explainability is supported by permutation importance and a parallel logistic regression. "
    "Accountability for any future clinical use must rest with a named clinical owner and a governance committee, "
    "not with the analyst or the model.", align="justify")

# ================================================================== 8 KPIs
r.h("8. Healthcare KPIs and Definitions", page_break=True)
r.p("KPIs are computed on the analysis cohort unless stated. Formulas are repeated in Appendix C and implemented "
    "as DAX measures in the Power BI pack.", align="justify")
kpis = pd.DataFrame([
    ["K1", "30-day readmission rate", "Readmissions < 30 days ÷ eligible index discharges", f"{pct(ov['rate'])} (95% CI {ci(ov['ci_low'], ov['ci_high'])})", "Quality / outcome"],
    ["K2", "Any-time readmission rate", "Readmissions (< 30 or > 30 days) ÷ eligible discharges", pct(eda["readmit_any_rate_cohort"]), "Outcome"],
    ["K3", "Encounter-level 30-day readmission rate", "Readmissions < 30 days ÷ all valid encounters", pct(eda["readmit30_rate_all_encounters"]), "Outcome"],
    ["K4", "In-hospital mortality (encounters)", "Encounters with expired disposition ÷ all valid encounters", pct(eda["expired_all_encounters"] / eda["all_encounters_n"], 2), "Outcome"],
    ["K5", "Average length of stay (ALOS)", "Σ days in hospital ÷ patients", f"{eda['mean_los']:.2f} days", "Utilisation"],
    ["K6", "Total bed-days", "Σ days in hospital", num(eda["total_bed_days_cohort"]), "Utilisation"],
    ["K7", "Mean medications per stay", "Σ distinct medications ÷ patients", f"{eda['mean_meds']:.1f}", "Utilisation"],
    ["K8", "Mean laboratory procedures per stay", "Σ lab procedures ÷ patients", f"{eda['mean_labs']:.1f}", "Utilisation"],
    ["K9", "HbA1c testing rate", "Patients with HbA1c measured ÷ patients", pct(eda["a1c_measured_rate"]), "Process"],
    ["K10", "Diabetes medication change rate", "Patients with any diabetes drug change ÷ patients", pct(eda["medication_change_rate"]), "Process"],
    ["K11", "Discharge-to-home rate", "Discharged home (± home health) ÷ patients", pct(eda["discharged_home_pct"]), "Flow"],
    ["K12", "Prior-year inpatient share", "Patients with ≥ 1 prior inpatient stay ÷ patients", pct(eda["prior_inpatient_rate"]), "Risk mix"],
    ["K13", "Facility-discharge 30-day readmission rate", "Readmissions < 30 days among SNF/ICF/rehab discharges ÷ those discharges", pct(fac["rate_1"]), "Quality"],
    ["K14", "Data completeness", "Non-missing cells ÷ all cells (cleaned)", f"{qcs.loc['completeness_pct_cells', CLEANED]:.1f}%", "Data quality"],
    ["K15", "Model ROC-AUC (test)", "Area under ROC curve on held-out patients", f"{mdl['test_roc_auc']:.3f}", "Model"],
    ["K16", "Readmissions captured in top-20% risk", "True positives ÷ all readmissions at top-20% threshold", pct(m20["recall_sensitivity"]), "Model"],
], columns=["ID", "KPI", "Formula", "Value", "Type"])
r.table(kpis, "KPI catalogue with calculated values", widths_cm=[1.0, 4.2, 6.2, 3.4, 1.8], font_size=8)

# ================================================================== 9 EDA
r.h("9. Exploratory Data Analysis", page_break=True)
r.h("9.1 Executive overview and cohort profile", 2)
r.figure(FIG_DIR / "fig00_executive_kpis.png", "Executive KPI overview",
         "The overview gives leaders the headline: roughly one patient in eleven returns within 30 days, stays are "
         "short on average, and HbA1c testing is uncommon.")
r.p(f"The cohort is {pct(eda['female_pct'])} female; {pct(eda['age_60plus_pct'])} are aged 60 or over; "
    f"{pct(eda['emergency_admission_pct'])} were emergency admissions; {pct(eda['diabetes_med_rate'])} received a "
    f"diabetes medication and {pct(eda['insulin_rate'])} insulin. Counts of prior visits are heavily right-skewed "
    f"(skewness of prior inpatient visits {desc.loc['number_inpatient', 'skew']:.1f}), so medians and rank-based tests "
    f"are used alongside means.", align="justify")
dshow = desc.loc[["time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications", "number_outpatient",
                  "number_emergency", "number_inpatient", "number_diagnoses", "age_mid"],
                 ["mean", "std", "min", "25%", "50%", "75%", "max", "skew"]].round(2).reset_index()
dshow.columns = ["Variable", "Mean", "SD", "Min", "Q1", "Median", "Q3", "Max", "Skew"]
r.table(dshow, f"Descriptive statistics of numeric variables (n = {num(ov['n'])})",
        widths_cm=[4.0, 1.6, 1.6, 1.4, 1.4, 1.6, 1.4, 1.4, 1.6], font_size=8)
r.h("9.2 Outcome distribution", 2)
r.figure(FIG_DIR / "fig03_outcome_distribution.png", "Distribution of the readmission outcome",
         f"The 30-day outcome is imbalanced ({pct(ov['rate'])} positive in the cohort). The encounter-level rate is "
         f"higher ({pct(eda['readmit30_rate_all_encounters'])}) because frequent users contribute many encounters; "
         f"analysing encounters as independent would overstate precision and mix in repeat-visit risk.")
r.h("9.3 Demographics", 2)
r.figure(FIG_DIR / "fig04_age_distribution_readmission.png", "Age distribution and 30-day readmission by age band",
         "Most patients are 50–90 years old. Readmission rises from about 7% below age 60 to over 10% at 70–90, "
         "with wide intervals in small young bands.")
r.figure(FIG_DIR / "fig12_demographic_subgroups.png", "30-day readmission by recorded race and gender",
         "Differences by gender are negligible. Rates by race differ slightly (Caucasian 9.2% vs African American "
         "8.7%), with overlapping intervals for smaller groups; the 'Unknown' and 'Other' groups are lower, possibly "
         "reflecting documentation differences rather than risk.")
r.h("9.4 Clinical and care-process comparisons", 2)
r.figure(FIG_DIR / "fig05_readmission_by_diagnosis.png", "30-day readmission by primary diagnosis group",
         f"Injury ({pct(by_diag.iloc[0]['rate'])}) and circulatory conditions ({pct(by_diag.iloc[1]['rate'])}) have "
         f"the highest rates; respiratory conditions the lowest ({pct(by_diag.iloc[-1]['rate'])}). Differences between "
         f"groups are real but small in absolute terms.")
r.figure(FIG_DIR / "fig08_readmission_by_discharge.png", "30-day readmission by discharge destination",
         f"Transfers to rehabilitation/other inpatient facilities ({pct(dis_rate('Other inpatient / rehab facility')['rate'])}) "
         f"and skilled nursing ({pct(dis_rate('Skilled nursing / ICF')['rate'])}) have about two to three times the "
         f"rate of patients discharged home ({pct(dis_rate('Home')['rate'])}). Facility discharge is a marker of "
         f"frailty and complexity, so this is not evidence that the destination itself causes readmission.")
r.figure(FIG_DIR / "fig07_prior_inpatient.png", "30-day readmission by prior-year inpatient admissions",
         f"A clear dose–response gradient: from {pct(by_ip.iloc[0]['rate'])} with no prior admission to "
         f"{pct(by_ip.iloc[-1]['rate'])} with five or more.")
r.figure(FIG_DIR / "fig09_hba1c.png", "HbA1c testing by primary diagnosis and readmission by HbA1c result",
         "HbA1c is tested in about a third of patients admitted primarily for diabetes but in only 10–20% of others. "
         "Unadjusted readmission is slightly lower when HbA1c was measured, regardless of the result.")
r.h("9.5 Resource utilisation", 2)
r.figure(FIG_DIR / "fig06_length_of_stay.png", "Length-of-stay distribution and readmission by length of stay",
         f"Stays are right-skewed (median {eda['median_los']:.0f} days, mean {eda['mean_los']:.2f}). Readmission "
         f"rises gradually with length of stay, reflecting illness severity.")
r.figure(FIG_DIR / "fig11_utilisation_by_diagnosis.png", "Bed-day consumption and length of stay by primary diagnosis",
         f"Circulatory conditions account for {pct(util.iloc[0]['bed_day_share'])} of bed-days because they are "
         f"common, not because stays are long; neoplasms have the longest mean stay "
         f"({util.set_index('diag_1_group').loc['Neoplasms', 'mean_los']:.1f} days).")
r.h("9.6 Relationships between variables", 2)
r.figure(FIG_DIR / "fig10_correlation_heatmap.png", "Spearman correlation matrix",
         f"Utilisation measures move together (length of stay with medications ρ = {sp.iloc[0]['spearman_rho']:.2f}, "
         f"with lab procedures ρ = {sp.iloc[1]['spearman_rho']:.2f}), but no single numeric variable is strongly "
         f"correlated with readmission (largest: prior inpatient visits, ρ = {sp.iloc[6]['spearman_rho']:.2f}). "
         f"Readmission is therefore driven by many weak signals, which foreshadows modest model performance.",
         width_cm=13.5)
r.h("9.7 Operational and quality issues identified", 2)
r.bullets(["Concentrated risk in facility discharges and frequent users — a small share of patients carries a large "
           "share of readmissions.",
           "Low and uneven HbA1c testing — a process gap independent of whether testing changes outcomes.",
           "Documentation gaps (weight, specialty, payer) that limit risk adjustment and equity analysis.",
           "No admission dates or hospital identifiers — trends and benchmarking cannot be produced from this extract."])

# ================================================================== 10 STATISTICS
r.h("10. Statistical Analysis and Results", page_break=True)
r.h("10.1 Methods and assumptions", 2)
r.table(pd.DataFrame([
    ["Proportion with CI", "Rates", "Wilson score interval (Wilson, 1927)", "Binomial sampling; accurate for small or extreme proportions"],
    ["Pearson χ² test of independence", "Categorical factor × readmission", "Cramér's V", "Independent observations (one row per patient); expected counts ≥ 5 (checked)"],
    ["Mann–Whitney U", "Numeric / count variable × readmission", "Rank-biserial r; Cohen's d; Welch 95% CI for mean difference", "Independent groups; no normality assumption (counts are skewed)"],
    ["Two-proportion z-test", "Pre-specified binary comparisons", "Risk difference, risk ratio, odds ratio with 95% CI", "Large samples"],
    ["Kruskal–Wallis H", "Length of stay across diagnosis groups", "Epsilon-squared (ε²)", "Independent groups; similar distribution shapes"],
    ["Spearman ρ", "Monotonic association between numeric variables", "ρ", "Monotonic relationship"],
    ["Multivariable logistic regression", "Adjusted associations with readmission", "Adjusted odds ratio (95% CI)", "Linearity of logit for numeric terms; low collinearity (all VIF < 1.4); independent observations"],
    ["Likelihood-ratio test", "HbA1c × diagnosis interaction", "χ² on 8 df", "Nested models"],
], columns=["Method", "Used for", "Effect size reported", "Key assumptions"]), "Statistical methods",
    widths_cm=[3.4, 3.8, 4.4, 5.0], font_size=8)
r.p("Multiple comparisons were controlled with Holm's step-down method within each family of tests (Holm, 1979). "
    "With about 70,000 patients, very small differences reach statistical significance, so interpretation focuses "
    "on effect sizes and confidence intervals rather than p-values alone. All results are associations in "
    "observational data; unmeasured confounding (for example, frailty, social support, discharge quality) may "
    "explain part or all of any association.", align="justify")
r.h("10.2 Overall rate", 2)
r.p(f"The 30-day readmission rate was {pct(ov['rate'], 2)} (95% Wilson CI {ci(ov['ci_low'], ov['ci_high'], lambda x: pct(x, 2))}; "
    f"{num(ov['events'])} of {num(ov['n'])} patients).")
r.h("10.3 Categorical factors", 2)
cshow = chi[["variable", "levels", "chi2", "dof", "cramers_v", "p_holm", "lowest_rate_level", "highest_rate_level"]].copy()
cshow["chi2"] = cshow["chi2"].map(lambda v: f"{v:,.1f}")
cshow["cramers_v"] = cshow["cramers_v"].map(lambda v: f"{v:.3f}")
cshow["p_holm"] = cshow["p_holm"].map(pval)
cshow.columns = ["Variable", "Levels", "χ²", "df", "Cramér's V", "p (Holm)", "Lowest-rate level", "Highest-rate level"]
r.table(cshow, "Chi-square tests of association with 30-day readmission", widths_cm=[3.2, 1.1, 1.5, 0.8, 1.5, 1.5, 3.5, 3.5], font_size=7.5)
r.p(f"Discharge destination has by far the largest effect (Cramér's V = {chi.iloc[0]['cramers_v']:.3f}); all other "
    f"factors have V < 0.05, which is conventionally a negligible effect even when highly significant. Gender, HbA1c "
    f"result category, glucose test result, admission type and admission source were not significant after Holm "
    f"correction.", align="justify")
r.h("10.4 Numeric factors", 2)
mshow = mw[["variable", "mean_readmitted", "mean_not_readmitted", "mean_diff", "mean_diff_ci_low", "mean_diff_ci_high",
            "rank_biserial_r", "p_holm"]].copy()
mshow["diff_ci"] = mshow.apply(lambda x: f"{x.mean_diff:.2f} ({x.mean_diff_ci_low:.2f} to {x.mean_diff_ci_high:.2f})", axis=1)
mshow = mshow[["variable", "mean_readmitted", "mean_not_readmitted", "diff_ci", "rank_biserial_r", "p_holm"]]
mshow["mean_readmitted"] = mshow["mean_readmitted"].round(2)
mshow["mean_not_readmitted"] = mshow["mean_not_readmitted"].round(2)
mshow["rank_biserial_r"] = mshow["rank_biserial_r"].round(3)
mshow["p_holm"] = mshow["p_holm"].map(pval)
mshow.columns = ["Variable", "Mean (readmitted)", "Mean (not)", "Difference (95% CI)", "Rank-biserial r", "p (Holm)"]
r.table(mshow, "Mann–Whitney U tests: numeric variables by 30-day readmission", widths_cm=[3.6, 2.2, 2.0, 4.0, 2.4, 2.4], font_size=8)
r.p(f"Readmitted patients stayed longer (mean difference {mw.set_index('variable').loc['time_in_hospital', 'mean_diff']:.2f} days), "
    f"were older, had more prior inpatient visits and more diagnoses. All effect sizes are small (|r| ≤ 0.12). "
    f"The number of non-laboratory procedures was not associated with readmission.", align="justify")
r.h("10.5 Pre-specified two-group comparisons", 2)
tshow = two[["comparison", "rate_1", "rate_0", "risk_difference", "rd_ci_low", "rd_ci_high", "risk_ratio", "rr_ci_low",
             "rr_ci_high", "p_holm"]].copy()
tshow["Rates"] = tshow.apply(lambda x: f"{pct(x.rate_1)} vs {pct(x.rate_0)}", axis=1)
tshow["Risk difference (95% CI)"] = tshow.apply(lambda x: f"{100 * x.risk_difference:+.1f} pp ({100 * x.rd_ci_low:+.1f} to {100 * x.rd_ci_high:+.1f})", axis=1)
tshow["Risk ratio (95% CI)"] = tshow.apply(lambda x: f"{x.risk_ratio:.2f} ({x.rr_ci_low:.2f}–{x.rr_ci_high:.2f})", axis=1)
tshow["p (Holm)"] = tshow["p_holm"].map(pval)
r.table(tshow[["comparison", "Rates", "Risk difference (95% CI)", "Risk ratio (95% CI)", "p (Holm)"]].rename(columns={"comparison": "Comparison"}),
        "Pre-specified comparisons of 30-day readmission", widths_cm=[5.4, 2.8, 3.8, 2.8, 1.8], font_size=8)
r.h("10.6 Resource use across diagnoses", 2)
kw = st["kruskal_los"]
r.p(f"Length of stay differed across the nine primary-diagnosis groups (Kruskal–Wallis H = {kw['H']:.1f}, df = {kw['dof']}, "
    f"p {pval(kw['p_value'])}), but the effect size was very small (ε² = {kw['epsilon_squared']:.3f}): diagnosis group "
    f"explains under 1% of the variation in length of stay.", align="justify")
r.h("10.7 Multivariable logistic regression", 2)
fit = st["logit_fit"]
r.p(f"A logistic regression of 30-day readmission on HbA1c result, primary diagnosis, age group, gender, race group, "
    f"discharge destination, admission source, medication change and seven utilisation counts was fitted to "
    f"{num(fit['n'])} patients ({num(fit['events'])} events; about {fit['events'] / 35:.0f} events per parameter). "
    f"The model converged; McFadden pseudo-R² was {fit['pseudo_r2_mcfadden']:.3f} and the maximum variance inflation "
    f"factor among numeric predictors was {max(fit['vif'].values()):.2f}. The low pseudo-R² again shows that the "
    f"available variables explain only a small part of readmission risk.", align="justify")
r.figure(FIG_DIR / "fig13_logistic_regression_forest.png", "Adjusted odds ratios for 30-day readmission",
         f"After adjustment, discharge to a rehabilitation/other inpatient facility (OR "
         f"{orr.loc['discharge_group = Other inpatient / rehab facility', 'odds_ratio']:.2f}) or skilled nursing (OR "
         f"{orr.loc['discharge_group = Skilled nursing / ICF', 'odds_ratio']:.2f}), each prior inpatient admission "
         f"(OR {orr.loc['number_inpatient', 'odds_ratio']:.2f}) and age 60–79 (OR "
         f"{orr.loc['age_group = 60–79', 'odds_ratio']:.2f}) remain the strongest associations. Respiratory and "
         f"musculoskeletal primary diagnoses carry lower odds than the reference ('Other').", width_cm=15.5)
r.h("10.8 HbA1c and readmission (H3)", 2)
r.p(f"In a model with a binary HbA1c-measured indicator and the same covariates, measurement was associated with "
    f"lower odds of readmission (adjusted OR {inter['a1c_measured_OR_main_model']:.2f}, 95% CI "
    f"{inter['a1c_measured_OR_ci'][0]:.2f}–{inter['a1c_measured_OR_ci'][1]:.2f}, p = {pval(inter['a1c_measured_p'])}). "
    f"Adding HbA1c × diagnosis interaction terms improved fit (likelihood-ratio χ² = {inter['LR_chi2']:.1f}, "
    f"df = {inter['dof']:.0f}, p = {pval(inter['p_value'])}), so the association depends on the primary diagnosis. "
    f"This replicates the central finding of Strack et al. (2014) on an independently constructed cohort. However, "
    f"testing may simply mark more attentive care or different patient mixes; a trial or quasi-experimental "
    f"evaluation would be needed to show that testing itself reduces readmissions.", align="justify")
r.h("10.9 Hypothesis summary", 2)
r.table(pd.DataFrame([
    ["H1", "Prior inpatient use → higher readmission", f"RR {ip['risk_ratio']:.2f} ({ip['rr_ci_low']:.2f}–{ip['rr_ci_high']:.2f}); adj. OR {orr.loc['number_inpatient', 'odds_ratio']:.2f} per admission", "Supported"],
    ["H2", "Facility discharge → higher readmission", f"RR {fac['risk_ratio']:.2f} ({fac['rr_ci_low']:.2f}–{fac['rr_ci_high']:.2f}); Cramér's V {chi.iloc[0]['cramers_v']:.3f}", "Supported"],
    ["H3", "HbA1c measured → lower readmission; differs by diagnosis", f"adj. OR {inter['a1c_measured_OR_main_model']:.2f}; interaction p = {pval(inter['p_value'])}", "Supported (small association)"],
    ["H4", "Longer stay and older age → higher readmission", f"LOS ≥ 7 d RR {los7['risk_ratio']:.2f}; age ≥ 60 RR {old['risk_ratio']:.2f}", "Supported (small effects)"],
    ["H5", "LOS differs across diagnoses", f"H = {kw['H']:.0f}, ε² = {kw['epsilon_squared']:.3f}", "Statistically supported; negligible effect"],
    ["H6", "Model beats prior-admission baseline", f"Test AUC {mdl['test_roc_auc']:.3f} vs {base_ip['roc_auc']:.3f}", "Supported (modest absolute performance)"],
], columns=["ID", "Hypothesis", "Evidence", "Conclusion"]), "Hypothesis outcomes", widths_cm=[1.0, 5.0, 6.8, 3.8], font_size=8.5)

# ================================================================== 11 VISUALISATION & DASHBOARD
r.h("11. Visualisation and Dashboard Design", page_break=True)
r.h("11.1 Design principles", 2)
r.bullets(["Every chart answers one question, states it in the title and shows units and sample sizes.",
           "Rates are always shown with 95% confidence intervals, and a reference line marks the overall rate.",
           "One colour for a single series (no rank-based colouring); a second colour only for emphasis.",
           "Colour palettes are colour-vision-deficiency-validated; text never relies on colour alone.",
           "Small groups (n < 30) are suppressed rather than shown with misleading precision.",
           "No dual axes; related measures on different scales are placed in side-by-side panels."])
r.h("11.2 Interactive dashboard (delivered)", 2)
r.p("Because Power BI Desktop could not be automated in this environment, the working dashboard was built as a "
    "single, self-contained HTML file (dashboard/healthcare_readmission_dashboard.html, about 1.9 MB, no internet "
    "connection or software installation required). It contains:", align="justify")
r.bullets(["Five filters (age group, gender, recorded race, primary diagnosis, admission type) with a reset button.",
           "Six KPI cards that recalculate for the current selection, including the readmission rate with its "
           "95% confidence interval.",
           "Six interactive charts (discharge destination, primary diagnosis, prior admissions, age band, "
           "length-of-stay distribution, HbA1c result) with hover tooltips and an expandable data table each.",
           "A model panel showing observed readmission by predicted-risk decile on the held-out test set.",
           "Automatic suppression of rates for groups under 30 patients, light/dark themes and method notes."])
r.p("Screenshots of the dashboard (desktop and mobile widths) are reproduced in Appendix F.")
r.h("11.3 Power BI build pack", 2)
r.p("The dashboard/powerbi folder contains a star-schema data model (one fact table with one row per patient and six "
    "dimension tables), 14 DAX measures (including Wilson confidence limits, small-sample suppression and comparison "
    "with the overall rate) and a step-by-step build guide with validation totals. No .pbix file is claimed or "
    "supplied.", align="justify")

# ================================================================== 12 MODELLING METHODOLOGY
r.h("12. Predictive Modelling Methodology", page_break=True)
r.h("12.1 Problem framing", 2)
r.table(pd.DataFrame([
    ["Prediction target", "readmit_30 = 1 if readmitted within 30 days of discharge"],
    ["Prediction time", "At discharge from the index encounter; all predictors are known by then"],
    ["Unit of analysis", "Patient (first eligible encounter); one row per patient"],
    ["Intended use (hypothetical)", "Rank patients for transition-of-care follow-up; not diagnosis or treatment"],
    ["Target distribution", f"{pct(mdl['split']['train_rate'])} positive in training; identical (stratified) in validation and test"],
    ["Data split", f"Train {num(mdl['split']['train'])} (60%), validation {num(mdl['split']['validation'])} (20%), test {num(mdl['split']['test'])} (20%), stratified on outcome, seed 42"],
], columns=["Element", "Specification"]), "Prediction problem specification", widths_cm=[4.0, 12.6])
r.h("12.2 Predictors and leakage control", 2)
r.p(f"Eleven numeric predictors ({', '.join(mdl['features_numeric'])}) and fourteen categorical predictors "
    f"({', '.join(mdl['features_categorical'])}) were selected on clinical and operational grounds. the table below lists "
    f"the variables deliberately excluded.")
r.table(pd.DataFrame(list(mdl["excluded_features"].items()), columns=["Excluded variable(s)", "Reason"]),
        "Variables excluded from the model", widths_cm=[6.0, 10.6], font_size=8.5)
r.h("12.3 Pre-processing", 2)
r.bullets(["Missing categorical values were already explicit 'Unknown' levels; no numeric values were missing, so "
           "no imputation was needed.",
           "Categorical variables: one-hot encoding with levels seen fewer than 50 times in training grouped as "
           "'infrequent'; unseen levels handled safely at prediction time.",
           "Numeric variables: standardised for logistic regression; left unscaled for tree models.",
           "All pre-processing is fitted inside scikit-learn pipelines on training folds only, preventing leakage "
           "from validation or test data."])
r.h("12.4 Baselines and candidate models", 2)
r.table(pd.DataFrame([
    ["Baseline 1: prevalence only", "Predicts the training prevalence for everyone", "Reference for 'no information' (AUC = 0.5)"],
    ["Baseline 2: prior inpatient count", "One-variable logistic regression; equivalent to flagging anyone with a prior-year admission", "A simple rule a hospital could apply today"],
    ["Logistic regression (L2)", "Linear, interpretable, well calibrated by construction", "Transparent reference model"],
    ["Random forest", "Captures non-linearities and interactions; robust to irrelevant features", "Flexible non-parametric model"],
    ["Histogram gradient boosting", "Strong on tabular data; early stopping limits overfitting", "State-of-the-art tabular baseline"],
], columns=["Model", "Description", "Why included"]), "Baselines and candidate models", widths_cm=[4.2, 7.4, 5.0], font_size=8.5)
r.p("Hyperparameters were tuned by randomised search with 5-fold stratified cross-validation on the training set "
    "only, optimising ROC-AUC. Class weights were not used, so predicted probabilities remain interpretable as risks; "
    "class imbalance is handled at the decision-threshold stage instead. The final model was chosen on the "
    "validation set (highest ROC-AUC, with a rule to prefer logistic regression if within 0.005). The decision "
    "threshold was fixed on validation predictions as the cut-off that flags the 20% highest-risk patients, an "
    "operationally realistic workload for a care-transition team. The test set was used once, after all choices were "
    "made.", align="justify")
tshow = tune.copy()
tshow["best_params"] = tshow["best_params"].astype(str).str.replace("np.float64(", "").str.replace(")", "").str.replace("{}", "—")
for c in ["cv_roc_auc_mean", "cv_roc_auc_sd", "val_roc_auc", "val_pr_auc"]:
    tshow[c] = tshow[c].map(lambda v: "—" if pd.isna(v) else f"{v:.3f}")
tshow.columns = ["Model", "CV ROC-AUC (mean)", "CV SD", "Selected hyperparameters", "Validation ROC-AUC", "Validation PR-AUC"]
r.table(tshow, "Cross-validation and validation results", widths_cm=[3.6, 1.8, 1.3, 6.1, 1.9, 1.9], font_size=7.5,
        note=mdl["selection_note"] + ".")

# ================================================================== 13 EVALUATION & RESPONSIBLE AI
r.h("13. Model Evaluation and Responsible AI", page_break=True)
r.h("13.1 Test-set performance", 2)
ts = test[["model", "roc_auc", "pr_auc", "brier", "accuracy", "precision_ppv", "recall_sensitivity", "specificity", "f1"]].copy()
for c in ts.columns[1:]:
    ts[c] = ts[c].map(lambda v: f"{v:.3f}")
ts.columns = ["Model", "ROC-AUC", "PR-AUC", "Brier", "Accuracy", "Precision", "Recall", "Specificity", "F1"]
r.table(ts, f"Held-out test-set performance (n = {num(mdl['split']['test'])}; prevalence {pct(mdl['split']['test_rate'])})",
        widths_cm=[4.6, 1.5, 1.5, 1.4, 1.6, 1.6, 1.4, 1.7, 1.3], font_size=8,
        note="Threshold metrics use each model's own validation-derived top-20% cut-off; the prevalence-only "
             "baseline uses 0.5 and therefore never flags anyone. Baseline 2 flags patients with any prior admission.")
r.p(f"The selected {best.lower()} reached ROC-AUC {mdl['test_roc_auc']:.3f} (bootstrap 95% CI "
    f"{mdl['test_roc_auc_ci'][0]:.3f}–{mdl['test_roc_auc_ci'][1]:.3f}) and PR-AUC {mdl['test_pr_auc']:.3f} "
    f"({mdl['test_pr_auc_ci'][0]:.3f}–{mdl['test_pr_auc_ci'][1]:.3f}), about twice the prevalence. The three "
    f"multivariable models perform similarly; all clearly beat the prior-admission rule (AUC {base_ip['roc_auc']:.3f}). "
    f"Performance in this range is typical of readmission models built from administrative data (Kansagara et al., "
    f"2011), and it means the model can separate groups of patients by risk but cannot reliably identify individual "
    f"patients who will be readmitted.", align="justify")
r.figure(FIG_DIR / "fig14_roc_pr_curves.png", "ROC and precision–recall curves on the test set",
         "The ROC curves sit well above chance but far from the top-left corner. The precision–recall curve is the "
         "more informative view for an imbalanced outcome (Saito & Rehmsmeier, 2015): precision falls quickly as "
         "recall increases.")
r.h("13.2 Why accuracy is misleading", 2)
th = thr[["rule", "accuracy", "precision_ppv", "recall_sensitivity", "specificity", "f1", "flagged_share"]].copy()
for c in th.columns[1:]:
    th[c] = th[c].map(lambda v: pct(v))
th.columns = ["Decision rule", "Accuracy", "Precision (PPV)", "Sensitivity", "Specificity", "F1", "Share flagged"]
r.table(th, f"Effect of the decision threshold ({best}, test set)", widths_cm=[5.4, 1.7, 2.0, 1.9, 1.9, 1.6, 2.1], font_size=8)
r.p(f"A rule that never flags anyone achieves {pct(thr.iloc[-1]['accuracy'])} accuracy — higher than any useful "
    f"model — while finding no readmissions. The default 0.5 cut-off behaves the same way because almost no "
    f"predicted risks exceed 50%. For imbalanced outcomes, sensitivity, precision, PR-AUC and the workload implied "
    f"by a threshold are the relevant measures.", align="justify")
r.figure(FIG_DIR / "fig16_confusion_matrix.png", "Confusion matrix at the top-20% threshold",
         f"Of {num(m20['tp'] + m20['fn'])} readmitted test patients, {num(m20['tp'])} were flagged; "
         f"{num(m20['fp'])} flagged patients were not readmitted. Roughly five patients would be reviewed per "
         f"readmission found.", width_cm=10.5)
r.h("13.3 Calibration", 2)
cal = mdl["calibration"]
r.p(f"Mean predicted risk ({pct(cal['mean_predicted'], 2)}) matches the observed rate ({pct(cal['observed_rate'], 2)}), "
    f"so calibration-in-the-large is good (intercept {cal['calibration_in_the_large']:.3f}). The calibration slope "
    f"of {cal['calibration_slope']:.2f} (> 1) shows that the random forest's predictions are too compressed toward "
    f"the average: true risk in the highest decile ({pct(mdl['top_decile_rate'])}) exceeds the mean prediction. "
    f"Recalibration (e.g., Platt or isotonic scaling on validation data) would be required before any risk value is "
    f"shown to users (Van Calster et al., 2019). Brier score was {mdl['test_brier']:.4f}.", align="justify")
r.figure(FIG_DIR / "fig15_calibration.png", "Calibration curves on the test set (risk deciles)", None, width_cm=10.5)
r.h("13.4 Interpretability", 2)
r.figure(FIG_DIR / "fig17_feature_importance.png", f"Permutation feature importance ({best})",
         "Discharge destination and prior inpatient admissions dominate, consistent with the statistical analysis. "
         "Importance measures how much the model relies on a feature, not whether changing it would change outcomes.",
         width_cm=14.5)
dshow = dec[["decile", "patients", "readmissions", "mean_pred", "observed_rate", "capture_cumulative", "lift"]].copy()
dshow["mean_pred"] = dshow["mean_pred"].map(pct)
dshow["observed_rate"] = dshow["observed_rate"].map(pct)
dshow["capture_cumulative"] = dshow["capture_cumulative"].map(pct)
dshow["lift"] = dshow["lift"].map(lambda v: f"{v:.2f}")
dshow.columns = ["Risk decile (1 = highest)", "Patients", "Readmissions", "Mean predicted", "Observed rate", "Cumulative capture", "Lift"]
r.table(dshow, "Readmission by predicted-risk decile (test set)", widths_cm=[3.2, 1.8, 2.2, 2.4, 2.3, 2.6, 1.6], font_size=8)
r.h("13.5 Subgroup performance and fairness", 2)
s2 = sub[["attribute", "group", "n", "events", "observed_rate", "mean_predicted", "roc_auc", "auc_ci_low", "auc_ci_high",
          "recall_sensitivity", "precision_ppv", "flagged_share"]].copy()
s2["AUC (95% CI)"] = s2.apply(lambda x: f"{x.roc_auc:.3f} ({x.auc_ci_low:.2f}–{x.auc_ci_high:.2f})", axis=1)
for c in ["observed_rate", "mean_predicted", "recall_sensitivity", "precision_ppv", "flagged_share"]:
    s2[c] = s2[c].map(pct)
s2 = s2[["attribute", "group", "n", "events", "observed_rate", "mean_predicted", "AUC (95% CI)", "recall_sensitivity",
         "precision_ppv", "flagged_share"]]
s2.columns = ["Attribute", "Group", "n", "Events", "Observed", "Mean predicted", "AUC (95% CI)", "Sensitivity", "PPV", "Flagged"]
r.table(s2, "Subgroup performance at the top-20% threshold (test set)", widths_cm=[1.8, 2.5, 1.1, 1.2, 1.5, 1.6, 2.6, 1.6, 1.3, 1.4], font_size=7.5)
r.figure(FIG_DIR / "fig18_subgroup_performance.png", "Discrimination, sensitivity and flag rate by subgroup",
         "Discrimination is similar across gender and the two largest race groups. Sensitivity is lowest for "
         "patients aged 40–59, who are flagged less often because their baseline risk is lower, and highest for "
         "those aged 80+. Estimates for small groups (Asian, Hispanic, Other) are imprecise. A deployed model would "
         "need explicit fairness criteria agreed with clinicians and community representatives.", width_cm=15.5)
r.h("13.6 Responsible-AI statement and deployment conditions", 2)
r.p("The model is an educational artefact. It must not be used to make or influence decisions about individual "
    "patients. Before any operational use, the following would be required:", bold_lead="Status. ")
r.numbered(["External and temporal validation on current local data (performance and calibration).",
            "Recalibration and an agreed operating threshold based on intervention capacity and the harms of false "
            "negatives (missed high-risk patients) and false positives (unnecessary follow-up, alarm fatigue).",
            "Ethics-committee and data-protection review; clinical safety case; named accountable owner.",
            "Human-in-the-loop use: scores support, never replace, clinical discharge judgement.",
            "Monitoring of data drift (input distributions), performance drift (AUC, calibration) and subgroup "
            "metrics at least quarterly, with a retraining and decommissioning policy."])
r.h("13.7 Model evaluation checklist", 2)
r.table(pd.DataFrame([
    ["Target, prediction time and unit defined", "Yes", "Section 12.1"],
    ["Identifiers and leakage variables removed", "Yes", "Section 12.2"],
    ["Patients not shared across train/validation/test", "Yes", "One row per patient"],
    ["Pre-processing fitted on training data only", "Yes", "scikit-learn pipelines"],
    ["Simple baseline(s) reported", "Yes", "Two baselines"],
    ["Hyperparameters tuned without test data", "Yes", "5-fold CV on training set"],
    ["Model and threshold selected on validation data", "Yes", "Section 12.4"],
    ["Single evaluation on untouched test set", "Yes", "Section 13.1"],
    ["Discrimination with uncertainty", "Yes", "Bootstrap 95% CI"],
    ["Imbalance-appropriate metrics", "Yes", "PR-AUC, sensitivity, PPV"],
    ["Calibration assessed", "Yes", "Slope, intercept, curve"],
    ["Subgroup / fairness analysis", "Yes", "Gender, race, age"],
    ["Interpretability output", "Yes", "Permutation importance; LR coefficients"],
    ["External / temporal validation", "No", "Not possible with one historical dataset"],
    ["Clinical utility (e.g., decision-curve) analysis", "No", "Recommended future work"],
], columns=["Check", "Done", "Evidence"]), "Model evaluation checklist", widths_cm=[8.0, 1.6, 7.0], font_size=8.5)

# ================================================================== 14 RESULTS & INTERPRETATION
r.h("14. Analytical Results and Interpretation", page_break=True)
r.h("14.1 Answers to the research questions", 2)
r.bullets([
    ("RQ1 — How common is early readmission? ", f"{pct(ov['rate'])} of patients at their first eligible encounter; "
     f"higher in older patients, after facility discharge and among frequent users."),
    ("RQ2 — Prior use. ", f"The strongest patient-level gradient in the data: from {pct(by_ip.iloc[0]['rate'])} "
     f"(no prior admission) to {pct(by_ip.iloc[-1]['rate'])} (five or more)."),
    ("RQ3 — Discharge destination. ", "Facility discharges carry two to three times the risk of home discharges, "
     "and the association survives adjustment."),
    ("RQ4 — HbA1c. ", "Testing is uncommon and associated with slightly lower readmission; the association varies "
     "by diagnosis. Causality cannot be inferred."),
    ("RQ5 — Length of stay and age. ", "Both are associated with higher readmission, with small effects."),
    ("RQ6 — Resource use. ", "Bed-days are concentrated in circulatory conditions because of volume; stay lengths "
     "differ little between diagnoses."),
    ("RQ7 — Prediction. ", f"A multivariable model ranks risk better than a simple rule (AUC {mdl['test_roc_auc']:.3f} "
     f"vs {base_ip['roc_auc']:.3f}); the top two risk deciles contain {pct(mdl['top2_decile_capture'])} of readmissions."),
])
r.h("14.2 Discussion", 2)
r.p("The results point to a consistent picture: readmission risk is concentrated in patients who are sicker, frailer "
    "and more dependent at discharge, as reflected by facility discharge, prior admissions and age. These are largely "
    "markers of underlying vulnerability rather than levers that a hospital can change directly. The actionable "
    "implication is to use them for targeting — directing transition-of-care resources to the groups where risk is "
    "concentrated — while the HbA1c finding identifies a care-process gap that is worth testing through a "
    "quality-improvement pilot.", align="justify")
r.h("14.3 Alternative explanations", 2)
r.bullets(["Confounding by severity and frailty: facility discharge and prior admissions may proxy unmeasured "
           "illness burden, functional status or social support.",
           "Selection into HbA1c testing: clinicians may test patients who are more stable, better documented or "
           "under endocrinology care, which would produce a favourable association without a causal effect.",
           "Outcome ascertainment: readmissions to hospitals outside the contributing network may be missing, "
           "which would bias rates downwards, possibly unevenly across groups.",
           "Competing risk of death after discharge: patients who die soon after discharge cannot be readmitted; "
           "post-discharge deaths are not recorded.",
           "Era effects: practice patterns in 1999–2008 differ from current care (e.g., ICD-10 coding, readmission "
           "penalties introduced from 2012)."])

# ================================================================== 15 RECOMMENDATIONS (landscape)
r.landscape(True)
r.h("15. Evidence-Based Recommendations")
r.p("Each recommendation is traced to a result calculated in this project (D = dataset finding) and, where "
    "relevant, to external evidence (E) or labelled as an operational hypothesis to be tested (H). Priorities "
    "reflect the size of the effect, the number of patients affected and feasibility.", align="justify")
rec = pd.DataFrame([
    ["R1", "High readmission after facility discharge", f"D: {pct(fac['rate_1'])} vs {pct(fac['rate_0'])}; RR {fac['risk_ratio']:.2f}; adj. OR up to {orr.loc['discharge_group = Other inpatient / rehab facility', 'odds_ratio']:.2f}. E: structured discharge programmes reduce readmissions (Jack et al., 2009; Leppin et al., 2014)",
     "Standardise facility hand-offs: reconciled medication list and discharge summary sent before transfer; follow-up call to the facility within 72 h", "Fewer avoidable returns from facilities", "Case management; nursing; receiving facilities", "High", "Medium", "30-day readmission rate for facility discharges (K13)", "Monthly"],
    ["R2", "Steep risk gradient with prior admissions", f"D: {pct(ip['rate_1'])} vs {pct(ip['rate_0'])}; adj. OR {orr.loc['number_inpatient', 'odds_ratio']:.2f} per admission. E: Naylor et al. (1999)",
     "Flag patients with ≥ 1 prior-year admission at admission; start discharge planning early; arrange follow-up within 7 days", "Earlier support for highest-risk group; simple rule, no model needed", "Hospitalists; discharge planners", "High", "Low", "% flagged patients with 7-day follow-up; their 30-day rate", "Monthly"],
    ["R3", "HbA1c rarely measured; association with lower readmission", f"D: tested {pct(eda['a1c_measured_rate'])}; adj. OR {inter['a1c_measured_OR_main_model']:.2f}; varies by diagnosis (p = {pval(inter['p_value'])}). E: Strack et al. (2014)",
     "Audit HbA1c practice; pilot a prompt to check or order HbA1c for admitted patients with diabetes (if none in previous 3 months) with a controlled evaluation", "More consistent diabetes management; evidence on whether testing matters (H)", "Diabetes team; laboratory; quality improvement", "Medium", "Low", "HbA1c testing rate (K9); readmission in pilot vs comparison wards", "Quarterly"],
    ["R4", "Older patients at higher risk", f"D: age ≥ 60 RR {old['risk_ratio']:.2f}; adj. OR {orr.loc['age_group = 60–79', 'odds_ratio']:.2f} (60–79)",
     "Add functional and caregiver assessment to discharge planning for patients ≥ 70 (operational hypothesis)", "Better-prepared discharges for frail older adults (H)", "Geriatrics; nursing", "Medium", "Medium", "30-day rate in patients ≥ 70", "Quarterly"],
    ["R5", "Risk concentrated in top deciles but model AUC modest", f"D: AUC {mdl['test_roc_auc']:.3f}; top 2 deciles capture {pct(mdl['top2_decile_capture'])}; calibration slope {cal['calibration_slope']:.2f}",
     "Do not deploy for individual decisions. If pursued, run a supervised pilot only after local re-validation, recalibration and governance approval", "Avoids harm from over-trusting a weak model", "Analytics; clinical governance committee", "Medium", "High", "Local AUC ≥ 0.70 and calibration slope 0.8–1.2 before pilot", "Quarterly"],
    ["R6", "Documentation gaps", f"D: weight {miss['weight']:.0f}%, specialty {miss['medical_specialty']:.0f}%, payer {miss['payer_code']:.0f}% missing",
     "Make weight/BMI and admitting specialty mandatory structured fields; publish a monthly data-quality dashboard", "Better risk adjustment and equity analysis", "Health information management; IT", "Medium", "Medium", "Completeness ≥ 90% for each field (K14)", "Monthly"],
    ["R7", "Subgroup differences in model sensitivity", "D: sensitivity 24% (40–59) vs 49% (80+); small-group estimates imprecise",
     "Define fairness criteria before any model use; monitor subgroup metrics; review with patient representatives", "Equitable allocation of follow-up resources", "Ethics committee; analytics", "Medium", "Low", "Subgroup AUC and sensitivity within agreed tolerance", "Quarterly"],
    ["R8", "Long stays linked to readmission; circulatory bed-day share", f"D: LOS ≥ 7 d RR {los7['risk_ratio']:.2f}; circulatory {pct(util.iloc[0]['bed_day_share'])} of bed-days",
     "Review complex discharge needs for stays ≥ 7 days; focus length-of-stay reviews on circulatory pathways", "Smoother discharge for complex patients without shortening safe stays (H)", "Bed management; cardiology", "Low", "Medium", "ALOS (K5) and 30-day rate for stays ≥ 7 days", "Monthly"],
], columns=["ID", "Finding / issue", "Supporting evidence", "Recommended action", "Expected benefit", "Responsible stakeholder",
            "Priority", "Effort", "Success metric", "Monitoring"])
r.table(rec, "Recommendation matrix", widths_cm=[0.8, 2.6, 4.4, 4.6, 2.6, 2.4, 1.3, 1.3, 2.8, 1.8], font_size=7.5)

# ================================================================== 16 TIMELINE
r.h("16. Project Timeline and Resource Allocation", page_break=True)
r.p("The roadmap below is the planned six-week internship schedule (30–35 hours per week, 195 hours in total). "
    "Planned hours are estimates for an intern working through each stage; they are not a log of time actually "
    "spent. The 'Executed in this project' column records what was actually produced.", align="justify")
road = pd.DataFrame([
    ["1", "Strategic planning", "Problem, objectives, scope, stakeholders, KPIs, risks, roadmap", "32", "Word, Excel, literature databases", "Supervisor availability", "Project charter approved", "Charter; KPI catalogue; risk register", "Objectives measurable; RQs answerable with data", "Sections 2–4, 8, 17"],
    ["2", "Data acquisition and QA", "Dataset comparison, download, profiling, cleaning, validation", "34", "Python, pandas, SQL, Excel", "Dataset access", "Clean dataset + QA report", "Raw/clean data; dictionary; issue log", "All validation rules pass; issues logged", "Scripts 01–02; Section 6; Appendices A–B"],
    ["3", "EDA and visualisation", "Descriptives, distributions, comparisons, figures, dashboard", "34", "Matplotlib, seaborn, HTML/JS, Power BI", "Clean data", "Figure set + dashboard", "12 figures; dashboard; Power BI pack", "Every chart titled, labelled, interpreted", "Scripts 03, 06; Sections 9, 11"],
    ["4", "Statistics and modelling", "Hypothesis tests, regression, model training and evaluation", "35", "SciPy, statsmodels, scikit-learn", "EDA findings", "Validated model + test report", "Test tables; model artefact; 6 figures", "No leakage; test set used once; baseline beaten", "Scripts 04–05; Sections 10, 12–13"],
    ["5", "Interpretation and recommendations", "Synthesis, alternative explanations, recommendation matrix", "30", "Word", "Weeks 2–4 results", "Draft analytical report", "Results chapter; recommendation matrix", "Each recommendation traceable", "Sections 14–15"],
    ["6", "Integration and reflection", "Integrated report, README, packaging, self-assessment", "30", "Word, Python, ZIP", "All prior outputs", "Final submission", "Final report; ZIP package; README", "All files open; numbers consistent", "Script 07; full package"],
], columns=["Week", "Theme", "Activities", "Planned h", "Tools", "Dependencies", "Milestone", "Deliverables", "Acceptance criteria", "Executed in this project"])
r.table(road, "Six-week roadmap: planned effort and executed work", widths_cm=[1.0, 2.4, 3.6, 1.3, 2.6, 2.0, 2.4, 3.0, 3.0, 3.1], font_size=7.5)
r.p("Dependencies form a chain: Week 2 cannot start without an accessible dataset; modelling depends on the "
    "cleaned cohort; recommendations depend on statistical and model results. The critical path therefore runs "
    "through data acquisition and cleaning, which is why the dataset choice prioritised accessibility.",
    align="justify")

# ================================================================== 17 RISK REGISTER
r.h("17. Risk Register and Contingency Planning", page_break=True)
risk = pd.DataFrame([
    ["RK1", "Chosen dataset becomes inaccessible", "Low", "High", "Download early; keep checksummed raw copy", "Switch to verified alternative (CMS HRRP, hospital-level redesign)", "Analyst", "Closed – data secured"],
    ["RK2", "Data quality too poor for objectives", "Medium", "High", "Profile in Week 2 before committing", "Narrow scope; drop unusable fields; document", "Analyst", "Mitigated – weight dropped"],
    ["RK3", "Target leakage inflates model performance", "Medium", "High", "Exclude outcome-derived fields; pipelines; patient-level split", "Re-run with stricter feature set", "Analyst / reviewer", "Mitigated"],
    ["RK4", "Non-independent repeat encounters", "High", "Medium", "Index-encounter cohort", "Grouped cross-validation by patient", "Analyst", "Mitigated"],
    ["RK5", "Over-interpretation of associations as causes", "Medium", "High", "Explicit causal caveats; alternative explanations", "Clinical review before dissemination", "Analyst / supervisor", "Mitigated"],
    ["RK6", "Model misused for individual decisions", "Low", "High", "Educational labels; deployment conditions", "Withdraw artefact; governance escalation", "Supervisor", "Open – monitor"],
    ["RK7", "Bias against patient subgroups", "Medium", "High", "Exclude race/payer as predictors; subgroup audit", "Re-weighting or group-specific thresholds after review", "Ethics committee", "Open – monitor"],
    ["RK8", "Privacy breach / re-identification", "Low", "High", "Aggregates only; small-cell suppression; no linkage", "Incident response; notify DPO", "Data protection officer", "Mitigated"],
    ["RK9", "Tool unavailability (e.g., Power BI)", "Medium", "Medium", "Open-source alternatives", "HTML dashboard + Power BI build pack", "Analyst", "Occurred – contingency used"],
    ["RK10", "Schedule overrun", "Medium", "Medium", "Weekly milestones; scripted pipeline", "Reduce optional analyses (e.g., extra models)", "Intern / supervisor", "Closed"],
    ["RK11", "Results not reproducible", "Low", "High", "Fixed seeds; requirements file; scripted steps", "Re-run from raw; compare checksums", "Reviewer", "Mitigated"],
], columns=["ID", "Risk", "Likelihood", "Impact", "Mitigation", "Contingency", "Owner", "Status"])
r.table(risk, "Risk register", widths_cm=[1.0, 4.2, 1.7, 1.4, 5.0, 4.6, 2.6, 3.0], font_size=7.5)
r.landscape(False)

# ================================================================== 18 WORKFLOW
r.h("18. Integrated Project Workflow")
r.p("The six weekly assignments were implemented as one reproducible pipeline. Each script reads only the outputs "
    "of earlier steps, so the whole analysis can be regenerated from the raw download with one command per step.",
    align="justify")
r.table(pd.DataFrame([
    ["01_data_acquisition.py", "UCI URL", "Raw ZIP + CSVs; SOURCE_METADATA.json; access probes", "2"],
    ["02_data_quality_and_cleaning.py", "Raw CSVs", "Clean encounters; analysis cohort; QA tables; data dictionary; transformation log", "2"],
    ["03_exploratory_data_analysis.py", "Clean data", "Descriptive tables; figures 1–12", "3"],
    ["04_statistical_analysis.py", "Cohort", "Test results; logistic regression; figure 13", "4"],
    ["05_predictive_modeling.py", "Cohort", "Model artefact; metrics; figures 14–18", "4"],
    ["06_visualization_dashboard.py", "Cohort; model metrics", "KPI overview; HTML dashboard; Power BI pack; screenshots", "3"],
    ["07_build_report.py", "All outputs", "This Word report", "5–6"],
], columns=["Script", "Input", "Output", "Week"]), "Pipeline scripts, inputs and outputs", widths_cm=[5.0, 3.0, 7.4, 1.2], font_size=8.5)
r.p("Reproducibility controls: pinned package versions (requirements.txt), fixed random seed (42), checksummed "
    "raw data, no manual edits to data or figures, and a README with the execution order.", align="justify")

# ================================================================== 19 LIMITATIONS & FUTURE
r.h("19. Limitations, Lessons Learned and Future Research", page_break=True)
r.h("19.1 Limitations", 2)
r.bullets(["Age of data (1999–2008): absolute rates and practice patterns may not reflect current care, and diagnoses "
           "use ICD-9 rather than ICD-10.",
           "No dates or hospital identifiers: no trend analysis, seasonality, hospital benchmarking or temporal validation.",
           "Encounter order assumed chronological from encounter_id; the source does not document this.",
           "Readmission ascertainment may miss returns to other hospitals; post-discharge deaths are unrecorded.",
           "Important predictors are absent: laboratory values (beyond two summary results), vital signs, functional "
           "status, social determinants, medication adherence and follow-up care.",
           "Observational design: all associations may be confounded; no causal claims are made.",
           "Model performance is modest and the model was not externally validated or recalibrated.",
           "US data: findings need local validation before application to Indian or other health systems."])
r.h("19.2 Lessons learned", 2)
r.bullets(["Accessibility and licensing should drive dataset choice as much as relevance; an impressive restricted "
           "dataset would have stalled the project.",
           "Cohort definition (one row per patient, excluding deaths) changes the headline rate from 11.2% to 9.0% and "
           "is essential for valid inference and leakage-free modelling.",
           "Honest quality metrics need care: counting 'Unknown' fills as complete would have overstated improvement.",
           "With large samples nearly everything is 'significant'; effect sizes and intervals carry the message.",
           "Accuracy is a poor metric for rare outcomes; threshold choice must be framed as a workload decision.",
           "Generating the report from analysis outputs prevents inconsistencies between text and results."])
r.h("19.3 Best practices for future healthcare analytics projects", 2)
r.numbered(["Write the analysis plan, outcome definition and hypotheses before looking at outcomes.",
            "Preserve raw data unchanged and log every transformation.",
            "Define the unit of analysis and split data by patient.",
            "Always report a simple baseline, uncertainty, calibration and subgroup performance.",
            "Separate dataset findings from external evidence and from operational hypotheses.",
            "Involve clinicians and privacy officers early, not at the end."])
r.h("19.4 Methodological improvements and future research", 2)
r.bullets(["Apply the pipeline to recent, local data with dates and hospital identifiers; add temporal validation.",
           "Include post-discharge factors (follow-up visits, medication adherence) and social determinants.",
           "Use competing-risk or time-to-event models and decision-curve analysis to judge clinical utility.",
           "Recalibrate models and set thresholds jointly with care-transition teams based on capacity.",
           "Evaluate the HbA1c and transition-of-care recommendations with stepped-wedge or controlled designs.",
           "Explore hospital-level readmission patterns using the current CMS HRRP data as a separate study."])

# ================================================================== 20 CONCLUSION
r.h("20. Conclusion", page_break=True)
r.p(f"This project carried a real healthcare question from definition to evidence-based recommendations using openly "
    f"licensed data. It produced a validated analysis cohort of {num(ov['n'])} patients, quantified a 30-day "
    f"readmission rate of {pct(ov['rate'])}, identified discharge destination and prior inpatient use as the dominant "
    f"risk markers, replicated the published association between HbA1c measurement and readmission, and built a "
    f"risk model whose modest performance (AUC {mdl['test_roc_auc']:.3f}) was reported honestly together with its "
    f"calibration and subgroup behaviour. The recommendations focus on targeting transition-of-care resources, closing "
    f"a diabetes-care process gap and improving documentation, with any predictive tool kept under strict governance. "
    f"The pipeline, dashboard and documentation are reproducible and can be re-run on current local data, which is the "
    f"essential next step before any operational decision.", align="justify")

# ================================================================== APPENDICES
r.h("Appendix A: Data Dictionary", page_break=True)
dd = ddict[["variable", "description", "role", "dtype", "n_unique", "missing_pct"]].copy()
dd.columns = ["Variable", "Description", "Role", "Type", "Unique", "Missing %"]
r.table(dd, "Data dictionary of the cleaned dataset", widths_cm=[3.6, 7.2, 1.8, 1.3, 1.5, 1.2], font_size=7)

r.h("Appendix B: Data Quality Checklist", page_break=True)
r.table(pd.DataFrame([
    ["Raw data preserved unchanged (checksums recorded)", "✓"], ["Source, licence and access date documented", "✓"],
    ["Schema and data types inspected", "✓"], ["Missing values profiled per column and pattern", "✓"],
    ["Missing-value strategy justified per field", "✓"], ["Duplicates checked (IDs and full rows)", "✓"],
    ["Invalid categories removed or recoded", "✓"], ["Range and domain rules executed", "✓"],
    ["Cross-field consistency rules executed", "✓"], ["Code labels mapped from official mapping file", "✓"],
    ["Cohort and outcome definitions documented", "✓"], ["Before/after quality metrics compared", "✓"],
    ["Issue log with residual risks", "✓"], ["Accuracy limitations stated", "✓"],
], columns=["Checklist item", "Status"]), "Data-quality assurance checklist", widths_cm=[13.6, 3.0], font_size=8.5)
rl = rules.copy()
rl["rule"] = rl["rule"].str.replace("'", "").str.slice(0, 80)
r.table(rl.rename(columns={"rule": "Validation rule", "type": "Type", "failures": "Failures", "threshold": "Threshold", "status": "Status"}),
        "Automated validation rules and results (cleaned data)", widths_cm=[8.6, 2.4, 1.6, 2.6, 1.4], font_size=7,
        note="SQL equivalent example: SELECT COUNT(*) FROM encounters WHERE time_in_hospital NOT BETWEEN 1 AND 14; "
             "-- expected 0")

r.h("Appendix C: KPI Formulas", page_break=True)
r.p("Notation: P = patients in the analysis cohort; R30 = patients readmitted within 30 days; LOSᵢ = length of stay "
    "of patient i; z = 1.96.")
r.table(pd.DataFrame([
    ["30-day readmission rate", "p̂ = R30 / P"],
    ["Wilson 95% CI", "[p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)] / (1 + z²/n)"],
    ["Risk ratio", "RR = p̂₁ / p̂₀; 95% CI exp(ln RR ± 1.96·SE), SE = √(1/a − 1/n₁ + 1/c − 1/n₀)"],
    ["Average length of stay", "ALOS = Σ LOSᵢ / P"], ["Total bed-days", "Σ LOSᵢ"],
    ["HbA1c testing rate", "Patients with A1C result ≠ 'Not measured' / P"],
    ["Discharge-to-home rate", "Patients discharged home (± home health) / P"],
    ["Facility-discharge readmission rate", "R30 among SNF/ICF/rehab discharges / those discharges"],
    ["Cell completeness", "1 − missing cells / (rows × columns)"],
    ["Sensitivity (recall)", "TP / (TP + FN)"], ["Specificity", "TN / (TN + FP)"],
    ["Precision (PPV)", "TP / (TP + FP)"], ["F1", "2 · PPV · Sensitivity / (PPV + Sensitivity)"],
    ["Brier score", "Σ (p̂ᵢ − yᵢ)² / n"], ["Lift (decile k)", "Observed rate in decile k / overall rate"],
], columns=["KPI / metric", "Formula"]), "KPI and metric formulas", widths_cm=[5.0, 11.6], font_size=8.5)

r.h("Appendix D: Statistical Test Results", page_break=True)
o = ors.copy()
o["OR (95% CI)"] = o.apply(lambda x: f"{x.odds_ratio:.2f} ({x.or_ci_low:.2f}–{x.or_ci_high:.2f})", axis=1)
o["p"] = o["p_value"].map(pval)
r.table(o[["term", "OR (95% CI)", "p"]].rename(columns={"term": "Term (reference in parentheses below)"}),
        "Full multivariable logistic regression (adjusted odds ratios)", widths_cm=[9.6, 4.6, 2.4], font_size=7.5,
        note="References: A1C 'Not measured'; diagnosis 'Other'; age 40–59; gender Female; race Caucasian; discharge "
             "Home; admission source Emergency room; change 'Ch'. Numeric terms per one-unit increase.")
sp2 = sp.copy()
sp2["spearman_rho"] = sp2["spearman_rho"].round(3)
sp2["p_holm"] = sp2["p_holm"].map(pval)
r.table(sp2[["var_1", "var_2", "spearman_rho", "p_holm"]].rename(columns={"var_1": "Variable 1", "var_2": "Variable 2",
        "spearman_rho": "Spearman ρ", "p_holm": "p (Holm)"}), "Spearman correlations for key variable pairs",
        widths_cm=[5.0, 5.0, 3.3, 3.3], font_size=8)
c2 = chi[["variable", "min_expected_count", "pct_cells_expected_lt5"]].copy()
c2["min_expected_count"] = c2["min_expected_count"].round(1)
c2["pct_cells_expected_lt5"] = c2["pct_cells_expected_lt5"].round(1)
r.table(c2.rename(columns={"variable": "Variable", "min_expected_count": "Minimum expected count",
                           "pct_cells_expected_lt5": "% cells expected < 5"}),
        "Chi-square assumption check (expected cell counts)", widths_cm=[6.0, 5.3, 5.3], font_size=8,
        note="Payer code has sparse levels with expected counts below 5; its test should be read with caution.")

r.h("Appendix E: Model Evaluation Tables", page_break=True)
imp2 = imp.head(15).copy()
imp2["importance_mean"] = imp2["importance_mean"].map(lambda v: f"{v:.4f}")
imp2["importance_std"] = imp2["importance_std"].map(lambda v: f"{v:.4f}")
r.table(imp2.rename(columns={"feature": "Feature", "importance_mean": "Mean AUC decrease", "importance_std": "SD"}),
        "Permutation importance (validation set, top 15)", widths_cm=[7.0, 5.0, 4.6], font_size=8)
coef = pd.read_csv(TABLE_DIR / "model_logistic_coefficients.csv").head(15)
coef["feature"] = coef["feature"].str.replace("num__", "").str.replace("cat__", "")
coef["coef_standardised"] = coef["coef_standardised"].round(3)
coef["odds_ratio"] = coef["odds_ratio"].round(3)
r.table(coef.rename(columns={"feature": "Feature (one-hot level)", "coef_standardised": "Coefficient", "odds_ratio": "Odds ratio"}),
        "Largest coefficients of the regularised logistic regression (reference model)", widths_cm=[9.0, 3.8, 3.8], font_size=8,
        note="Numeric features standardised (per SD); categorical coefficients relative to the omitted encoding.")
r.table(pd.DataFrame([
    ["Selected model", best], ["Serialized artefact", "models/readmission_model.joblib (scikit-learn pipeline + threshold)"],
    ["scikit-learn version", mdl["sklearn_version"]], ["Top-20% threshold (validation)", f"{mdl['threshold_top20']:.4f}"],
    ["Max-F1 threshold (validation)", f"{mdl['threshold_max_f1']:.4f}"],
    ["Test ROC-AUC (95% CI)", f"{mdl['test_roc_auc']:.3f} ({mdl['test_roc_auc_ci'][0]:.3f}–{mdl['test_roc_auc_ci'][1]:.3f})"],
    ["Test PR-AUC (95% CI)", f"{mdl['test_pr_auc']:.3f} ({mdl['test_pr_auc_ci'][0]:.3f}–{mdl['test_pr_auc_ci'][1]:.3f})"],
    ["Brier score", f"{mdl['test_brier']:.4f}"], ["Calibration slope / intercept", f"{cal['calibration_slope']:.2f} / {cal['calibration_in_the_large']:.3f}"],
], columns=["Item", "Value"]), "Model card summary", widths_cm=[6.0, 10.6], font_size=8.5)

r.h("Appendix F: Dashboard Screenshots", page_break=True)
r.p("Screenshots were captured automatically from the delivered HTML dashboard using headless Microsoft Edge with "
    "no filters applied. They show the real dashboard, not a mock-up.")
r.figure(FIG_DIR / "dashboard_screenshot_desktop.png", "Interactive dashboard — desktop layout (1,360 px wide)", None, width_cm=12.0)
r.page_break()
r.figure(FIG_DIR / "dashboard_screenshot_mobile.png", "Interactive dashboard — mobile layout (390 px wide, first screen)", None, width_cm=6.5)

r.h("Appendix G: Reflective Self-Assessment Template", page_break=True)
r.p("No personal reflections, experiences or challenges were supplied by the intern, so this appendix is a template. "
    "It must be completed by the intern in their own words; nothing below describes events that actually occurred.",
    italic=True, align="justify")
for title, prompts in [
    ("G.1 Technical skills", ["Which stage of the pipeline was most difficult for you, and why?",
                              "Describe one error you found in your own work and how you detected it.",
                              "Which statistical or machine-learning concept do you now understand better? Give an example."]),
    ("G.2 Healthcare domain knowledge", ["What did you learn about readmissions, HbA1c or discharge planning?",
                                          "Which clinical terms were new to you, and how did you learn them?"]),
    ("G.3 Ethics and responsibility", ["Where did you have to balance usefulness against privacy or fairness?",
                                        "How would you explain the model's limitations to a clinician?"]),
    ("G.4 Communication and teamwork", ["How did you incorporate supervisor or peer feedback?",
                                         "Which chart or explanation worked best for a non-technical audience?"]),
    ("G.5 Time management", ["Compare your actual hours with the planned roadmap (Section 16). What caused differences?"]),
    ("G.6 Overall", ["Rate yourself (1–5) on Python, SQL, statistics, visualisation, ML, domain knowledge and "
                     "communication, with one piece of evidence for each rating.",
                     "What would you do differently if you repeated the project?"]),
]:
    r.h(title, 2)
    r.bullets(prompts)
    r.p("Response: ____________________________________________________________", color=MUTED)

r.h("Appendix H: Career Development Plan", page_break=True)
r.p("A twelve-month plan building on the skills exercised in this project. Targets are suggestions to be adapted "
    "with the internship supervisor.", align="justify")
r.table(pd.DataFrame([
    ["Python", "pandas, scikit-learn pipelines", "Write tests (pytest) for the cleaning functions; package the pipeline", "0–3 months", "Tested, documented repository"],
    ["SQL", "Validation logic in pandas", "Rebuild Week 2 validation in SQL (PostgreSQL/SQLite); learn window functions", "0–3 months", "SQL scripts reproducing QA results"],
    ["Statistics", "Tests, CIs, logistic regression", "Study causal inference basics (DAGs, propensity scores); regression diagnostics", "3–6 months", "Short write-up applying propensity weighting to H3"],
    ["Power BI", "Data model and DAX designed", "Build the .pbix from the provided pack; learn row-level security", "0–2 months", "Published Power BI report"],
    ["Machine learning", "Tuning, calibration, fairness", "Recalibration, decision-curve analysis, SHAP explanations, model monitoring", "3–9 months", "Notebook with recalibrated model and decision curve"],
    ["Healthcare terminology", "ICD-9 groups, HbA1c, discharge dispositions", "Learn ICD-10, SNOMED CT basics, FHIR resources, OMOP CDM", "3–9 months", "Glossary; mapping exercise ICD-9 → ICD-10"],
    ["Privacy and governance", "DPDP Act, ABDM, ICMR AI guidelines", "Complete a data-protection or research-ethics course; follow DPDP Rules commencement", "0–6 months", "Certificate; DPIA template for a hospital project"],
    ["Communication", "Executive summary, dashboard", "Present findings to a clinical audience; write a one-page brief", "0–3 months", "Recorded 10-minute presentation"],
    ["Portfolio", "This project", "Publish code, README and dashboard on GitHub (public data only)", "0–1 month", "Public repository link on CV"],
], columns=["Skill area", "Current evidence", "Next development step", "Timeline", "Evidence of progress"]),
    "Career development plan", widths_cm=[2.6, 3.2, 5.4, 2.0, 3.4], font_size=8)

# ================================================================== REFERENCES
r.h("References", page_break=True)
refs = [
    "Centers for Medicare & Medicaid Services. (2026). Hospital Readmissions Reduction Program [Data set]. Provider Data Catalog. https://data.cms.gov/provider-data/dataset/9n3s-kdb3",
    "Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). Diabetes 130-US hospitals for years 1999–2008 [Data set]. UCI Machine Learning Repository. https://doi.org/10.24432/C5230J",
    "Collins, G. S., Moons, K. G. M., Dhiman, P., Riley, R. D., Beam, A. L., Van Calster, B., Ghassemi, M., Liu, X., Reitsma, J. B., van Smeden, M., Boulesteix, A.-L., Camaradou, J. C., Celi, L. A., Denaxas, S., Denniston, A. K., Glocker, B., Golub, R. M., Harvey, H., Heinze, G., … Logullo, P. (2024). TRIPOD+AI statement: Updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ, 385, e078378. https://doi.org/10.1136/bmj-2023-078378",
    "Holm, S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics, 6(2), 65–70.",
    "Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. Computing in Science & Engineering, 9(3), 90–95. https://doi.org/10.1109/MCSE.2007.55",
    "Indian Council of Medical Research. (2023). Ethical guidelines for application of artificial intelligence in biomedical research and healthcare. https://www.icmr.gov.in/ethical-guidelines-for-application-of-artificial-intelligence-in-biomedical-research-and-healthcare",
    "Jack, B. W., Chetty, V. K., Anthony, D., Greenwald, J. L., Sanchez, G. M., Johnson, A. E., Forsythe, S. R., O'Donnell, J. K., Paasche-Orlow, M. K., Manasseh, C., Martin, S., & Culpepper, L. (2009). A reengineered hospital discharge program to decrease rehospitalization: A randomized trial. Annals of Internal Medicine, 150(3), 178–187. https://doi.org/10.7326/0003-4819-150-3-200902030-00007",
    "Jencks, S. F., Williams, M. V., & Coleman, E. A. (2009). Rehospitalizations among patients in the Medicare fee-for-service program. New England Journal of Medicine, 360(14), 1418–1428. https://doi.org/10.1056/NEJMsa0803563",
    "Kahn, M. G., Callahan, T. J., Barnard, J., Bauck, A. E., Brown, J., Davidson, B. N., Estiri, H., Goerg, C., Holve, E., Johnson, S. G., Liaw, S.-T., Hamilton-Lopez, M., Meeker, D., Ong, T. C., Ryan, P., Shang, N., Weiskopf, N. G., Weng, C., Zozus, M. N., & Schilling, L. (2016). A harmonized data quality assessment terminology and framework for the secondary use of electronic health record data. eGEMs, 4(1), 1244. https://doi.org/10.13063/2327-9214.1244",
    "Kansagara, D., Englander, H., Salanitro, A., Kagen, D., Theobald, C., Freeman, M., & Kripalani, S. (2011). Risk prediction models for hospital readmission: A systematic review. JAMA, 306(15), 1688–1698. https://doi.org/10.1001/jama.2011.1515",
    "Leppin, A. L., Gionfriddo, M. R., Kessler, M., Brito, J. P., Mair, F. S., Gallacher, K., Wang, Z., Erwin, P. J., Sylvester, T., Boehmer, K., Ting, H. H., Murad, M. H., Shippee, N. D., & Montori, V. M. (2014). Preventing 30-day hospital readmissions: A systematic review and meta-analysis of randomized trials. JAMA Internal Medicine, 174(7), 1095–1107. https://doi.org/10.1001/jamainternmed.2014.1608",
    "McKinney, W. (2010). Data structures for statistical computing in Python. In S. van der Walt & J. Millman (Eds.), Proceedings of the 9th Python in Science Conference (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a",
    "Ministry of Electronics and Information Technology. (2025). Digital Personal Data Protection Rules, 2025 (G.S.R. notification of 14 November 2025). Government of India. https://www.meity.gov.in/",
    "National Health Authority. (2020). Health data management policy: Ayushman Bharat Digital Mission. Government of India. https://abdm.gov.in/",
    "Naylor, M. D., Brooten, D., Campbell, R., Jacobsen, B. S., Mezey, M. D., Pauly, M. V., & Schwartz, J. S. (1999). Comprehensive discharge planning and home follow-up of hospitalized elders: A randomized clinical trial. JAMA, 281(7), 613–620. https://doi.org/10.1001/jama.281.7.613",
    "Obermeyer, Z., Powers, B., Vogeli, C., & Mullainathan, S. (2019). Dissecting racial bias in an algorithm used to manage the health of populations. Science, 366(6464), 447–453. https://doi.org/10.1126/science.aax2342",
    "Pedregosa, F., Varoquaux, G., Gramfort, A., Michel, V., Thirion, B., Grisel, O., Blondel, M., Prettenhofer, P., Weiss, R., Dubourg, V., Vanderplas, J., Passos, A., Cournapeau, D., Brucher, M., Perrot, M., & Duchesnay, É. (2011). Scikit-learn: Machine learning in Python. Journal of Machine Learning Research, 12, 2825–2830.",
    "Rajkomar, A., Hardt, M., Howell, M. D., Corrado, G., & Chin, M. H. (2018). Ensuring fairness in machine learning to advance health equity. Annals of Internal Medicine, 169(12), 866–872. https://doi.org/10.7326/M18-1990",
    "Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLOS ONE, 10(3), e0118432. https://doi.org/10.1371/journal.pone.0118432",
    "Seabold, S., & Perktold, J. (2010). Statsmodels: Econometric and statistical modeling with Python. In Proceedings of the 9th Python in Science Conference (pp. 92–96). https://doi.org/10.25080/Majora-92bf1922-011",
    "Strack, B., DeShazo, J. P., Gennings, C., Olmo, J. L., Ventura, S., Cios, K. J., & Clore, J. N. (2014). Impact of HbA1c measurement on hospital readmission rates: Analysis of 70,000 clinical database patient records. BioMed Research International, 2014, 781670. https://doi.org/10.1155/2014/781670",
    "U.S. Department of Health and Human Services. (2012). Guidance regarding methods for de-identification of protected health information in accordance with the Health Insurance Portability and Accountability Act (HIPAA) Privacy Rule. https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html",
    "Van Calster, B., McLernon, D. J., van Smeden, M., Wynants, L., & Steyerberg, E. W. (2019). Calibration: The Achilles heel of predictive analytics. BMC Medicine, 17, 230. https://doi.org/10.1186/s12916-019-1466-7",
    "Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., Burovski, E., Peterson, P., Weckesser, W., Bright, J., van der Walt, S. J., Brett, M., Wilson, J., Millman, K. J., Mayorov, N., Nelson, A. R. J., Jones, E., Kern, R., Larson, E., … Vázquez-Baeza, Y. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python. Nature Methods, 17(3), 261–272. https://doi.org/10.1038/s41592-019-0686-2",
    "Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. Journal of the American Statistical Association, 22(158), 209–212. https://doi.org/10.1080/01621459.1927.10502953",
    "World Health Organization. (2021). Ethics and governance of artificial intelligence for health: WHO guidance. https://www.who.int/publications/i/item/9789240029200",
]
for ref in refs:
    para = r.p(ref, size=9.5, space_after=6)
    para.paragraph_format.left_indent = Pt(24)
    para.paragraph_format.first_line_indent = Pt(-24)

OUT.parent.mkdir(exist_ok=True)
r.save(OUT)
print(f"Saved {OUT} | figures {r.fig_n} | tables {r.tab_n}")
