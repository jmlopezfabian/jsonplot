"""Helpers shared by the matplotlib renderers."""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Total width a bar group occupies, in category units.
GROUP_WIDTH = 0.8
#: Air between adjacent bars, as a fraction of bar width.
BAR_GAP = 0.08

_TIME_FMT = {
    "year": "%Y",
    "quarter": "%Y-Q%q",
    "month": "%Y-%m",
    "week": "%d %b %Y",
    "day": "%d %b %Y",
}


def categories(pf: pd.DataFrame, role: str) -> list:
    """Categories in the order the plot frame delivers them."""
    if role not in pf.columns:
        return []
    return list(pd.Index(pf[role].drop_duplicates()))


def positions(cats: list) -> dict:
    return {c: i for i, c in enumerate(cats)}


def tick_labels(values, channel) -> list[str]:
    """Readable labels for the discrete axis."""
    if channel is not None and channel.type == "temporal":
        fmt = _TIME_FMT.get(channel.time_unit or "day", "%Y-%m-%d")
        out = []
        for v in values:
            ts = pd.Timestamp(v)
            if "%q" in fmt:
                out.append(ts.strftime("%Y") + f"-Q{ts.quarter}")
            else:
                out.append(ts.strftime(fmt))
        return out
    return [_short(v) for v in values]


def _short(v) -> str:
    s = str(v)
    return s if len(s) <= 28 else s[:27] + "…"


def bar_slots(n_series: int) -> list[tuple[float, float]]:
    """(offset, width) for each series within a group.

    The gap between adjacent bars is surface air, not a border: it separates
    the marks without adding a line that competes with the data.
    """
    if n_series <= 1:
        return [(0.0, GROUP_WIDTH)]
    slot = GROUP_WIDTH / n_series
    width = slot * (1 - BAR_GAP)
    start = -GROUP_WIDTH / 2 + slot / 2
    return [(start + i * slot, width) for i in range(n_series)]


def annotate_bars(ax, xs, ys, horizontal: bool, color: str) -> None:
    """Write each bar's value beside it, in ink — never in the series color."""
    for x, y in zip(xs, ys):
        if pd.isna(y):
            continue
        if horizontal:
            ax.annotate(fmt_number(y), (y, x), xytext=(4, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=9, color=color)
        else:
            ax.annotate(fmt_number(y), (x, y), xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9, color=color)


def fmt_number(v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    a = abs(v)
    if a >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if a >= 10_000:
        return f"{v / 1_000:.0f}k"
    if a >= 100 or float(v).is_integer():
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def as_numeric_x(pf: pd.DataFrame, cats: list) -> np.ndarray:
    pos = positions(cats)
    return pf["x"].map(pos).to_numpy(dtype=float)
