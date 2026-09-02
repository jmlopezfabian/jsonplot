"""Stage 4: build the plot frame.

The plot frame is a DataFrame whose columns are named after channels — "x",
"y", "color", "facet"… — rather than after the user's columns. That translation
is deliberate: past this point no renderer needs to know where a value came
from, so drawing stops depending on the user's data at all. It is also what
lets the core's tests assert on data instead of on pixels.
"""

from __future__ import annotations

import pandas as pd

from ..binding.binder import BoundChannel, BoundSpec
from . import ops

#: Fixed order of application. Changing it changes results, so it lives here
#: and only here.
STAGES = ("filter", "derive", "aggregate", "sort", "limit")


def build_plot_frame(bound: BoundSpec) -> pd.DataFrame:
    """BoundSpec -> DataFrame ready to draw (filters already applied in bind)."""
    pf = _project(bound)
    pf = _derive(pf, bound)
    pf = _aggregate(pf, bound)
    pf = _sort(pf, bound)
    pf = _limit(pf, bound)
    return pf.reset_index(drop=True)


# --------------------------------------------------------------------------


def _project(bound: BoundSpec) -> pd.DataFrame:
    """One column per channel, renamed to the role."""
    cols: dict[str, pd.Series] = {}
    for role, ch in bound.channels.items():
        if ch.field is not None:
            cols[role] = bound.frame[ch.field].copy()
    if not cols:
        return pd.DataFrame(index=bound.frame.index)
    return pd.DataFrame(cols, index=bound.frame.index)


def _derive(pf: pd.DataFrame, bound: BoundSpec) -> pd.DataFrame:
    for role, ch in bound.channels.items():
        if role not in pf.columns:
            continue
        if ch.time_unit:
            pf[role] = ops.apply_time_unit(pf[role], ch.time_unit)
        if ch.bin is not None:
            pf[role] = ops.apply_bin(pf[role], ch.bin)
    return pf


def _aggregate(pf: pd.DataFrame, bound: BoundSpec) -> pd.DataFrame:
    if not bound.needs_aggregation:
        return _drop_incomplete(pf, bound)

    measures = {r: ch.aggregate for r, ch in bound.channels.items() if ch.is_measure}
    groups = [r for r in bound.group_roles if r in pf.columns]
    for role in measures:
        if role not in pf.columns:
            pf[role] = pd.NA  # count channel with no field: the groupby fills it
    pf = _drop_incomplete(pf, bound, skip=set(measures))
    out = ops.aggregate(pf, groups, measures)
    return out


def _drop_incomplete(pf: pd.DataFrame, bound: BoundSpec, skip: set[str] = frozenset()):
    """Drop rows with no value in a required channel.

    A NaN on an axis is not data: matplotlib would draw it as a silent gap.
    """
    required = [r for r in bound.capability.required if r in pf.columns and r not in skip]
    return pf.dropna(subset=required) if required else pf


def _sort(pf: pd.DataFrame, bound: BoundSpec) -> pd.DataFrame:
    sort = bound.spec.data.sort
    if sort is None:
        return _default_sort(pf, bound)
    key = _resolve_key(sort.by, bound, pf)
    if key is None:
        return pf
    return ops.sort_frame(pf, key, sort.order)


def _default_sort(pf: pd.DataFrame, bound: BoundSpec) -> pd.DataFrame:
    """With no explicit `sort`: chronological or alphabetical on the x axis.

    A time series drawn in row-arrival order is a scribble, so the default
    order cannot be "none".
    """
    x = bound.get("x")
    if x is None or "x" not in pf.columns:
        return pf
    if isinstance(pf["x"].dtype, pd.CategoricalDtype) and pf["x"].dtype.ordered:
        return pf.sort_values("x", kind="stable")
    return ops.sort_frame(pf, "x", "asc")


def _resolve_key(by: str, bound: BoundSpec, pf: pd.DataFrame) -> str | None:
    if by in pf.columns:
        return by
    for role, ch in bound.channels.items():  # allow sorting by source column name
        if ch.field == by and role in pf.columns:
            return role
    return None


def _limit(pf: pd.DataFrame, bound: BoundSpec) -> pd.DataFrame:
    n = bound.spec.data.limit
    if not n:
        return pf
    key = "x" if "x" in pf.columns else next(iter(pf.columns), None)
    return pf if key is None else ops.limit_categories(pf, key, n)


def channel_titles(bound: BoundSpec) -> dict[str, str]:
    """Each channel's label, aggregation included."""
    return {role: ch.title for role, ch in bound.channels.items()}


def categories(pf: pd.DataFrame, role: str) -> list:
    """A role's categories, in the order they appear in the plot frame."""
    if role not in pf.columns:
        return []
    return list(pd.Index(pf[role].drop_duplicates()))


def channel(bound: BoundSpec, role: str) -> BoundChannel | None:
    return bound.get(role)
