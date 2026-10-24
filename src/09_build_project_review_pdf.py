"""Step 9 - Project review PDF: development process, tech stack, challenges, enhancements,
performance, scalability and implementation efficiency.

Timings are those measured in the full pipeline run of 24 October 2026 (Windows 11 laptop).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FIG_DIR, ROOT  # noqa: E402
from report_data import AUTHOR, REPO_URL, mdl, ov  # noqa: E402
from viz_style import BASE, HIGHLIGHT, INK, INK_2, MUTED, finish  # noqa: E402

OUT = ROOT / "report" / "Project_Review_Process_Challenges_and_Roadmap.pdf"
STEP_SECONDS = {"01 Data acquisition": 28, "02 Quality & cleaning": 26, "03 Exploratory analysis": 41,
                "04 Statistics": 21, "05 Predictive modelling": 405, "06 Dashboard": 12, "07 Final report": 4,
                "08 Weekly reports": 10}
MODEL_SECONDS = {"Logistic regression tuning": 26, "Random forest tuning": 221, "Gradient boosting tuning": 57,
                 "Evaluation\n(bootstrap CIs, importance)": 87}

# ------------------------------------------------------------------ fonts & styles
FONT_DIR = Path("C:/Windows/Fonts")
try:
    pdfmetrics.registerFont(TTFont("Body", str(FONT_DIR / "calibri.ttf")))
    pdfmetrics.registerFont(TTFont("Body-Bold", str(FONT_DIR / "calibrib.ttf")))
    pdfmetrics.registerFont(TTFont("Body-Italic", str(FONT_DIR / "calibrii.ttf")))
    pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "consola.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-Bold")
    BODY, BOLD, ITALIC, MONO = "Body", "Body-Bold", "Body-Italic", "Mono"
except Exception:  # non-Windows fallback
    BODY, BOLD, ITALIC, MONO = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"

ACCENT = colors.HexColor("#1c5cab")
GREY = colors.HexColor("#595959")
BAND = colors.HexColor("#f2f6fb")
LINE = colors.HexColor("#c9ced6")

S = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=26, leading=31, textColor=ACCENT, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName=BODY, fontSize=13, leading=17, alignment=TA_CENTER, textColor=INK_2),
    "meta": ParagraphStyle("meta", fontName=BODY, fontSize=10.5, leading=15, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=17, leading=21, textColor=ACCENT, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=5),
    "body": ParagraphStyle("body", fontName=BODY, fontSize=10.5, leading=14.5, alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": ParagraphStyle("bullet", fontName=BODY, fontSize=10.5, leading=14, leftIndent=14, bulletIndent=3, spaceAfter=3),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.6, leading=10.6),
    "cellb": ParagraphStyle("cellb", fontName=BOLD, fontSize=8.6, leading=10.6),
    "head": ParagraphStyle("head", fontName=BOLD, fontSize=8.8, leading=10.8, textColor=colors.white),
    "caption": ParagraphStyle("caption", fontName=BODY, fontSize=9, leading=11.5, textColor=GREY, spaceAfter=10),
    "note": ParagraphStyle("note", fontName=ITALIC, fontSize=9.5, leading=12.5, textColor=GREY, spaceAfter=8),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=8.5, leading=11, backColor=colors.HexColor("#f4f4f2"),
                           borderPadding=5, spaceBefore=4, spaceAfter=8),
    "toc1": ParagraphStyle("toc1", fontName=BODY, fontSize=11, leading=16),
    "toc2": ParagraphStyle("toc2", fontName=BODY, fontSize=10, leading=14, leftIndent=14, textColor=INK_2),
}


class Doc(SimpleDocTemplate):
    """Registers headings with the table of contents (two-pass build)."""

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            level = 0 if flowable.style.name == "h1" else 1
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (level, flowable.getPlainText(), self.page, key))


def page_decor(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont(BODY, 8)
        canvas.setFillColor(GREY)
        canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.3 * cm, "Project Review · Diabetic readmission analytics")
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Page {doc.page}")
        canvas.setStrokeColor(LINE)
        canvas.line(2 * cm, A4[1] - 1.45 * cm, A4[0] - 2 * cm, A4[1] - 1.45 * cm)
    canvas.restoreState()


story: list = []
H1 = lambda t: story.append(Paragraph(t, S["h1"]))  # noqa: E731
H2 = lambda t: story.append(Paragraph(t, S["h2"]))  # noqa: E731
P = lambda t, st="body": story.append(Paragraph(t, S[st]))  # noqa: E731


def bullets(items):
    for it in items:
        story.append(Paragraph(it, S["bullet"], bulletText="•"))


def table(rows, widths, head=True, bold_first=True):
    data = []
    for r_i, row in enumerate(rows):
        cells = []
        for c_i, v in enumerate(row):
            if head and r_i == 0:
                cells.append(Paragraph(str(v), S["head"]))
            else:
                cells.append(Paragraph(str(v), S["cellb"] if bold_first and c_i == 0 else S["cell"]))
        data.append(cells)
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0, hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if head:
        style.append(("BACKGROUND", (0, 0), (-1, 0), ACCENT))
    for i in range(1 if head else 0, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 8))


def figure(path: Path, caption: str, width_cm: float = 16.5):
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width_cm * cm, width_cm * cm * ratio
    story.append(KeepTogether([img, Spacer(1, 3), Paragraph(caption, S["caption"])]))


# ------------------------------------------------------------------ charts
def timing_chart() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.9), gridspec_kw={"width_ratios": [1.05, 1], "wspace": 0.55})
    names, secs = list(STEP_SECONDS), list(STEP_SECONDS.values())
    total = sum(secs)
    ax = axes[0]
    ax.barh(names, secs, color=[HIGHLIGHT if s == max(secs) else BASE for s in secs], height=0.6)
    for y, s in enumerate(secs):
        ax.text(s + 5, y, f"{s} s  ({s / total:.0%})", va="center", fontsize=8.5, color=INK_2)
    ax.invert_yaxis()
    ax.set_xlim(0, max(secs) * 1.3)
    ax.set_xlabel("Seconds")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Pipeline run time by step (total {total / 60:.1f} min)")
    ax = axes[1]
    names, secs = list(MODEL_SECONDS), list(MODEL_SECONDS.values())
    ax.barh(names, secs, color=[HIGHLIGHT if s == max(secs) else BASE for s in secs], height=0.6)
    for y, s in enumerate(secs):
        ax.text(s + 4, y, f"{s} s", va="center", fontsize=8.5, color=INK_2)
    ax.invert_yaxis()
    ax.set_xlim(0, max(secs) * 1.3)
    ax.set_xlabel("Seconds")
    ax.grid(axis="y", visible=False)
    ax.set_title("Inside step 05: where modelling time goes")
    out = FIG_DIR / "review_pipeline_timing.png"
    finish(fig, out, source="Measured in the full pipeline run of 24 Oct 2026 on a Windows 11 laptop (all CPU cores used for tuning).")
    return out


def architecture_chart() -> Path:
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.98, bottom=0.02)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    cols = [
        ("Sources", ["EHR / HIS (FHIR API)", "Lab system", "Claims / payer", "Public data (UCI, CMS)"], 0.01),
        ("Ingest & store", ["Scheduled ingest (Airflow / Prefect)", "Data lake: partitioned Parquet", "Warehouse:\nDuckDB → Postgres / Snowflake"], 0.215),
        ("Quality & transform", ["Validation suite (rules as code)", "dbt / SQL transforms", "Versioned datasets (DVC)"], 0.42),
        ("Analytics & ML", ["Feature store", "Training in Docker + MLflow", "Model registry + drift monitor"], 0.625),
        ("Serve & use", ["Power BI service\n(incremental refresh)", "Scoring API (FastAPI) / batch scores", "Worklist in EHR", "Reports (auto-generated)"], 0.83),
    ]
    for title, boxes, x in cols:
        ax.text(x + 0.08, 0.95, title, ha="center", fontsize=9.5, fontweight="bold", color=INK)
        h = 0.78 / len(boxes)
        for i, b in enumerate(boxes):
            y = 0.86 - (i + 1) * h + 0.02
            ax.add_patch(FancyBboxPatch((x, y), 0.16, h - 0.04, boxstyle="round,pad=0,rounding_size=0.012",
                                        fc="#e6f0fd" if i % 2 else "#cde2fb", ec="#1c5cab", lw=0.9))
            ax.text(x + 0.08, y + (h - 0.04) / 2, b, ha="center", va="center", fontsize=7.6, color=INK, wrap=True)
        if x < 0.8:
            ax.add_patch(FancyArrowPatch((x + 0.165, 0.47), (x + 0.2, 0.47), arrowstyle="-|>", mutation_scale=12,
                                         color=INK_2, lw=1.2))
    ax.text(0.5, 0.015, "Cross-cutting: access control & audit logs · encryption · CI/CD (GitHub Actions) · monitoring & alerting",
            ha="center", fontsize=8.3, color=MUTED)
    out = FIG_DIR / "review_target_architecture.png"
    finish(fig, out, source=None)
    return out


# ------------------------------------------------------------------ content
def build() -> Path:
    timing, arch = timing_chart(), architecture_chart()

    # Cover
    story.extend([Spacer(1, 4.5 * cm),
                  Paragraph("HEALTHCARE DATA ANALYTICS INTERNSHIP · PROJECT REVIEW", ParagraphStyle(
                      "kicker", fontName=BODY, fontSize=10, textColor=GREY, alignment=TA_CENTER, spaceAfter=10)),
                  Paragraph("Project Review: Process, Challenges and Roadmap", S["title"]), Spacer(1, 10),
                  Paragraph("Development process and tech stack · challenges and solutions · future enhancements · "
                            "performance · scalability · implementation efficiency", S["subtitle"]),
                  Spacer(1, 1.2 * cm),
                  Paragraph("<i>Project: 30-day readmission and resource use among diabetic inpatients "
                            "(UCI Diabetes 130-US Hospitals, 1999–2008)</i>", S["meta"]),
                  Spacer(1, 4 * cm),
                  Paragraph(f"<b>Prepared by:</b> {AUTHOR}", S["meta"]),
                  Paragraph(f"<b>Repository:</b> {REPO_URL}", S["meta"]),
                  Paragraph(f"<b>Date:</b> {date.today().strftime('%d %B %Y')}", S["meta"]),
                  PageBreak()])
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    story.extend([Paragraph("Contents", S["h1"].clone("toch", spaceAfter=10)), toc, PageBreak()])

    # Summary
    H1("Summary")
    P(f"The project is a reproducible, end-to-end healthcare analytics pipeline. It downloads a public dataset of "
      f"101,766 inpatient encounters, validates and cleans it, builds an analysis cohort of {ov['n']:,} patients, "
      f"runs statistical tests and a predictive model (random forest, test ROC-AUC {mdl['test_roc_auc']:.3f}), and "
      f"produces an interactive dashboard, a Power BI build pack, a 61-page integrated report and six weekly "
      f"reports, all from one command in about nine minutes.")
    P("This review explains how the project was built, the problems met along the way and how they were solved, "
      "and where it can go next. The biggest single opportunity is clear from the measurements: predictive "
      "modelling takes about three-quarters of the run time, and most of that is random-forest tuning.")
    table([["Topic", "Key takeaway"],
           ["Process", "Eight scripted steps, each with fixed inputs and outputs; every number traceable to code"],
           ["Challenges", "Data gaps, repeated patients, leakage risk, modest model performance and several tooling problems — all resolved or documented"],
           ["Enhancements", "Current local data, explainability (SHAP), recalibration, survival models, EHR integration"],
           ["Performance", "Faster tuning (successive halving), Parquet storage, caching unchanged steps"],
           ["Scalability", "Columnar storage and DuckDB/Spark for volume; orchestration, containers and a model registry for operations"],
           ["Efficiency", "Config files, tests, CI, a small development sample and automated document builds"]],
          [3.2, 13.8])

    # 1. Process & stack
    story.append(PageBreak())
    H1("1. Step-by-Step Development Process")
    P("The project followed a CRISP-DM-style lifecycle with added quality, ethics and communication stages. Each "
      "stage became a numbered Python script so it could be re-run and audited.")
    figure(FIG_DIR / "plan_workflow.png", "Figure 1. Project workflow (adapted from CRISP-DM).")
    table([["#", "Step", "What was done", "Output"],
           ["1", "Define the problem", "Healthcare question, objectives, scope, KPIs, hypotheses, risks and a six-week roadmap", "Strategic plan"],
           ["2", "Research data sources", "Compared seven sources on nine weighted criteria; verified access programmatically", "Dataset choice (UCI, score 4.50/5)"],
           ["3", "Set up the environment", "Isolated Python virtual environment; pinned package versions", "requirements.txt"],
           ["4", "Acquire data", "Scripted download; SHA-256 checksum; provenance and licence recorded; raw data never edited", "01_data_acquisition.py"],
           ["5", "Profile the data", "Types, missing values ('?' markers), duplicates, invalid codes, distributions", "Profiling tables"],
           ["6", "Validate and clean", "44 rules (range, domain, cross-field, uniqueness); documented cleaning; issue log", "02_data_quality_and_cleaning.py"],
           ["7", "Define the cohort", "First encounter per patient; deaths and hospice excluded", "69,970-patient cohort"],
           ["8", "Explore", "Descriptive statistics and 12 figures with confidence intervals", "03_exploratory_data_analysis.py"],
           ["9", "Test hypotheses", "Chi-square, Mann–Whitney, Kruskal–Wallis, Holm correction, logistic regression", "04_statistical_analysis.py"],
           ["10", "Model", "Baselines + 3 models; 60/20/20 patient split; CV tuning; one test evaluation; calibration; fairness", "05_predictive_modeling.py"],
           ["11", "Visualise", "Executive KPI figure, offline HTML dashboard, Power BI star schema and DAX", "06_visualization_dashboard.py"],
           ["12", "Report", "Word reports generated from outputs; references checked against Crossref", "07 and 08 scripts"],
           ["13", "Quality-check documents", "Word refreshes contents pages; PDFs rendered and inspected page by page", "Verified reports"],
           ["14", "Prove reproducibility", "Deleted all outputs and re-ran from the raw download: identical results", "Reproducibility check"],
           ["15", "Package and publish", "Full and GitHub ZIPs; public GitHub repo with MIT licence; demo script", "GitHub repository"]],
          [0.7, 3.0, 9.0, 4.3])

    H2("1.1 Tech stack")
    table([["Layer", "Tools (version used)", "Purpose"],
           ["Language", "Python 3.14.3", "All processing, analysis and document generation"],
           ["Data handling", "pandas 3.0.6, NumPy 2.5.4", "Loading, profiling, cleaning, reshaping"],
           ["Statistics", "SciPy 1.18.1, statsmodels 0.15.0", "Hypothesis tests, confidence intervals, logistic regression, VIF"],
           ["Machine learning", "scikit-learn 1.9.1, joblib 1.6.0", "Pipelines, tuning, models, metrics, model saving"],
           ["Visualisation", "Matplotlib 3.11.2, seaborn 0.13.2", "Publication-quality static charts (colour-blind-safe palette)"],
           ["Dashboard", "HTML, CSS, JavaScript (no libraries); Power BI + DAX", "Offline interactive dashboard; Power BI build pack"],
           ["Documents", "python-docx 1.2.0; Microsoft Word (COM via PowerShell); ReportLab", "Word reports, TOC refresh, this PDF"],
           ["Quality checks", "PyMuPDF; headless Microsoft Edge", "Render pages for inspection; dashboard screenshots"],
           ["Data access", "requests 2.34.2; Crossref API", "Download data; verify references"],
           ["Version control", "Git 2.55, GitHub, GitHub CLI", "History, publishing, collaboration"],
           ["Platform", "Windows 11, PowerShell", "Development and execution"]],
          [3.0, 6.0, 8.0])

    # 2. Challenges
    story.append(PageBreak())
    H1("2. Challenges and How They Were (or Could Be) Solved")
    P("The challenges below were all encountered in this project. Each row gives why it mattered and the solution "
      "used, plus a better long-term option where one exists.")
    H2("2.1 Data challenges")
    table([["Challenge", "Why it mattered", "Solution"],
           ["Best datasets were restricted (MIMIC-IV, HCUP)", "Credentialing or purchase would take weeks", "Weighted selection favoured an open CC BY 4.0 dataset; restricted sources kept as future options"],
           ["Missing values coded as '?' and 'NULL/Not Mapped'", "Standard tools would not count them as missing", "Converted markers to true missing values; mapped codes with the official mapping file"],
           ["Weight 97% missing; specialty 49%; payer 40%", "Imputation would fabricate data", "Dropped weight; kept others with an explicit 'Unknown' level; documented the effect"],
           ["Completeness metric initially overstated", "Counting 'Unknown' as complete inflated the improvement", "Redefined the metric to treat 'Unknown' as missing (honest 95.8% → 97.6%)"],
           ["Repeated encounters (up to 40 per patient)", "Breaks independence; leaks patients across train/test", "One index encounter per patient; grouped CV suggested as a sensitivity analysis"],
           ["Data from 1999–2008, no dates or hospital IDs", "No trends, benchmarking or temporal validation", "Stated as a limitation; future work uses current local data"]],
          [4.3, 5.0, 7.7])
    H2("2.2 Methodological challenges")
    table([["Challenge", "Why it mattered", "Solution"],
           ["Risk of target leakage", "Would inflate model performance", "Prediction-time rule; outcome fields excluded; preprocessing inside pipelines"],
           ["Rare outcome (9%)", "Accuracy is misleading (91% by predicting 'no')", "PR-AUC, sensitivity and PPV; threshold chosen from workload (top 20%)"],
           ["Large sample makes everything 'significant'", "p-values alone mislead", "Effect sizes, confidence intervals and Holm correction"],
           [f"Modest model performance (AUC {mdl['test_roc_auc']:.3f})", "Not accurate enough for individual decisions", "Honest reporting; recommendations rely on statistical findings; richer data proposed"],
           [f"Calibration slope {mdl['calibration']['calibration_slope']:.2f}", "Risk estimates compressed toward the mean", "Reported; Platt/isotonic recalibration proposed before any use"],
           ["Baseline flagged every patient", "Tied scores at the cut-off", "Strict threshold (p > t) made it the intended 'any prior admission' rule"],
           ["Fairness concerns", "Race and payer could encode inequity", "Excluded as predictors; subgroup audit instead"]],
          [4.3, 5.0, 7.7])
    H2("2.3 Engineering and tooling challenges")
    table([["Challenge", "Solution used", "Better long-term option"],
           ["Python not on PATH; stale Anaconda entry", "Located the installed interpreter with the py launcher", "Document setup in README; use uv or conda environment files"],
           ["Virtual environment failed on a very long path", "Created it at a short path", "Keep projects in short paths (e.g. C:\\dev\\project)"],
           ["Power BI Desktop cannot be automated", "Offline HTML dashboard + Power BI build pack", "Power BI service with a scheduled dataset refresh"],
           ["Word tables of contents do not update by themselves", "Refresh via Word automation (PowerShell COM)", "LibreOffice headless or docx2pdf in CI"],
           ["Hidden Word dialogs froze automation", "Closed orphaned processes; verified documents from file contents", "Time-outs and a clean Word profile for automation"],
           ["Headless Edge screenshots silently failed", "Separate browser profile and temp copy of the page", "Playwright for reliable browser automation"],
           ["Unicode errors in the Windows console", "PYTHONIOENCODING=utf-8", "Set UTF-8 mode globally (PYTHONUTF8=1)"],
           ["Project files lost during a storage change", "Regenerated everything from the scripted pipeline; checksums matched", "Commit early to GitHub; keep work outside temporary folders"],
           ["GitHub showed the licence as 'Other'", "Standard MIT text in LICENSE; data licence in README", "Use GitHub's licence templates"]],
          [4.5, 6.0, 6.5])

    # 3. Enhancements
    story.append(PageBreak())
    H1("3. Future Enhancements and Upgrades")
    table([["Area", "Enhancement", "Benefit", "Effort"],
           ["Data", "Current local hospital data (ICD-10) with admission dates and hospital IDs", "Relevance; trends; temporal validation; benchmarking", "High"],
           ["Data", "Add vital signs, lab values, social determinants, follow-up visits", "Better prediction (current AUC is modest)", "High"],
           ["Data", "Link CMS HRRP hospital-level data as a separate benchmark study", "Hospital comparisons", "Medium"],
           ["Analytics", "Time-series forecasting of monthly readmissions (ETS/ARIMA)", "Capacity planning", "Medium"],
           ["Analytics", "Survival models (time to readmission, death as competing risk)", "Uses timing information", "Medium"],
           ["Analytics", "Propensity-score analysis of HbA1c testing", "Stronger evidence than plain association", "Medium"],
           ["Model", "SHAP explanations per patient", "Transparent, clinician-friendly reasons", "Low"],
           ["Model", "Recalibration (isotonic/Platt) and decision-curve analysis", "Trustworthy risks; shows clinical usefulness", "Low"],
           ["Model", "Fairness mitigation and monitoring dashboards", "Equitable performance across groups", "Medium"],
           ["Model", "NLP on discharge summaries", "Captures information missing from coded data", "High"],
           ["Product", "Build the Power BI .pbix and publish to the Power BI service", "Organisation-wide access with security", "Low"],
           ["Product", "Streamlit app for what-if exploration and patient scoring", "Interactive model demonstration", "Low"],
           ["Integration", "FHIR-based worklist inside the EHR", "Risk flags where clinicians work", "High"],
           ["Evaluation", "Stepped-wedge pilot of the discharge interventions", "Measures real impact on readmissions", "High"],
           ["Reporting", "Automated plain-language summaries for each refresh", "Faster communication to non-technical staff", "Low"]],
          [2.2, 7.0, 5.6, 2.2])

    # 4. Performance
    story.append(PageBreak())
    H1("4. Optimising Performance")
    P("Optimisation should start from measurement. The full pipeline takes about nine minutes; predictive "
      "modelling accounts for 74% of that, and random-forest tuning alone for 40%.")
    figure(timing, "Figure 2. Measured run time per step and inside the modelling step.")
    H2("4.1 Optimisations ranked by expected impact")
    table([["Optimisation", "Where", "Expected effect"],
           ["Successive-halving search (HalvingRandomSearchCV) instead of full randomised search", "Step 05", "Large cut in tuning time; poor candidates are dropped early on small samples"],
           ["Fewer trees / depth limits for the random forest, or select gradient boosting", "Step 05", "Faster training and a much smaller model file (currently about 20 MB); gradient boosting's test AUC was only about 0.002 lower"],
           ["Fewer bootstrap resamples and permutation repeats (or run them on a sample)", "Step 05", "The 87 s evaluation phase is dominated by bootstrap confidence intervals and permutation importance"],
           ["Store cleaned data as Parquet with categorical types", "Steps 02–08", "Smaller files (38 MB CSV) and faster loading in every later step"],
           ["Cache: skip a step when its inputs have not changed (Make, DVC)", "All", "Re-runs after small edits take seconds instead of minutes"],
           ["Remove slow access probes from routine runs", "Step 01", "About 20 s of the 28 s is spent checking alternative datasets; the download itself takes about 4 s"],
           ["Vectorise the ICD-9 grouping (numeric ranges with pd.cut)", "Step 02", "Replaces a Python function applied to 300,000 codes"],
           ["Pre-aggregate dashboard data instead of embedding row-level data", "Step 06", "Smaller, faster dashboard (currently 1.9 MB)"],
           ["Run independent steps in parallel (statistics and EDA)", "03–04", "Shorter wall-clock time"]],
          [7.6, 1.8, 7.6])
    H2("4.2 Model inference performance")
    bullets(["Batch scoring of all discharges once a day is cheaper than scoring on every request.",
             "A smaller model (gradient boosting or a pruned forest) loads and scores faster in an API.",
             "Export to ONNX for fast, language-independent inference if real-time scoring is needed."])

    # 5. Scalability
    story.append(PageBreak())
    H1("5. Making the Project Scalable")
    P("The current design runs comfortably on one laptop for about 100,000 records. Scaling has two dimensions: more "
      "data (more hospitals, more years, more variables) and more use (more users, regular refreshes, live scoring).")
    figure(arch, "Figure 3. Target architecture for a multi-hospital, regularly refreshed deployment.")
    table([["Dimension", "Current", "Scalable approach"],
           ["Data volume", "CSV files in memory with pandas", "Partitioned Parquet; DuckDB for single-machine analytics; Spark or Polars for very large data"],
           ["Storage", "Local folders", "Data lake + warehouse (PostgreSQL, Snowflake or BigQuery) with access control"],
           ["Ingestion", "Download from UCI", "Scheduled, incremental loads from EHR (FHIR), lab and claims systems"],
           ["Transformations", "pandas scripts", "SQL/dbt models for shared logic; validation suite run on every load"],
           ["Orchestration", "run_pipeline.py", "Airflow or Prefect with retries, schedules and alerts"],
           ["Environment", "Local virtual environment", "Docker images for identical runs anywhere"],
           ["Modelling", "Single training run", "MLflow tracking and model registry; scheduled retraining; drift monitoring"],
           ["Serving", "Saved model + demo script", "FastAPI scoring service or nightly batch scores written to the warehouse"],
           ["Dashboards", "Static HTML file", "Power BI service with incremental refresh and row-level security per hospital"],
           ["Configuration", "Constants in code", "YAML configuration per site (paths, thresholds, code mappings)"],
           ["Multi-site", "One dataset", "Hospital ID in every table; per-site validation and calibration"]],
          [2.8, 4.2, 10.0])
    H2("5.1 Governance at scale")
    bullets(["Role-based access and audit logs for all identifiable data (DPDP Act 2023 and Rules 2025 in India).",
             "Data-sharing agreements and a data-protection impact assessment for every new site.",
             "A model card and monitoring report for every model version."])

    # 6. Efficiency
    story.append(PageBreak())
    H1("6. Improving Implementation Efficiency")
    table([["Strategy", "How", "Benefit"],
           ["Work on a development sample", "A 5–10% stratified sample for coding and debugging; full data only for final runs", "Seconds per iteration instead of minutes"],
           ["Configuration file", "Move paths, seeds, thresholds and model grids to a YAML file", "Change behaviour without editing code"],
           ["Automated tests", "pytest for cleaning rules, cohort logic and metric functions", "Catches errors like the baseline threshold bug immediately"],
           ["Continuous integration", "GitHub Actions runs tests and the pipeline on a sample at every push", "Broken changes never reach the main branch"],
           ["Linting and formatting", "ruff + pre-commit hooks", "Consistent, readable code with less review effort"],
           ["Incremental builds", "Make or DVC so only changed steps re-run", "Faster feedback loop"],
           ["Shared helpers", "Common modules (data loading, styles, document helpers) — already used", "Less duplication; one place to fix"],
           ["Documents as code", "Reports generated from results — already used", "Numbers can never drift from the analysis"],
           ["Notebooks for exploration only", "Explore in Jupyter, then move stable code into scripts", "Speed of exploration with reliable pipelines"],
           ["Logging and timing", "Structured logs with durations per step", "Bottlenecks are visible (as in Figure 2)"],
           ["Commit early and often", "Small Git commits with clear messages; push to GitHub daily", "History and backup (avoids the file-loss problem)"],
           ["Reproducible environments", "Pin versions; lock files; Docker", "No 'works on my machine' problems"]],
          [3.6, 7.4, 6.0])
    H2("6.1 Example: development sample")
    story.append(Paragraph("cohort = pd.read_parquet('data/processed/cohort.parquet')<br/>"
                           "if config['dev_mode']:<br/>"
                           "&nbsp;&nbsp;&nbsp;&nbsp;cohort = cohort.groupby('readmit_30', group_keys=False)"
                           ".sample(frac=0.1, random_state=42)", S["code"]))

    # Roadmap
    H1("7. Prioritised Improvement Roadmap")
    table([["Horizon", "Actions"],
           ["Quick wins (1–2 weeks)", "Successive-halving tuning; Parquet storage; drop probes from routine runs; pytest suite; GitHub Actions; YAML config; recalibration and SHAP; build the Power BI .pbix"],
           ["Medium term (1–3 months)", "DuckDB warehouse; Docker; MLflow; Prefect orchestration; decision-curve analysis; forecasting; Streamlit demo"],
           ["Long term (3–12 months)", "Local current data under a data-sharing agreement; FHIR integration; multi-site deployment with monitoring; pilot evaluation of interventions"]],
          [4.0, 13.0])
    P("These steps keep the project's main strengths — reproducibility, transparency and honest evaluation — while "
      "making it faster to work on, cheaper to run and ready for real organisational use.", "note")

    doc = Doc(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
              title="Project Review: Process, Challenges and Roadmap", author=AUTHOR,
              subject="Healthcare data analytics project review")
    doc.multiBuild(story, onFirstPage=page_decor, onLaterPages=page_decor)
    print(f"Saved {OUT}")
    return OUT


if __name__ == "__main__":
    build()
