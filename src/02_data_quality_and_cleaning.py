"""Step 2 - Data profiling, validation, cleaning and quality assurance.

Inputs : data/raw/uci_diabetes_130/diabetic_data.csv, IDS_mapping.csv (never modified)
Outputs: data/processed/diabetes_encounters_clean.csv   (all valid encounters, with flags)
         data/processed/diabetes_index_encounters.csv   (analysis cohort: first encounter per
                                                          patient, alive and not discharged to hospice)
         outputs/tables/data_quality_*.csv, docs/data_dictionary.csv, docs/transformation_log.csv
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CLEAN_CSV, DOCS_DIR, IDS_MAPPING_CSV, INDEX_COHORT_CSV, RAW_CSV,  # noqa: E402
                    TABLE_DIR, get_logger, save_json)

log = get_logger("cleaning")

MED_COLS = ["metformin", "repaglinide", "nateglinide", "chlorpropamide", "glimepiride", "acetohexamide",
            "glipizide", "glyburide", "tolbutamide", "pioglitazone", "rosiglitazone", "acarbose", "miglitol",
            "troglitazone", "tolazamide", "examide", "citoglipton", "insulin", "glyburide-metformin",
            "glipizide-metformin", "glimepiride-pioglitazone", "metformin-rosiglitazone",
            "metformin-pioglitazone"]
COUNT_COLS = ["time_in_hospital", "num_lab_procedures", "num_procedures", "num_medications",
              "number_outpatient", "number_emergency", "number_inpatient", "number_diagnoses"]
ID_COLS = ["admission_type_id", "discharge_disposition_id", "admission_source_id"]

# Mapping codes that carry no information are treated as "missing-coded".
UNINFORMATIVE_ID_CODES = {
    "admission_type_id": {"5", "6", "8"},                    # Not Available, NULL, Not Mapped
    "discharge_disposition_id": {"18", "25", "26"},          # NULL, Not Mapped, Unknown/Invalid
    "admission_source_id": {"9", "15", "17", "20", "21"},    # Not Available, NULL, Not Mapped, Unknown
}
EXPIRED_CODES = {"11", "19", "20", "21"}
HOSPICE_CODES = {"13", "14"}

# Validation rules: column -> (min, max) inclusive, from the dataset documentation.
RANGE_RULES = {"time_in_hospital": (1, 14), "num_lab_procedures": (0, 200), "num_procedures": (0, 6),
               "num_medications": (1, 100), "number_outpatient": (0, 100), "number_emergency": (0, 100),
               "number_inpatient": (0, 100), "number_diagnoses": (1, 16)}
DOMAIN_RULES = {
    "gender": {"Female", "Male"},
    "readmitted": {"NO", ">30", "<30"},
    "max_glu_serum": {"None", "Norm", ">200", ">300"},
    "A1Cresult": {"None", "Norm", ">7", ">8"},
    "change": {"No", "Ch"},
    "diabetesMed": {"Yes", "No"},
    **{m: {"No", "Steady", "Up", "Down"} for m in MED_COLS},
}

transform_log: list[dict] = []
issue_log: list[dict] = []


def record(step: str, action: str, rationale: str, rows_affected: int | str) -> None:
    transform_log.append({"step": len(transform_log) + 1, "stage": step, "action": action,
                          "rationale": rationale, "rows_or_cells_affected": rows_affected})


def issue(issue_id: str, dimension: str, description: str, magnitude: str, resolution: str, residual: str) -> None:
    issue_log.append({"issue_id": issue_id, "quality_dimension": dimension, "description": description,
                      "magnitude": magnitude, "resolution": resolution, "residual_risk": residual})


# --------------------------------------------------------------------------- loading
def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_CSV, dtype=str, keep_default_na=False)
    log.info("Loaded raw data %s", df.shape)
    return df


def load_id_mappings() -> dict[str, dict[str, str]]:
    """IDS_mapping.csv holds three tables separated by blank lines."""
    text = IDS_MAPPING_CSV.read_text(encoding="utf-8")
    blocks = [b for b in text.replace("\r\n", "\n").split("\n,\n") if b.strip()]
    maps = {}
    for block in blocks:
        tbl = pd.read_csv(io.StringIO(block.strip()), dtype=str, keep_default_na=False)
        key = tbl.columns[0]
        maps[key] = {k.strip(): v.strip().rstrip(" .") for k, v in zip(tbl.iloc[:, 0], tbl.iloc[:, 1])}
    return maps


# --------------------------------------------------------------------------- quality metrics
def missing_mask(df: pd.DataFrame) -> pd.DataFrame:
    """Cells that are missing or missing-coded under the dataset's conventions.

    'Unknown' (our explicit fill value) still counts as missing information, so the
    before/after comparison does not reward relabelling.
    """
    m = df.isna() | df.astype(str).isin(["?", "", "nan", "Unknown/Invalid", "Unknown"])
    for col, codes in UNINFORMATIVE_ID_CODES.items():
        if col in df:
            m[col] = m[col] | df[col].astype(str).isin(codes)
    return m


def validity_mask(df: pd.DataFrame) -> pd.Series:
    """True where a row passes every range and domain rule that applies to its columns."""
    ok = pd.Series(True, index=df.index)
    for col, (lo, hi) in RANGE_RULES.items():
        v = pd.to_numeric(df[col], errors="coerce")
        ok &= v.between(lo, hi)
    for col, allowed in DOMAIN_RULES.items():
        if col in df:
            ok &= df[col].astype(str).isin(allowed)
    return ok


def consistency_checks(df: pd.DataFrame) -> dict[str, int]:
    meds_present = [c for c in MED_COLS if c in df]
    any_med = (df[meds_present] != "No").any(axis=1)
    any_adjust = df[meds_present].isin(["Up", "Down"]).any(axis=1)
    disp = df["discharge_disposition_id"].astype(str)
    return {
        "diabetesMed=No but a diabetes drug is recorded": int(((df["diabetesMed"] == "No") & any_med).sum()),
        "diabetesMed=Yes but no diabetes drug recorded": int(((df["diabetesMed"] == "Yes") & ~any_med).sum()),
        "change=No but a dose was adjusted (Up/Down)": int(((df["change"] == "No") & any_adjust).sum()),
        "expired at discharge but labelled readmitted": int((disp.isin(EXPIRED_CODES)
                                                             & (df["readmitted"] != "NO")).sum()),
    }


def quality_snapshot(df: pd.DataFrame, label: str) -> dict:
    miss = missing_mask(df)
    valid = validity_mask(df)
    cons = consistency_checks(df)
    return {
        "dataset_state": label,
        "rows": len(df),
        "columns": df.shape[1],
        "unique_patients": int(df["patient_nbr"].nunique()),
        "completeness_pct_cells": round(100 * (1 - miss.values.mean()), 2),
        "rows_fully_complete_pct": round(100 * (~miss.any(axis=1)).mean(), 2),
        "columns_over_40pct_missing": int((miss.mean() > 0.40).sum()),
        "validity_pct_rows": round(100 * valid.mean(), 3),
        "duplicate_encounter_ids": int(df["encounter_id"].duplicated().sum()),
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "constant_columns": int((df.nunique(dropna=False) <= 1).sum()),
        "consistency_violations_total": int(sum(cons.values())),
        **{f"consistency: {k}": v for k, v in cons.items()},
    }


# --------------------------------------------------------------------------- transformations
def icd9_group(code) -> str:
    """Group ICD-9-CM codes into the categories used by Strack et al. (2014)."""
    if code is None or (isinstance(code, float) and np.isnan(code)) or code in ("?", ""):
        return "Missing"
    c = str(code)
    if c[0] in "VE":
        return "Other"
    try:
        v = float(c)
    except ValueError:
        return "Other"
    if int(v) == 250:
        return "Diabetes"
    if 390 <= v <= 459 or int(v) == 785:
        return "Circulatory"
    if 460 <= v <= 519 or int(v) == 786:
        return "Respiratory"
    if 520 <= v <= 579 or int(v) == 787:
        return "Digestive"
    if 580 <= v <= 629 or int(v) == 788:
        return "Genitourinary"
    if 710 <= v <= 739:
        return "Musculoskeletal"
    if 800 <= v <= 999:
        return "Injury"
    if 140 <= v <= 239:
        return "Neoplasms"
    return "Other"


def clean(raw: pd.DataFrame, maps: dict[str, dict[str, str]]) -> pd.DataFrame:
    df = raw.copy()

    # 1. Standardise missing markers
    n_q = int((df == "?").sum().sum())
    df = df.replace("?", np.nan)
    record("Missing values", "Replaced '?' placeholder with a true missing value (NaN)",
           "'?' is the dataset's documented missing marker; NaN lets tools count and handle it", n_q)

    # 2. Invalid gender
    bad_gender = df["gender"] == "Unknown/Invalid"
    df = df.loc[~bad_gender].copy()
    record("Validity", "Removed rows with gender 'Unknown/Invalid'",
           "Invalid domain value; too few rows (n=3) to justify an extra category", int(bad_gender.sum()))
    issue("DQ-01", "Validity", "Gender recorded as 'Unknown/Invalid'", f"{int(bad_gender.sum())} rows",
          "Rows removed", "Negligible")

    # 3. Drop uninformative columns
    weight_missing = raw["weight"].eq("?").mean()
    df = df.drop(columns=["weight"])
    record("Completeness", "Dropped 'weight'",
           f"{weight_missing:.1%} missing; imputation would fabricate most values", "1 column")
    issue("DQ-02", "Completeness", "Weight almost entirely missing", f"{weight_missing:.1%} of rows",
          "Column dropped", "Body weight/BMI cannot be analysed as a risk factor")
    const_cols = [c for c in df.columns if df[c].nunique(dropna=False) <= 1]
    df = df.drop(columns=const_cols)
    record("Relevance", f"Dropped constant columns {const_cols}", "Zero variance: carry no information",
           f"{len(const_cols)} columns")
    issue("DQ-03", "Relevance", f"Constant medication columns {const_cols}", f"{len(const_cols)} columns",
          "Columns dropped", "None")

    # 4. High-missing categoricals -> explicit 'Unknown' category
    for col in ["payer_code", "medical_specialty", "race"]:
        share = df[col].isna().mean()
        n = int(df[col].isna().sum())
        df[col] = df[col].fillna("Unknown")
        record("Missing values", f"Filled missing '{col}' with explicit 'Unknown' category",
               "Missingness may itself be informative (e.g., documentation practice); keeps rows and avoids "
               "guessing values", n)
        issue(f"DQ-0{4 + ['payer_code', 'medical_specialty', 'race'].index(col)}", "Completeness",
              f"Missing {col}", f"{share:.1%} of rows", "Explicit 'Unknown' category",
              "Analyses by this field are limited to recorded values; bias if missingness is non-random")

    # 5. Collapse medical specialty to top categories
    top_spec = df.loc[df["medical_specialty"] != "Unknown", "medical_specialty"].value_counts().head(10).index
    n_other = int((~df["medical_specialty"].isin(list(top_spec) + ["Unknown"])).sum())
    df["medical_specialty_grp"] = np.where(df["medical_specialty"].isin(list(top_spec) + ["Unknown"]),
                                           df["medical_specialty"], "Other")
    record("Normalisation", "Grouped medical_specialty into 10 most frequent + 'Other' + 'Unknown'",
           "73 sparse levels; rare levels give unstable estimates", n_other)

    # 6. Map ID codes to labels; uninformative codes -> 'Unknown'
    key_for = {"admission_type_id": "admission_type_id", "discharge_disposition_id": "discharge_disposition_id",
               "admission_source_id": "admission_source_id"}
    for col, key in key_for.items():
        mapping = maps[key]
        labels = df[col].map(mapping)
        unmapped = int(labels.isna().sum())
        uninformative = df[col].isin(UNINFORMATIVE_ID_CODES[col])
        labels = labels.where(~uninformative, "Unknown").fillna("Unknown")
        df[col.replace("_id", "")] = labels
        record("Normalisation", f"Mapped {col} codes to descriptive labels via IDS_mapping.csv; codes for "
               "NULL/Not Available/Not Mapped/Unknown set to 'Unknown'",
               "Human-readable categories; merges several codes that all mean 'unknown'",
               int(uninformative.sum()) + unmapped)
        issue(f"DQ-{7 + list(key_for).index(col):02d}", "Completeness", f"Uninformative {col} codes",
              f"{uninformative.mean():.1%} of rows", "Recoded as 'Unknown'", "Some loss of detail")

    # Broad grouping of discharge disposition for analysis
    disp = df["discharge_disposition_id"]
    df["discharge_group"] = np.select(
        [disp == "1", disp == "6", disp.isin(["3", "4", "24", "15"]), disp.isin(["22", "23", "5", "2", "27",
                                                                                  "28", "29", "30", "9", "10"]),
         disp.isin(EXPIRED_CODES), disp.isin(HOSPICE_CODES), disp == "7"],
        ["Home", "Home with health service", "Skilled nursing / ICF", "Other inpatient / rehab facility",
         "Expired", "Hospice", "Left against medical advice"], default="Other / Unknown")
    adm = df["admission_type"]
    df["admission_type_grp"] = np.where(adm.isin(["Emergency", "Urgent", "Elective"]), adm,
                                        np.where(adm == "Unknown", "Unknown", "Other"))
    src = df["admission_source_id"]
    df["admission_source_grp"] = np.select(
        [src == "7", src.isin(["1", "2", "3"]), src.isin(["4", "5", "6", "10", "18", "22", "25", "26"])],
        ["Emergency room", "Referral", "Transfer"], default="Other / Unknown")
    record("Feature engineering", "Created discharge_group, admission_type_grp, admission_source_grp",
           "Clinically meaningful groupings with adequate counts per level", len(df))

    # 7. Numeric conversion and validation
    for col in COUNT_COLS:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(int)
    record("Data types", f"Converted {len(COUNT_COLS)} count columns from text to integer",
           "Enables numeric validation and analysis", f"{len(COUNT_COLS)} columns")

    # 8. Age band -> ordered category and numeric midpoint
    df["age_band"] = df["age"].str.strip("[)").str.replace("-", "–")
    df["age_mid"] = df["age"].str.extract(r"\[(\d+)-")[0].astype(int) + 5
    df["age_group"] = pd.cut(df["age_mid"], bins=[0, 40, 60, 80, 100],
                             labels=["<40", "40–59", "60–79", "80+"]).astype(str)
    record("Normalisation", "Derived age_band label, numeric age_mid (band midpoint) and 4-level age_group",
           "Ordered numeric use in models; broader groups for stable subgroup estimates", len(df))

    # 9. Diagnoses -> ICD-9 chapter groups
    for i in (1, 2, 3):
        df[f"diag_{i}_group"] = df[f"diag_{i}"].map(icd9_group)
    record("Feature engineering", "Grouped diag_1–diag_3 ICD-9 codes into 9 clinical categories "
           "(Strack et al., 2014 scheme)", "700+ raw codes are too sparse for analysis", len(df) * 3)
    issue("DQ-10", "Completeness", "Missing secondary/tertiary diagnoses",
          f"diag_1 {raw['diag_1'].eq('?').sum()}, diag_2 {raw['diag_2'].eq('?').sum()}, "
          f"diag_3 {raw['diag_3'].eq('?').sum()} rows", "Kept as 'Missing' group",
          "Fewer recorded comorbidities may reflect coding depth rather than health")

    # 10. Lab result labels
    df["A1C_result"] = df["A1Cresult"].replace({"None": "Not measured"})
    df["glucose_serum"] = df["max_glu_serum"].replace({"None": "Not measured"})
    df["A1C_measured"] = (df["A1Cresult"] != "None").astype(int)
    record("Normalisation", "Relabelled lab value 'None' as 'Not measured'; added A1C_measured flag",
           "'None' means the test was not done, not a missing value", len(df))

    # 11. Engineered utilisation and medication features
    meds = [c for c in MED_COLS if c in df]
    df["prior_visits_total"] = df[["number_outpatient", "number_emergency", "number_inpatient"]].sum(axis=1)
    df["n_diabetes_meds"] = (df[meds] != "No").sum(axis=1)
    df["n_med_dose_changes"] = df[meds].isin(["Up", "Down"]).sum(axis=1)
    df["any_prior_inpatient"] = (df["number_inpatient"] > 0).astype(int)
    record("Feature engineering", "Created prior_visits_total, n_diabetes_meds, n_med_dose_changes, "
           "any_prior_inpatient", "Summarise utilisation history and treatment intensity", len(df))

    # 12. Outcome and cohort flags
    df["readmit_30"] = (df["readmitted"] == "<30").astype(int)
    df["readmit_any"] = (df["readmitted"] != "NO").astype(int)
    df["expired_or_hospice"] = df["discharge_disposition_id"].isin(EXPIRED_CODES | HOSPICE_CODES).astype(int)
    df = df.sort_values("encounter_id", key=lambda s: s.astype(np.int64))
    df["encounter_seq"] = df.groupby("patient_nbr").cumcount() + 1
    df["is_index_encounter"] = (df["encounter_seq"] == 1).astype(int)
    record("Cohort definition", "Added readmit_30 (<30 days) target, expired_or_hospice flag and "
           "encounter sequence per patient (ordered by encounter_id)",
           "Readmission is impossible after death and not a quality failure after hospice discharge; "
           "repeated encounters of one patient are not independent", len(df))
    issue("DQ-11", "Uniqueness", "Repeated encounters for the same patient",
          f"{len(df) - df['patient_nbr'].nunique():,} non-index encounters",
          "Analysis cohort keeps first encounter per patient", "Later-encounter risk not modelled; "
          "encounter_id ordering assumed chronological (not documented)")
    issue("DQ-12", "Timeliness", "Data cover 1999–2008 and contain no admission dates",
          "Entire dataset", "Documented; no time-trend analysis attempted",
          "Practice patterns and coding (ICD-9 to ICD-10) have changed since; findings may not transfer")
    issue("DQ-13", "Accuracy", "Values cannot be checked against source medical records",
          "Entire dataset", "Range, domain and consistency checks only",
          "Passing automated checks does not prove clinical accuracy")
    issue("DQ-14", "Validity", "Readmission label scope (same hospital system vs any hospital) not documented",
          "Target variable", "Documented as a limitation", "Readmissions may be under-counted")

    df["encounter_id"] = df["encounter_id"].astype(np.int64)
    df["patient_nbr"] = df["patient_nbr"].astype(np.int64)
    return df


def build_data_dictionary(clean_df: pd.DataFrame) -> pd.DataFrame:
    desc = {
        "encounter_id": "Unique encounter identifier (de-identified)",
        "patient_nbr": "Unique patient identifier (de-identified)",
        "race": "Patient race as recorded; 'Unknown' if missing",
        "gender": "Patient gender (Female/Male)",
        "age": "Age band in 10-year intervals (raw label)",
        "age_band": "Age band label, e.g. 70–80",
        "age_mid": "Midpoint of age band in years (derived)",
        "age_group": "Broad age group: <40, 40–59, 60–79, 80+ (derived)",
        "admission_type_id": "Raw admission type code", "admission_type": "Admission type label",
        "admission_type_grp": "Emergency / Urgent / Elective / Other / Unknown",
        "discharge_disposition_id": "Raw discharge disposition code",
        "discharge_disposition": "Discharge disposition label", "discharge_group": "Grouped discharge destination",
        "admission_source_id": "Raw admission source code", "admission_source": "Admission source label",
        "admission_source_grp": "Emergency room / Referral / Transfer / Other / Unknown",
        "time_in_hospital": "Length of stay (days, 1–14)",
        "payer_code": "Payer code (e.g. MC = Medicare); 'Unknown' if missing",
        "medical_specialty": "Specialty of admitting physician; 'Unknown' if missing",
        "medical_specialty_grp": "Top-10 specialties, 'Other', 'Unknown'",
        "num_lab_procedures": "Number of lab tests during encounter",
        "num_procedures": "Number of non-lab procedures during encounter",
        "num_medications": "Number of distinct generic medications administered",
        "number_outpatient": "Outpatient visits in year before encounter",
        "number_emergency": "Emergency visits in year before encounter",
        "number_inpatient": "Inpatient admissions in year before encounter",
        "diag_1": "Primary diagnosis (ICD-9-CM, first 3 digits)", "diag_2": "Secondary diagnosis (ICD-9-CM)",
        "diag_3": "Additional secondary diagnosis (ICD-9-CM)",
        "diag_1_group": "Primary diagnosis category (derived)", "diag_2_group": "Secondary diagnosis category",
        "diag_3_group": "Additional diagnosis category",
        "number_diagnoses": "Number of diagnoses entered", "max_glu_serum": "Max glucose serum test (raw)",
        "glucose_serum": "Glucose serum result; 'Not measured' if not done", "A1Cresult": "HbA1c result (raw)",
        "A1C_result": "HbA1c result: Not measured / Norm / >7 / >8", "A1C_measured": "1 if HbA1c measured",
        "change": "Any change in diabetic medication (Ch/No)", "diabetesMed": "Any diabetic medication prescribed",
        "readmitted": "Raw outcome: <30, >30, NO", "readmit_30": "Target: 1 if readmitted within 30 days",
        "readmit_any": "1 if readmitted at any time", "prior_visits_total": "Outpatient + emergency + inpatient",
        "n_diabetes_meds": "Number of diabetes drugs recorded (not 'No')",
        "n_med_dose_changes": "Number of diabetes drugs with dose Up/Down",
        "any_prior_inpatient": "1 if any inpatient admission in prior year",
        "expired_or_hospice": "1 if discharged as expired or to hospice",
        "encounter_seq": "Order of encounter within patient (by encounter_id)",
        "is_index_encounter": "1 for the first encounter of each patient",
    }
    rows = []
    for col in clean_df.columns:
        s = clean_df[col]
        role = "Identifier" if col in ("encounter_id", "patient_nbr") else (
            "Target" if col == "readmit_30" else ("Outcome (raw)" if col in ("readmitted", "readmit_any") else "Feature"))
        rows.append({
            "variable": col,
            "description": desc.get(col, "Diabetes medication status: No / Steady / Up / Down" if col in MED_COLS else ""),
            "role": role, "dtype": str(s.dtype), "n_unique": int(s.nunique()),
            "missing_pct": round(100 * s.isna().mean(), 2),
            "example_values": ", ".join(map(str, s.dropna().unique()[:5])),
        })
    return pd.DataFrame(rows)


def main() -> None:
    raw = load_raw()
    maps = load_id_mappings()

    before = quality_snapshot(raw, "Raw (as downloaded)")
    raw_missing = missing_mask(raw).mean().mul(100).round(2).rename("missing_pct_raw")
    raw_missing.to_frame().reset_index(names="column").to_csv(TABLE_DIR / "data_quality_missing_by_column_raw.csv",
                                                               index=False)
    # Missing-pattern sample for the heatmap figure (reproducible sample)
    missing_mask(raw).sample(2000, random_state=1).to_csv(TABLE_DIR / "missing_pattern_sample.csv", index=False)

    df = clean(raw, maps)
    cons_after = consistency_checks(df)
    after_cols = [c for c in raw.columns if c in df.columns]
    after = quality_snapshot(df[after_cols], "Cleaned (all encounters)")

    index = df[(df["is_index_encounter"] == 1) & (df["expired_or_hospice"] == 0)].copy()
    record("Cohort definition", "Analysis cohort = index encounter per patient, excluding expired/hospice",
           "Independent observations with an observable readmission outcome", len(index))
    cohort_q = quality_snapshot(index[after_cols], "Analysis cohort (index, alive, non-hospice)")

    # Unresolved consistency findings are logged, not silently "fixed".
    for i, (k, v) in enumerate(cons_after.items()):
        if v:
            issue(f"DQ-C{i + 1}", "Consistency", k, f"{v} rows",
                  "Retained and documented (cannot determine which field is wrong)", "Minor")

    qc = pd.DataFrame([before, after, cohort_q]).set_index("dataset_state").T.reset_index(names="metric")
    qc.to_csv(TABLE_DIR / "data_quality_before_after.csv", index=False)

    # Validation rule results on the cleaned data
    vrows = []
    for col, (lo, hi) in RANGE_RULES.items():
        fails = int((~df[col].between(lo, hi)).sum())
        vrows.append({"rule": f"{col} within [{lo}, {hi}]", "type": "Range", "failures": fails,
                      "threshold": "0 failures", "status": "PASS" if fails == 0 else "FAIL"})
    for col, allowed in DOMAIN_RULES.items():
        if col in df:
            fails = int((~df[col].isin(allowed)).sum())
            vrows.append({"rule": f"{col} in {sorted(allowed)}", "type": "Domain", "failures": fails,
                          "threshold": "0 failures", "status": "PASS" if fails == 0 else "FAIL"})
    for rule, fails in [("encounter_id unique", int(df["encounter_id"].duplicated().sum())),
                        ("patient_nbr not null", int(df["patient_nbr"].isna().sum())),
                        ("readmit_30 consistent with readmitted", int(((df["readmitted"] == "<30")
                                                                       != (df["readmit_30"] == 1)).sum())),
                        ("analysis cohort: one row per patient", int(index["patient_nbr"].duplicated().sum())),
                        ("analysis cohort: no expired/hospice", int(index["expired_or_hospice"].sum()))]:
        vrows.append({"rule": rule, "type": "Uniqueness/Logic", "failures": fails, "threshold": "0 failures",
                      "status": "PASS" if fails == 0 else "FAIL"})
    for k, v in cons_after.items():
        vrows.append({"rule": k, "type": "Consistency", "failures": v, "threshold": "<0.5% of rows (warn)",
                      "status": "PASS" if v / len(df) < 0.005 else "WARN"})
    pd.DataFrame(vrows).to_csv(TABLE_DIR / "data_quality_validation_rules.csv", index=False)
    pd.DataFrame(issue_log).to_csv(TABLE_DIR / "data_quality_issue_log.csv", index=False)
    pd.DataFrame(transform_log).to_csv(DOCS_DIR / "transformation_log.csv", index=False)

    df.to_csv(CLEAN_CSV, index=False)
    index.to_csv(INDEX_COHORT_CSV, index=False)
    build_data_dictionary(df).to_csv(DOCS_DIR / "data_dictionary.csv", index=False)

    save_json({"raw_rows": len(raw), "clean_rows": len(df), "clean_patients": int(df["patient_nbr"].nunique()),
               "expired_or_hospice_all": int(df["expired_or_hospice"].sum()),
               "index_encounters": int(df["is_index_encounter"].sum()),
               "index_expired_or_hospice": int(df.loc[df["is_index_encounter"] == 1, "expired_or_hospice"].sum()),
               "cohort_rows": len(index), "cohort_readmit30_n": int(index["readmit_30"].sum()),
               "cohort_readmit30_rate": float(index["readmit_30"].mean()),
               "all_readmit30_rate": float(df["readmit_30"].mean()),
               "consistency_after": cons_after, "quality_before": before, "quality_after": after,
               "quality_cohort": cohort_q}, TABLE_DIR / "cleaning_summary.json")
    log.info("Clean encounters %s | cohort %s | 30-day rate %.4f", df.shape, index.shape, index["readmit_30"].mean())


if __name__ == "__main__":
    main()
