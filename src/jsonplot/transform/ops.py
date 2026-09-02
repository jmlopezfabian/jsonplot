"""Data operations. Each one is a pure DataFrame-to-DataFrame (or
Series-to-Series) function with no knowledge of matplotlib."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..spec.models import Bin, Filter

_PERIOD = {"day": "D", "week": "W", "month": "M", "quarter": "Q", "year": "Y"}

_AGG_FUNCS = {
    "sum": "sum", "mean": "mean", "median": "median",
    "min": "min", "max": "max", "std": "std", "nunique": "nunique",
}


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------


def apply_filters(df: pd.DataFrame, filters: list[Filter]) -> pd.DataFrame:
    if not filters:
        return df
    mask = pd.Series(True, index=df.index)
    for f in filters:
        mask &= filter_mask(df, f)
    return df[mask]


def filter_mask(df: pd.DataFrame, f: Filter) -> pd.Series:
    s = df[f.field]
    v = f.value
    match f.op:
        case "eq":      return s == v
        case "ne":      return s != v
        case "gt":      return s > _coerce(s, v)
        case "gte":     return s >= _coerce(s, v)
        case "lt":      return s < _coerce(s, v)
        case "lte":     return s <= _coerce(s, v)
        case "in":      return s.isin(v)
        case "not_in":  return ~s.isin(v)
        case "between": return s.between(_coerce(s, v[0]), _coerce(s, v[1]))
        case "contains":return s.astype("string").str.contains(str(v), case=False, na=False)
        case "isnull":  return s.isna()
        case "notnull": return s.notna()
    raise ValueError(f"filter operator not implemented: {f.op}")


def _coerce(s: pd.Series, v):
    """Lets a date column be compared against the string '2024-01-01'."""
    if pd.api.types.is_datetime64_any_dtype(s) and isinstance(v, str):
        return pd.Timestamp(v)
    return v


def rows_removed(df: pd.DataFrame, f: Filter) -> int:
    """How many rows a filter drops on its own. For the EMPTY_RESULT hint."""
    return int((~filter_mask(df, f)).sum())


# --------------------------------------------------------------------------
# Derivation
# --------------------------------------------------------------------------


def apply_time_unit(s: pd.Series, unit: str) -> pd.Series:
    """Truncate a temporal series to the start of its period."""
    s = pd.to_datetime(s)
    if unit == "day":
        return s.dt.normalize()
    return s.dt.to_period(_PERIOD[unit]).dt.to_timestamp()


def apply_bin(s: pd.Series, spec: Bin) -> pd.Series:
    """Discretize into intervals and return each interval's midpoint.

    Returning the center (rather than the interval label) keeps the axis
    quantitative, which is what every renderer expects.
    """
    if spec.step:
        lo = np.floor(s.min() / spec.step) * spec.step
        hi = np.ceil(s.max() / spec.step) * spec.step + spec.step
        edges = np.arange(lo, hi, spec.step)
    else:
        edges = np.histogram_bin_edges(s.dropna(), bins=spec.maxbins)
    cut = pd.cut(s, bins=edges, include_lowest=True)
    return cut.map(lambda iv: iv.mid if isinstance(iv, pd.Interval) else np.nan).astype(float)


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------


def aggregate(
    df: pd.DataFrame,
    group_cols: list[str],
    measures: dict[str, str],
) -> pd.DataFrame:
    """Group by `group_cols` and apply `{column: aggregation}`.

    `count` resolves to the group size, so it works even when the channel
    declares no field.
    """
    if not group_cols:
        row = {col: _apply_one(df, col, agg) for col, agg in measures.items()}
        return pd.DataFrame([row])

    grouped = df.groupby(group_cols, dropna=False, observed=True, sort=False)
    parts = []
    for col, agg in measures.items():
        if agg == "count":
            part = grouped.size().rename(col)
        else:
            part = grouped[col].agg(_AGG_FUNCS[agg]).rename(col)
        parts.append(part)
    return pd.concat(parts, axis=1).reset_index()


def _apply_one(df: pd.DataFrame, col: str, agg: str):
    if agg == "count":
        return len(df)
    return getattr(df[col], _AGG_FUNCS[agg])()


# --------------------------------------------------------------------------
# Ordering and trimming
# --------------------------------------------------------------------------


def sort_frame(df: pd.DataFrame, by: str, order: str) -> pd.DataFrame:
    if by not in df.columns:
        return df
    return df.sort_values(by, ascending=(order == "asc"), kind="stable")


def limit_categories(df: pd.DataFrame, key: str, n: int) -> pd.DataFrame:
    """Keep the first N categories of `key` in their current order.

    It runs after sorting, so `sort: "-y"` + `limit: 10` gives the top 10 by
    value and `sort: "x"` + `limit: 10` gives the first ten alphabetically.
    It picks categories rather than rows: trimming rows would split groups when
    a category carries several series.
    """
    if key not in df.columns:
        return df.head(n)
    keep = pd.Index(df[key].drop_duplicates())[:n]
    return df[df[key].isin(keep)]
