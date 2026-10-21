"""Step 6 - Executive KPI figure, interactive HTML dashboard and Power BI build pack.

Outputs
  outputs/figures/fig00_executive_kpis.png
  dashboard/healthcare_readmission_dashboard.html   (self-contained; open in any modern browser)
  dashboard/powerbi/*.csv, DAX_measures.dax, POWERBI_BUILD_GUIDE.md
  outputs/figures/dashboard_screenshot_*.png         (if Microsoft Edge is available for headless capture)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DASHBOARD_DIR, FIG_DIR, INDEX_COHORT_CSV, MODEL_DIR, TABLE_DIR, get_logger,  # noqa: E402
                    load_json)
from viz_style import BASE, INK, INK_2, MUTED, SURFACE, finish, rate_ci  # noqa: E402

log = get_logger("visualisation")
MIN_N = 30
AGE_BANDS = ["0–10", "10–20", "20–30", "30–40", "40–50", "50–60", "60–70", "70–80", "80–90", "90–100"]


def executive_kpis(cohort: pd.DataFrame, model: dict) -> None:
    n, k = len(cohort), int(cohort["readmit_30"].sum())
    rate, lo, hi = rate_ci(k, n)
    tiles = [
        ("Patients analysed", f"{n:,}", "index encounters, 1999–2008"),
        ("30-day readmission rate", f"{rate:.1%}", f"95% CI {lo:.1%}–{hi:.1%}; {k:,} patients"),
        ("Mean length of stay", f"{cohort['time_in_hospital'].mean():.2f} days",
         f"{cohort['time_in_hospital'].sum():,} bed-days in total"),
        ("HbA1c tested during stay", f"{cohort['A1C_measured'].mean():.1%}", "of patients (all have a diabetes diagnosis)"),
        ("Prior-year inpatient stay", f"{cohort['any_prior_inpatient'].mean():.1%}",
         "of patients; their 30-day rate is ~1.9× higher"),
        ("Model discrimination", f"AUC {model['test_roc_auc']:.3f}",
         f"top 20% flagged capture {model['test_metrics_top20']['recall_sensitivity']:.0%} of readmissions"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 4.6))
    for ax, (label, value, sub) in zip(axes.ravel(), tiles):
        ax.set_axis_off()
        ax.add_patch(plt.Rectangle((0.02, 0.04), 0.96, 0.92, transform=ax.transAxes, facecolor="#ffffff",
                                   edgecolor="#e1e0d9", linewidth=1))
        ax.text(0.08, 0.76, label, fontsize=10.5, color=INK_2, transform=ax.transAxes)
        ax.text(0.08, 0.42, value, fontsize=24, color=INK, fontweight="bold", transform=ax.transAxes)
        ax.text(0.08, 0.17, sub, fontsize=8.8, color=MUTED, transform=ax.transAxes)
    fig.suptitle("Executive KPI overview — diabetic inpatient readmissions", x=0.01, ha="left", fontsize=13,
                 fontweight="bold", y=1.02)
    fig.subplots_adjust(left=0.0, right=1.0, wspace=0.05, hspace=0.12)
    finish(fig, FIG_DIR / "fig00_executive_kpis.png", source="Source: UCI Diabetes 130-US Hospitals (1999–2008); "
           "analysis cohort; model metrics on held-out test set. Educational analysis only.")


def encode(series: pd.Series, levels: list[str]) -> list[int]:
    lookup = {lvl: i for i, lvl in enumerate(levels)}
    return [lookup[v] for v in series]


def build_dashboard(cohort: pd.DataFrame, model: dict) -> Path:
    c = cohort.copy()
    c["prior_ip_lbl"] = c["number_inpatient"].clip(upper=3).map({0: "None", 1: "1", 2: "2", 3: "3 or more"})
    levels = {
        "age_group": ["<40", "40–59", "60–79", "80+"],
        "age_band": AGE_BANDS,
        "gender": sorted(c["gender"].unique()),
        "race": c["race"].value_counts().index.tolist(),
        "diag": c["diag_1_group"].value_counts().index.tolist(),
        "discharge": c["discharge_group"].value_counts().index.tolist(),
        "adm_type": c["admission_type_grp"].value_counts().index.tolist(),
        "a1c": ["Not measured", "Norm", ">7", ">8"],
        "prior_ip": ["None", "1", "2", "3 or more"],
    }
    deciles = pd.read_csv(TABLE_DIR / "model_risk_deciles.csv")
    data = {
        "age_group": encode(c["age_group"], levels["age_group"]),
        "age_band": encode(c["age_band"], levels["age_band"]),
        "gender": encode(c["gender"], levels["gender"]),
        "race": encode(c["race"], levels["race"]),
        "diag": encode(c["diag_1_group"], levels["diag"]),
        "discharge": encode(c["discharge_group"], levels["discharge"]),
        "adm_type": encode(c["admission_type_grp"], levels["adm_type"]),
        "a1c": encode(c["A1C_result"], levels["a1c"]),
        "prior_ip": encode(c["prior_ip_lbl"], levels["prior_ip"]),
        "a1c_measured": c["A1C_measured"].astype(int).tolist(),
        "los": c["time_in_hospital"].astype(int).tolist(),
        "meds": c["num_medications"].astype(int).tolist(),
        "y": c["readmit_30"].astype(int).tolist(),
        "levels": levels,
        "model_deciles": [{"decile": int(r.decile), "n": int(r.patients), "k": int(r.readmissions)}
                          for r in deciles.itertuples()],
        "model_prevalence": float(model["split"]["test_rate"]),
    }
    template = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(encoding="utf-8")
    html = (template.replace("__DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
            .replace("__MIN_N__", str(MIN_N)).replace("__N_PATIENTS__", f"{len(c):,}")
            .replace("__MODEL_NAME__", model["selected_model"]).replace("__AUC__", f"{model['test_roc_auc']:.3f}")
            .replace("__CAPTURE__", f"{model['top2_decile_capture']:.0%}")
            .replace("__GENERATED__", date.today().isoformat()))
    out = DASHBOARD_DIR / "healthcare_readmission_dashboard.html"
    out.write_text(html, encoding="utf-8")
    log.info("Dashboard written: %s (%.1f MB)", out, out.stat().st_size / 1e6)
    return out


def powerbi_pack(cohort: pd.DataFrame) -> None:
    pb = DASHBOARD_DIR / "powerbi"
    pb.mkdir(exist_ok=True)
    dims = {"dim_diagnosis": "diag_1_group", "dim_discharge": "discharge_group",
            "dim_admission_type": "admission_type_grp", "dim_age_group": "age_group", "dim_race": "race",
            "dim_a1c": "A1C_result"}
    fact = cohort[["encounter_id", "gender", "age_band", "age_mid", "time_in_hospital", "num_lab_procedures",
                   "num_procedures", "num_medications", "number_inpatient", "number_emergency",
                   "number_outpatient", "number_diagnoses", "A1C_measured", "any_prior_inpatient", "readmit_30",
                   "readmitted"]].copy()
    for dim, col in dims.items():
        levels = sorted(cohort[col].unique(), key=str)
        key = f"{dim.replace('dim_', '')}_key"
        pd.DataFrame({key: range(1, len(levels) + 1), col: levels}).to_csv(pb / f"{dim}.csv", index=False)
        fact[key] = cohort[col].map({lvl: i + 1 for i, lvl in enumerate(levels)})
    fact.to_csv(pb / "fact_encounters.csv", index=False)

    dax = """// DAX measures for the Diabetes Readmission dashboard (table: fact_encounters)
