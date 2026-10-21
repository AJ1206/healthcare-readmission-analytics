# Power BI build guide — Diabetes Readmission Dashboard

A `.pbix` file is **not** included: Power BI Desktop is a Windows GUI application that could not be
automated in this project environment. Everything needed to rebuild the dashboard in about 30–45
minutes is provided instead.

## 1. Files

| File | Purpose |
|---|---|
| `fact_encounters.csv` | One row per patient (index encounter), 69,970 rows, numeric measures + foreign keys |
| `dim_diagnosis.csv`, `dim_discharge.csv`, `dim_admission_type.csv`, `dim_age_group.csv`, `dim_race.csv`, `dim_a1c.csv` | Dimension tables (key + label) |
| `DAX_measures.dax` | All measures, ready to paste |

## 2. Data model (star schema)

```
dim_diagnosis (diagnosis_key) 1 ──* fact_encounters
dim_discharge (discharge_key) 1 ──* fact_encounters
dim_admission_type (admission_type_key) 1 ──* fact_encounters
dim_age_group (age_group_key) 1 ──* fact_encounters
dim_race (race_key) 1 ──* fact_encounters
dim_a1c (a1c_key) 1 ──* fact_encounters
```
All relationships: single direction, dimension filters fact.

## 3. Steps

1. **Get Data → Text/CSV**: load all seven CSV files. In Power Query set `readmit_30`, `A1C_measured`,
   `any_prior_inpatient` and all count columns to *Whole Number*.
2. **Model view**: create the six relationships above (drag `*_key` from each dimension to the fact table).
3. **New measure**: paste each measure from `DAX_measures.dax`. Format rates as Percentage (1 decimal).
4. **Page 1 — Overview**
   - Six **Card** visuals: Patients, Readmission Rate 30d, Readmissions 30d, Average LOS, HbA1c Testing Rate,
     Prior Inpatient Share. Add the CI Low/High measures to the readmission card's subtitle (or a multi-row card).
   - **Slicers** (one row across the top): dim_age_group, fact_encounters[gender], dim_race, dim_diagnosis,
     dim_admission_type.
   - **Clustered bar charts** (Y = dimension label, X = `Readmission Rate (reportable)`), sorted descending, with
     error bars (Analytics pane → Error bars → upper = CI High, lower = CI Low) for: discharge destination,
     primary diagnosis, prior inpatient admissions (`number_inpatient` binned 0/1/2/3+), age band.
   - **Column chart**: `time_in_hospital` on X, Patients on Y (length-of-stay distribution).
   - Add a constant line at `Overall Readmission Rate` on each bar chart.
5. **Accessibility**: use one colour for all bars (no rank-based colouring); enable data labels selectively; set
   alt text on every visual; add a **Table** visual with `Small Sample Flag` so suppressed groups are explained.
6. **Explanatory text box**: cohort definition, outcome definition, data period (1999–2008), "association not
   causation", and "educational use only".

## 4. Validation

After building, check that with no filters applied: Patients = 69,970; Readmission Rate 30d =
8.97%; Average LOS = 4.27. These match the Python
analysis and the HTML dashboard.
