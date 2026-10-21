"""Shared Matplotlib styling and plotting helpers.

Colours follow a colour-vision-deficiency-validated reference palette:
categorical hues are used in a fixed order, magnitude uses a single-hue ramp,
and text is always drawn in neutral ink rather than series colours.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from statsmodels.stats.proportion import proportion_confint  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
HIGHLIGHT = SERIES[1]
BASE = SERIES[0]
NEUTRAL_BAR = "#c3c2b7"
BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
ORDINAL_BLUE = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]
DIVERGING = LinearSegmentedColormap.from_list("blue_gray_red", ["#104281", "#5598e7", "#f0efec", "#e66767",
                                                                 "#a02c2c"])
SEQUENTIAL = LinearSegmentedColormap.from_list("blue_seq", [BLUE_RAMP[0], BLUE_RAMP[6], BLUE_RAMP[-1]])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 22,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
    "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2, "legend.frameon": False, "legend.labelcolor": INK_2,
    "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def rate_ci(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float, float]:
    """Proportion with Wilson score interval."""
    lo, hi = proportion_confint(successes, n, alpha=alpha, method="wilson")
    return successes / n, lo, hi


def rate_table(df: pd.DataFrame, group: str, target: str = "readmit_30", order=None, min_n: int = 0) -> pd.DataFrame:
    g = df.groupby(group, observed=True)[target].agg(["sum", "count"]).rename(columns={"sum": "events", "count": "n"})
    rows = [(idx, *rate_ci(int(r.events), int(r.n))) for idx, r in g.iterrows()]
    out = pd.DataFrame(rows, columns=[group, "rate", "ci_low", "ci_high"]).set_index(group)
    out = g.join(out)
    if order is not None:
        out = out.reindex([o for o in order if o in out.index])
    return out[out["n"] >= min_n]


def finish(fig, path: Path, caption: str | None = None, source: str = "Source: UCI Diabetes 130-US Hospitals "
           "(1999–2008), analysis cohort; author's analysis.") -> None:
    if source:
        fig.text(0.0, -0.02, source, fontsize=7.5, color=MUTED, ha="left", va="top", transform=fig.transFigure)
    fig.savefig(path)
    plt.close(fig)


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.012, text, transform=ax.transAxes, fontsize=9, color=INK_2, ha="left", va="bottom")


def rate_barh(ax, tbl: pd.DataFrame, overall: float | None = None, color=BASE, highlight: set | None = None,
              pct_fmt: str = "{:.1%}", xlabel: str = "30-day readmission rate (95% CI)") -> None:
    """Horizontal rate bars with Wilson CIs, n labels and an overall reference line."""
    y = np.arange(len(tbl))
    colors = [HIGHLIGHT if highlight and idx in highlight else color for idx in tbl.index]
    ax.barh(y, tbl["rate"], color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    ax.errorbar(tbl["rate"], y, xerr=[tbl["rate"] - tbl["ci_low"], tbl["ci_high"] - tbl["rate"]],
                fmt="none", ecolor=INK_2, elinewidth=1, capsize=2.5)
    for yi, (idx, r) in zip(y, tbl.iterrows()):
        ax.text(r["ci_high"] + 0.003, yi, f"{pct_fmt.format(r['rate'])}  (n={int(r['n']):,})", va="center",
                fontsize=8.5, color=INK_2)
    ax.set_yticks(y, [str(i) for i in tbl.index])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel(xlabel)
    ax.set_xlim(0, max(tbl["ci_high"].max() * 1.32, 0.05))
    if overall is not None:
        ax.axvline(overall, color=INK_2, linewidth=1, linestyle=(0, (1, 2)))
        ax.text(overall, 0.005, f" overall {pct_fmt.format(overall)}", fontsize=8, color=INK_2, ha="left",
                va="bottom", transform=ax.get_xaxis_transform())