Patients = COUNTROWS ( fact_encounters )
Readmissions 30d = SUM ( fact_encounters[readmit_30] )
Readmission Rate 30d = DIVIDE ( [Readmissions 30d], [Patients] )

// Wilson 95% confidence interval for the readmission rate
Readmission Rate CI Low =
VAR n = [Patients]
VAR p = [Readmission Rate 30d]
VAR z = 1.96
RETURN IF ( n > 0, DIVIDE ( p + z ^ 2 / ( 2 * n ) - z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ), 1 + z ^ 2 / n ) )

Readmission Rate CI High =
VAR n = [Patients]
VAR p = [Readmission Rate 30d]
VAR z = 1.96
RETURN IF ( n > 0, DIVIDE ( p + z ^ 2 / ( 2 * n ) + z * SQRT ( p * ( 1 - p ) / n + z ^ 2 / ( 4 * n ^ 2 ) ), 1 + z ^ 2 / n ) )

// Small-sample suppression: hide rates for groups with fewer than 30 patients
Readmission Rate (reportable) = IF ( [Patients] < 30, BLANK (), [Readmission Rate 30d] )
Small Sample Flag = IF ( [Patients] < 30, "n < 30 - not reported", BLANK () )

Overall Readmission Rate = CALCULATE ( [Readmission Rate 30d], ALLSELECTED ( fact_encounters ) )
Rate Difference vs Overall (pp) = ( [Readmission Rate (reportable)] - [Overall Readmission Rate] ) * 100

