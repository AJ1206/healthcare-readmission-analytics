"""Planning diagrams for the weekly reports: Gantt roadmap, workflow, risk matrix, modelling flow and
dashboard wireframes. Wireframes are design mock-ups (layout only); real numbers come from the analysis."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FIG_DIR  # noqa: E402
from viz_style import BASE, HIGHLIGHT, INK, INK_2, MUTED, SURFACE, finish  # noqa: E402

LIGHT = "#cde2fb"
MID = "#86b6ef"
DARK = "#1c5cab"
WARM = "#fde3d6"
GREY = "#eeede9"
NO_SOURCE = None


def _box(ax, x, y, w, h, text, fc=LIGHT, ec=DARK, fs=8.5, bold=False, color=INK, ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015", fc=fc, ec=ec, lw=1))
    tx = x + w / 2 if ha == "center" else x + 0.012
    ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, color=color, fontweight="bold" if bold else "normal",
            wrap=True)


def _arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11, color=INK_2, lw=1.1))


def gantt() -> Path:
    tasks = [  # (label, start_week, duration_weeks, phase_colour)
        ("Problem definition & stakeholder interviews", 0.0, 0.5, DARK),
        ("Objectives, scope, KPIs, risk register", 0.4, 0.6, DARK),
        ("Dataset research & selection", 0.9, 0.4, BASE),
        ("Acquisition, profiling, cleaning, QA", 1.2, 0.8, BASE),
        ("Exploratory analysis & figures", 2.0, 0.6, MID),
        ("Dashboard design & build", 2.4, 0.6, MID),
        ("Hypothesis tests & regression", 3.0, 0.5, HIGHLIGHT),
        ("Predictive modelling & evaluation", 3.3, 0.7, HIGHLIGHT),
        ("Interpretation & recommendations", 4.0, 0.7, "#6250d6"),
        ("Draft analytical report", 4.4, 0.6, "#6250d6"),
        ("Integration, packaging, self-assessment", 5.0, 0.8, "#008300"),
        ("Final review & submission", 5.7, 0.3, "#008300"),
    ]
    milestones = [(1.0, "M1 Charter approved"), (2.0, "M2 Clean data + QA report"), (3.0, "M3 Figures + dashboard"),
                  (4.0, "M4 Model validated"), (5.0, "M5 Draft report"), (6.0, "M6 Final submission")]
    fig, ax = plt.subplots(figsize=(11, 5.4))
    for i, (lbl, s, d, c) in enumerate(tasks):
        ax.barh(i, d, left=s, color=c, height=0.55)
    ax.set_yticks(range(len(tasks)), [t[0] for t in tasks], fontsize=8.5)
    ax.invert_yaxis()
    for x, lbl in milestones:
        ax.axvline(x, color=INK_2, lw=0.8, ls=(0, (2, 3)))
        ax.plot(x, len(tasks) - 0.35, marker="D", color=INK, ms=6, clip_on=False)
        ax.text(x, len(tasks) + 0.25, lbl, rotation=0, ha="center", va="top", fontsize=7.5, color=INK_2)
    ax.set_xlim(0, 6.05)
    ax.set_ylim(len(tasks) + 0.6, -0.7)
    ax.set_xticks([0.5 + i for i in range(6)], [f"Week {i + 1}" for i in range(6)])
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_title("Six-week project roadmap (Gantt chart)")
    out = FIG_DIR / "plan_gantt.png"
    finish(fig, out, source="Planned schedule: 30–35 hours per week (195 hours). Diamonds mark milestone reviews.")
    return out


def workflow() -> Path:
    fig, ax = plt.subplots(figsize=(11.5, 3.6))
    ax.set_axis_off()
    fig.subplots_adjust(left=0.005, right=0.995, top=0.98, bottom=0.02)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    stages = [("1  Define", "Problem, scope,\nKPIs, risks"), ("2  Acquire", "Source, licence,\nchecksum"),
              ("3  Assure quality", "Profile, validate,\nclean, log"), ("4  Explore", "Distributions,\ncomparisons"),
              ("5  Analyse", "Tests, CIs,\nregression"), ("6  Model", "Train, tune,\nvalidate"),
              ("7  Communicate", "Dashboard,\nreport"), ("8  Act & monitor", "Recommend,\ntrack KPIs")]
    w, gap = 0.105, 0.0175
    for i, (title, sub) in enumerate(stages):
        x = 0.01 + i * (w + gap)
        _box(ax, x, 0.42, w, 0.32, "", fc=LIGHT if i % 2 == 0 else "#e6f0fd")
        ax.text(x + w / 2, 0.66, title, ha="center", va="center", fontsize=8.6, fontweight="bold", color=INK)
        ax.text(x + w / 2, 0.52, sub, ha="center", va="center", fontsize=7.6, color=INK_2)
        if i < len(stages) - 1:
            _arrow(ax, x + w + 0.002, 0.58, x + w + gap - 0.002, 0.58)
    ax.add_patch(FancyArrowPatch((0.95, 0.4), (0.06, 0.4), connectionstyle="arc3,rad=-0.25", arrowstyle="-|>",
                                 mutation_scale=11, color=MUTED, lw=1, ls="--"))
    ax.text(0.5, 0.08, "Feedback loop: monitoring results and stakeholder review feed the next planning cycle",
            ha="center", fontsize=8, color=MUTED)
    ax.text(0.5, 0.86, "Governance throughout: privacy & ethics checkpoints · weekly milestone reviews · version control",
            ha="center", fontsize=8.5, color=INK_2,
            bbox=dict(boxstyle="round,pad=0.4", fc=GREY, ec="none"))
    out = FIG_DIR / "plan_workflow.png"
    finish(fig, out, source=None)
    return out


def risk_matrix(risks: list[tuple[str, int, int]]) -> Path:
    """risks: (id, likelihood 1-3, impact 1-3)."""
    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    colours = {2: "#d8ecd8", 3: "#d8ecd8", 4: "#fff1cc", 5: "#fde3d6", 6: "#f6c6c6", 9: "#f0a8a8"}
    for li in range(1, 4):
        for im in range(1, 4):
            score = li * im
            ax.add_patch(Rectangle((im - 0.5, li - 0.5), 1, 1, fc=colours.get(score, "#eef7ee"), ec=SURFACE, lw=3))
            ax.text(im + 0.42, li - 0.42, f"{score}", ha="right", va="bottom", fontsize=7, color=MUTED)
    cells: dict[tuple[int, int], list[str]] = {}
    for rid, li, im in risks:
        cells.setdefault((li, im), []).append(rid)
    for (li, im), ids in cells.items():
        ax.text(im, li, "\n".join(", ".join(ids[k:k + 3]) for k in range(0, len(ids), 3)), ha="center", va="center",
                fontsize=8.5, color=INK, fontweight="bold")
    ax.set_xlim(0.5, 3.5)
    ax.set_ylim(0.5, 3.5)
    ax.set_xticks([1, 2, 3], ["Low", "Medium", "High"])
    ax.set_yticks([1, 2, 3], ["Low", "Medium", "High"])
    ax.set_xlabel("Impact")
    ax.set_ylabel("Likelihood")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Risk heat map (likelihood × impact)")
    out = FIG_DIR / "plan_risk_matrix.png"
    finish(fig, out, source="Score = likelihood × impact (1–3 each). Risk IDs refer to the risk register.")
    return out


def modelling_flow() -> Path:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.set_axis_off()
    fig.subplots_adjust(left=0.005, right=0.995, top=0.98, bottom=0.02)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    steps = ["Define target,\nprediction time,\nunit of analysis", "Build cohort;\nremove leakage\n& identifiers",
             "Split by patient:\ntrain 60 / val 20 /\ntest 20 (stratified)", "Pre-process inside\npipeline (encode,\nscale, impute)",
             "Baselines:\nprevalence;\none-variable rule", "Candidates: LR,\nrandom forest,\ngradient boosting",
             "Tune with 5-fold\nCV on training\ndata only", "Select model &\nthreshold on\nvalidation set",
             "Evaluate ONCE on\ntest: AUC, PR-AUC,\ncalibration", "Fairness audit,\ninterpretability,\nmodel card"]
    w, h = 0.17, 0.27
    for i, s in enumerate(steps):
        row, col = divmod(i, 5)
        x = 0.02 + col * 0.197
        y = 0.6 if row == 0 else 0.17
        fc = WARM if i == 8 else (LIGHT if row == 0 else "#e6f0fd")
        _box(ax, x, y, w, h, s, fc=fc, fs=8)
        ax.text(x + 0.012, y + h - 0.035, str(i + 1), fontsize=8, color=DARK, fontweight="bold")
        if col < 4:
            _arrow(ax, x + w + 0.002, y + h / 2, x + 0.197 - 0.002, y + h / 2)
    ax.add_patch(FancyArrowPatch((0.02 + 4 * 0.197 + w / 2, 0.6), (0.02 + w / 2, 0.44), connectionstyle="arc3,rad=0.08",
                                 arrowstyle="-|>", mutation_scale=11, color=INK_2, lw=1.1))
    ax.text(0.5, 0.05, "The test set is touched only in step 9, after every modelling decision is fixed (prevents optimistic bias).",
            ha="center", fontsize=8.5, color=INK_2)
    out = FIG_DIR / "plan_modelling_flow.png"
    finish(fig, out, source=None)
    return out


def _frame(title, subtitle):
    fig, ax = plt.subplots(figsize=(11, 6.6))
    fig.subplots_adjust(left=0.005, right=0.995, top=0.995, bottom=0.03)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0, 0), 1, 1, fc="#ffffff", ec="#b9b8b2", lw=1.2))
    ax.add_patch(Rectangle((0, 0.93), 1, 0.07, fc=GREY, ec="none"))
    ax.text(0.015, 0.965, title, va="center", fontsize=10.5, fontweight="bold", color=INK)
    ax.text(0.985, 0.965, subtitle, va="center", ha="right", fontsize=8, color=MUTED)
    return fig, ax


def _mini_bars(ax, x, y, w, h, n=5, horizontal=True, colour=MID):
    vals = [0.9, 0.7, 0.55, 0.45, 0.3, 0.25, 0.2][:n]
    if horizontal:
        bh = h / (n * 1.6)
        for i, v in enumerate(vals):
            ax.add_patch(Rectangle((x + 0.09 * w, y + h - (i + 1) * bh * 1.6), v * 0.8 * w, bh, fc=colour, ec="none"))
            ax.add_patch(Rectangle((x + 0.01 * w, y + h - (i + 1) * bh * 1.6), 0.07 * w, bh, fc=GREY, ec="none"))
    else:
        bw = w / (n * 1.6)
        for i, v in enumerate(vals[::-1]):
            ax.add_patch(Rectangle((x + 0.05 * w + i * bw * 1.6, y + 0.05 * h), bw, v * 0.85 * h, fc=colour, ec="none"))


def _panel(ax, x, y, w, h, title, note=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.01", fc="#fbfbfa", ec="#cfcec8", lw=1))
    ax.text(x + 0.01, y + h - 0.03, title, fontsize=8.3, fontweight="bold", color=INK, va="top")
    if note:
        ax.text(x + 0.01, y + 0.015, note, fontsize=6.8, color=MUTED, va="bottom")


def wireframe_executive() -> Path:
    fig, ax = _frame("Executive overview — readmissions & capacity", "Wireframe · monthly refresh · audience: leadership")
    ax.text(0.015, 0.895, "Filters:  [ Period ▾ ]  [ Hospital/ward ▾ ]  [ Age group ▾ ]  [ Diagnosis ▾ ]   (Reset)",
            fontsize=8, color=INK_2)
    for i, (lbl, val) in enumerate([("30-day readmission", "x.x% (CI)"), ("Readmissions", "n,nnn"),
                                    ("Avg length of stay", "x.x days"), ("Bed-days", "nnn,nnn"),
                                    ("HbA1c testing rate", "xx%"), ("vs target", "▲ / ▼ pp")]):
        x = 0.015 + i * 0.163
        _panel(ax, x, 0.7, 0.152, 0.15, lbl)
        ax.text(x + 0.01, 0.745, val, fontsize=12, fontweight="bold", color=INK)
    _panel(ax, 0.015, 0.36, 0.48, 0.31, "Trend: monthly 30-day rate with target band", "Line + CI band; annotate interventions")
    xs = [0.04 + i * 0.037 for i in range(12)]
    ys = [0.47, 0.5, 0.48, 0.53, 0.51, 0.49, 0.46, 0.47, 0.44, 0.45, 0.43, 0.42]
    ax.fill_between(xs, [v - 0.03 for v in ys], [v + 0.03 for v in ys], color=LIGHT)
    ax.plot(xs, ys, color=BASE, lw=2)
    ax.axhline(0.45, xmin=0.04, xmax=0.48, color=HIGHLIGHT, lw=1, ls="--")
    _panel(ax, 0.51, 0.36, 0.475, 0.31, "Rate by discharge destination (with 95% CI)", "Sorted bars; overall reference line")
    _mini_bars(ax, 0.52, 0.39, 0.45, 0.22, n=6)
    _panel(ax, 0.015, 0.03, 0.31, 0.3, "Where are bed-days used? (by diagnosis)", "Bar of share of bed-days")
    _mini_bars(ax, 0.02, 0.06, 0.3, 0.2, n=5, colour=BASE)
    _panel(ax, 0.335, 0.03, 0.31, 0.3, "Risk mix: prior admissions", "Ordinal bars: 0 / 1 / 2 / 3+")
    _mini_bars(ax, 0.34, 0.06, 0.3, 0.2, n=4, horizontal=False, colour=MID)
    _panel(ax, 0.655, 0.03, 0.33, 0.3, "Key messages (plain language)")
    for k, t in enumerate(["• 1 in 11 patients returns within 30 days", "• Facility discharges: 2× the risk",
                           "• Prior admission: strongest warning sign", "• Data note: groups n<30 suppressed"]):
        ax.text(0.665, 0.25 - k * 0.045, t, fontsize=7.8, color=INK_2)
    out = FIG_DIR / "wireframe_executive_dashboard.png"
    finish(fig, out, source="Mock-up for design review (layout only; values illustrative). Built version: Appendix / dashboard file.")
    return out


def wireframe_operational() -> Path:
    fig, ax = _frame("Discharge-planning worklist — today's discharges", "Wireframe · daily refresh · audience: case managers")
    ax.text(0.015, 0.895, "Ward [ All ▾ ]   Discharge date [ Today ▾ ]   Show: (●) High priority  ( ) All   Search [ patient ID ]",
            fontsize=8, color=INK_2)
    cols = ["Patient (ID)", "Ward", "Age", "Discharge to", "Prior admits (12 m)", "Risk group", "Follow-up booked?", "Action"]
    xs = [0.02, 0.14, 0.22, 0.28, 0.43, 0.57, 0.69, 0.83]
    ax.add_patch(Rectangle((0.015, 0.8), 0.97, 0.05, fc=GREY, ec="none"))
    for x, c in zip(xs, cols):
        ax.text(x, 0.825, c, fontsize=7.8, fontweight="bold", color=INK, va="center")
    rows = [("P-10xx", "Med 3", "82", "Skilled nursing", "3", "High", "No", "Call facility"),
            ("P-10xx", "Card 1", "76", "Rehab unit", "1", "High", "Yes", "—"),
            ("P-10xx", "Med 2", "64", "Home + health svc", "2", "Medium", "No", "Book 7-day visit"),
            ("P-10xx", "Surg 1", "58", "Home", "0", "Standard", "—", "Routine"),
            ("P-10xx", "Med 3", "71", "Home", "0", "Standard", "—", "Routine")]
    for r, row in enumerate(rows):
        y = 0.76 - r * 0.06
        if r % 2:
            ax.add_patch(Rectangle((0.015, y - 0.025), 0.97, 0.05, fc="#f6f6f4", ec="none"))
        for x, v in zip(xs, row):
            colour = INK
            if v == "High":
                ax.add_patch(FancyBboxPatch((x - 0.004, y - 0.016), 0.07, 0.032, boxstyle="round,pad=0,rounding_size=0.008",
                                            fc=WARM, ec="none"))
                v = "▲ High"
            ax.text(x, y, v, fontsize=7.8, color=colour, va="center")
    _panel(ax, 0.015, 0.05, 0.47, 0.37, "Why is this patient flagged? (selected row)", "Plain-language reasons, not raw model output")
    for k, t in enumerate(["• Discharged to skilled nursing facility", "• 3 hospital admissions in the past year",
                           "• Age 80+", "Risk group = top 20% of predicted risk", "Clinician judgement overrides the flag."]):
        ax.text(0.03, 0.34 - k * 0.05, t, fontsize=8, color=INK_2 if k < 3 else MUTED)
    _panel(ax, 0.5, 0.05, 0.485, 0.37, "Checklist before discharge", "Recorded in the EHR; completion rate is a process KPI")
    for k, t in enumerate(["☐ Medication reconciliation sent to facility", "☐ Discharge summary within 24 h",
                           "☐ Follow-up appointment ≤ 7 days", "☐ Patient / caregiver teach-back done",
                           "☐ HbA1c checked (if none in last 3 months)"]):
        ax.text(0.515, 0.34 - k * 0.05, t, fontsize=8, color=INK_2)
    out = FIG_DIR / "wireframe_operational_worklist.png"
    finish(fig, out, source="Mock-up for design review (no real patients). A live worklist requires local validation and governance approval.")
    return out


def wireframe_report() -> Path:
    fig, ax = _frame("Quarterly quality report — one-page brief", "Wireframe · PDF/print · audience: quality committee")
    _panel(ax, 0.015, 0.68, 0.97, 0.22, "Headline")
    ax.text(0.03, 0.8, "30-day readmissions fell / rose from x.x% to y.y% this quarter (95% CI …).", fontsize=11, color=INK,
            fontweight="bold")
    ax.text(0.03, 0.73, "One sentence on what changed and why it matters for patients and capacity.", fontsize=8.5, color=INK_2)
    _panel(ax, 0.015, 0.3, 0.475, 0.35, "Chart 1: rate by discharge destination", "Same chart every quarter = easy comparison")
    _mini_bars(ax, 0.02, 0.34, 0.46, 0.25, n=6)
    _panel(ax, 0.51, 0.3, 0.475, 0.35, "Chart 2: data-quality traffic lights", "Completeness of key fields vs 90% target")
    for k, (lbl, ok) in enumerate([("Weight / BMI", False), ("Admitting specialty", False), ("Payer", False),
                                   ("Diagnosis codes", True), ("Discharge destination", True)]):
        y = 0.57 - k * 0.05
        ax.add_patch(plt.Circle((0.535, y), 0.012, color="#0ca30c" if ok else "#d03b3b"))
        ax.text(0.555, y, f"{lbl}: {'meets target' if ok else 'below target'}", va="center", fontsize=8, color=INK_2)
    _panel(ax, 0.015, 0.03, 0.97, 0.24, "Recommendations & owners")
    for k, t in enumerate(["1. Action — owner — due date — success metric", "2. Action — owner — due date — success metric",
                           "3. Action — owner — due date — success metric"]):
        ax.text(0.03, 0.19 - k * 0.05, t, fontsize=8.5, color=INK_2)
    out = FIG_DIR / "wireframe_quality_report.png"
    finish(fig, out, source="Mock-up for design review (layout only). Status colours are always paired with a text label.")
    return out


def all_figures(risks):
    return {"gantt": gantt(), "workflow": workflow(), "risk": risk_matrix(risks), "modelling": modelling_flow(),
            "wf_exec": wireframe_executive(), "wf_ops": wireframe_operational(), "wf_report": wireframe_report()}
