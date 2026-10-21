# End-to-End Healthcare Data Analytics — Diabetic Inpatient 30-Day Readmission

A complete, reproducible six-week internship project: data acquisition, quality assurance, exploratory and
statistical analysis, predictive modelling, an interactive dashboard and an integrated Word report, all
built on real, openly licensed hospital data.

> **Educational use only.** The predictive model has not been clinically or institutionally validated and
> must not be used to make decisions about individual patients.

## About this repository

To keep the repository small, these generated files are **not committed**. Running the pipeline recreates them:

| Not in repo | Recreated by |
|---|---|
| `data/raw/` (UCI download, ~21 MB) | `src/01_data_acquisition.py` (downloads from UCI and records a checksum) |
| `data/processed/` (cleaned data, ~62 MB) | `src/02_data_quality_and_cleaning.py` |
| `models/readmission_model.joblib` (~20 MB) | `src/05_predictive_modeling.py` |
| `dashboard/powerbi/*.csv` (Power BI tables) | `src/06_visualization_dashboard.py` |

Everything needed to review the work without running anything is included: the final report (`report/`), all
figures and result tables (`outputs/`), model metrics (`models/model_metrics.json`) and the interactive
dashboard (`dashboard/healthcare_readmission_dashboard.html`).

## Dataset

| | |
|---|---|
| Title | Diabetes 130-US Hospitals for Years 1999–2008 |
| Creators | Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014) |
| Publisher | UCI Machine Learning Repository — https://doi.org/10.24432/C5230J |
| Download | https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip |
| Licence | CC BY 4.0 (redistribution with attribution permitted) |
| Size | 101,766 inpatient encounters, 71,518 patients, 50 columns |
| Outcome | `readmitted`: `<30` days, `>30` days, `NO` |

Provenance (access timestamp, SHA-256 checksums) is written to `data/raw/SOURCE_METADATA.json`.
The dataset has no admission dates, hospital identifiers or costs, so time trends, hospital benchmarking and
cost analysis are out of scope.

## Project structure

```
Healthcare_Analytics_Project/
├── run_pipeline.py                 # runs steps 01–07 in order
├── requirements.txt
├── src/
│   ├── common.py, viz_style.py, docx_helpers.py, dashboard_template.html
│   ├── 01_data_acquisition.py      # download, checksum, provenance, probe alternative datasets
│   ├── 02_data_quality_and_cleaning.py
│   ├── 03_exploratory_data_analysis.py
│   ├── 04_statistical_analysis.py
│   ├── 05_predictive_modeling.py
│   ├── 06_visualization_dashboard.py
│   ├── 07_build_report.py
│   └── update_word_fields.ps1      # refreshes TOC/lists in Word (Windows)
├── data/raw/                       # untouched ZIP + CSVs + SOURCE_METADATA.json
├── data/processed/                 # cleaned encounters; analysis cohort (one row per patient)
├── docs/                           # data dictionary, transformation log, dataset access probes
├── outputs/figures/                # 19 analysis charts + 2 dashboard screenshots (PNG, 200 dpi)
├── outputs/tables/                 # all result tables (CSV/JSON)
├── models/                         # readmission_model.joblib, model_metrics.json
├── dashboard/                      # healthcare_readmission_dashboard.html + powerbi/ build pack
└── report/Healthcare_Data_Analytics_Final_Report.docx
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

## Reproducing the analysis

```bash
python run_pipeline.py           # all steps (about 8–12 minutes; model tuning is the slow part)
python run_pipeline.py --from 3  # re-run from a given step
```

Then refresh the Word report's table of contents, lists of figures/tables and page numbers:

- Windows with Word: `powershell -ExecutionPolicy Bypass -File src/update_word_fields.ps1 -Docx "<full path to report docx>"`
- Otherwise: open the report in Word, press **Ctrl+A**, then **F9**.

All randomness uses seed 42, so results are identical between runs on the same package versions.

## Outputs

| Output | Location |
|---|---|
| Final report (60 pages, 21 figures, 42 tables) | `report/Healthcare_Data_Analytics_Final_Report.docx` |
| Interactive dashboard (open in any browser, works offline) | `dashboard/healthcare_readmission_dashboard.html` |
| Power BI star schema, DAX measures, build guide | `dashboard/powerbi/` |
| Trained model (scikit-learn pipeline + threshold) | `models/readmission_model.joblib` |
| Data dictionary / transformation log | `docs/data_dictionary.csv`, `docs/transformation_log.csv` |
| Data-quality report (before/after, rules, issue log) | `outputs/tables/data_quality_*.csv` |

Loading the model (same scikit-learn version required):

```python
import joblib, pandas as pd
bundle = joblib.load("models/readmission_model.joblib")
cohort = pd.read_csv("data/processed/diabetes_index_encounters.csv")
risk = bundle["model"].predict_proba(cohort[bundle["features"]])[:, 1]
```

## Key findings (analysis cohort: 69,970 patients, first eligible encounter each)

- **30-day readmission:** 8.97% (95% CI 8.76–9.18%); 11.2% if all encounters are counted.
- **Discharge to a care facility:** 15.2% vs 7.5% (risk ratio 2.03); adjusted OR 2.95 for rehabilitation/other
  inpatient facilities and 1.81 for skilled nursing, versus home.
- **Prior-year inpatient admission:** 15.4% vs 8.1% (RR 1.90); adjusted OR 1.42 per prior admission.
- **HbA1c measured in only 18.4% of patients;** measurement associated with lower readmission (adjusted OR 0.92,
  95% CI 0.85–0.99), varying by primary diagnosis (interaction p = 0.009), replicating Strack et al. (2014).
- **Resource use:** mean length of stay 4.27 days; circulatory conditions account for 29.8% of bed-days.
- **Model:** random forest, test ROC-AUC 0.649 (95% CI 0.634–0.664), PR-AUC 0.174 (prevalence 9.0%). Flagging the
  top 20% of risk finds 36.8% of readmissions at 17.0% precision. This is modest performance, typical of
  administrative-data readmission models.

## Limitations and ethics

- Data are from 1999–2008 (ICD-9 era); absolute rates may not reflect current care.
- Observational data: all associations may be confounded; no causal claims are made.
- No external or temporal validation was possible; the model's calibration slope (1.26) shows compressed risk estimates.
- Race and payer are excluded as model inputs; subgroup performance is audited instead.
- The dashboard suppresses rates for groups with fewer than 30 patients.
- Indian context: the DPDP Act 2023 and DPDP Rules 2025 (core obligations from 14 May 2027) would apply to any
  re-use on identifiable Indian patient data; see report Section 7.

## Not included

- **Power BI `.pbix`:** Power BI Desktop cannot be automated in the build environment. A star-schema data model,
  DAX measures and a step-by-step guide are in `dashboard/powerbi/`.
- **Self-assessment:** the report's Appendix G is a template for the intern to complete.

## Citation

Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). *Diabetes 130-US hospitals for years 1999–2008* [Data set].
UCI Machine Learning Repository. https://doi.org/10.24432/C5230J

## Licence

Code: [MIT](LICENSE). Data: CC BY 4.0, as published by the UCI Machine Learning Repository (attribution above).