Bed Days = SUM ( fact_encounters[time_in_hospital] )
Average LOS = AVERAGE ( fact_encounters[time_in_hospital] )
HbA1c Testing Rate = DIVIDE ( SUM ( fact_encounters[A1C_measured] ), [Patients] )
Prior Inpatient Share = DIVIDE ( SUM ( fact_encounters[any_prior_inpatient] ), [Patients] )
Average Medications = AVERAGE ( fact_encounters[num_medications] )
Average Lab Procedures = AVERAGE ( fact_encounters[num_lab_procedures] )
"""
    (pb / "DAX_measures.dax").write_text(dax, encoding="utf-8")

    guide = f"""# Power BI build guide — Diabetes Readmission Dashboard

A `.pbix` file is **not** included: Power BI Desktop is a Windows GUI application that could not be
automated in this project environment. Everything needed to rebuild the dashboard in about 30–45
minutes is provided instead.

## 1. Files

| File | Purpose |
|---|---|
| `fact_encounters.csv` | One row per patient (index encounter), {len(fact):,} rows, numeric measures + foreign keys |
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

After building, check that with no filters applied: Patients = {len(fact):,}; Readmission Rate 30d =
{fact['readmit_30'].mean():.2%}; Average LOS = {fact['time_in_hospital'].mean():.2f}. These match the Python
analysis and the HTML dashboard.
"""
    (pb / "POWERBI_BUILD_GUIDE.md").write_text(guide, encoding="utf-8")
    log.info("Power BI pack written to %s", pb)


def screenshot(html: Path) -> list[Path]:
    """Capture the dashboard with headless Microsoft Edge, if present."""
    candidates = [shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
    edge = next((c for c in candidates if c and Path(c).exists()), None)
    if not edge:
        log.warning("Microsoft Edge not found - dashboard screenshots skipped")
        return []
    shots = []
    with tempfile.TemporaryDirectory() as tmp:
        # A dedicated profile forces a separate headless instance (otherwise a running Edge may absorb the call),
        # and the HTML is copied to a plain temp path that the browser process can always read.
        tmp_html = Path(tmp) / "dashboard.html"
        shutil.copy(html, tmp_html)
        for name, size in [("desktop", "1360,2250"), ("mobile", "390,1300")]:
            tmp_png = Path(tmp) / f"{name}.png"
            cmd = [edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-color-profile=srgb",
                   "--blink-settings=preferredColorScheme=1", f"--user-data-dir={Path(tmp) / 'profile'}",
                   "--no-first-run", "--virtual-time-budget=4000", f"--window-size={size}",
                   f"--screenshot={tmp_png}", tmp_html.as_uri()]
            try:
                subprocess.run(cmd, timeout=180, capture_output=True)
            except (subprocess.SubprocessError, OSError) as exc:
                log.warning("Screenshot failed: %s", exc)
                continue
            if tmp_png.exists():
                out = FIG_DIR / f"dashboard_screenshot_{name}.png"
                shutil.copy(tmp_png, out)
                shots.append(out)
                log.info("Screenshot saved %s", out)
            else:
                log.warning("Edge produced no screenshot for %s", name)
    return shots


def main() -> None:
    cohort = pd.read_csv(INDEX_COHORT_CSV, low_memory=False)
    model = load_json(MODEL_DIR / "model_metrics.json")
    executive_kpis(cohort, model)
    html = build_dashboard(cohort, model)
    powerbi_pack(cohort)
    screenshot(html)


if __name__ == "__main__":
    main()
