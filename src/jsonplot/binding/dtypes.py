"""Mapping between pandas dtypes and channel types."""

from __future__ import annotations

import pandas as pd
from pandas.api import types as pdt

from ..spec.capabilities import NUMERIC_ONLY

QUANTITATIVE = "quantitative"
NOMINAL = "nominal"
ORDINAL = "ordinal"
TEMPORAL = "temporal"


def infer_type(s: pd.Series) -> str:
    """The channel type a column takes when the contract doesn't say."""
    if pdt.is_datetime64_any_dtype(s) or isinstance(s.dtype, pd.PeriodDtype):
        return TEMPORAL
    if isinstance(s.dtype, pd.CategoricalDtype):
        return ORDINAL if s.dtype.ordered else NOMINAL
    if pdt.is_bool_dtype(s):
        return NOMINAL
    if pdt.is_numeric_dtype(s):
        return QUANTITATIVE
    return NOMINAL


def allowed_types(s: pd.Series) -> tuple[str, ...]:
    """The channel types a column can carry.

    A number can always be treated as a category (the year 2024 as a label),
    but text can never be treated as a quantity.
    """
    if pdt.is_datetime64_any_dtype(s) or isinstance(s.dtype, pd.PeriodDtype):
        return (TEMPORAL, ORDINAL, NOMINAL)
    if pdt.is_numeric_dtype(s) and not pdt.is_bool_dtype(s):
        return (QUANTITATIVE, ORDINAL, NOMINAL)
    return (NOMINAL, ORDINAL)


def is_compatible(channel_type: str, s: pd.Series) -> bool:
    return channel_type in allowed_types(s)


def aggregate_is_valid(agg: str, s: pd.Series) -> bool:
    if agg in ("count", "nunique"):
        return True
    if agg in NUMERIC_ONLY:
        return pdt.is_numeric_dtype(s) and not pdt.is_bool_dtype(s)
    return True  # min / max work on anything orderable


def valid_aggregates(s: pd.Series) -> tuple[str, ...]:
    base = ("count", "nunique", "min", "max")
    if pdt.is_numeric_dtype(s) and not pdt.is_bool_dtype(s):
        return ("sum", "mean", "median", "std") + base
    return base


def describe_column(s: pd.Series, examples: int = 3) -> dict:
    """A compact column summary, sized to fit in a prompt."""
    out: dict = {
        "dtype": str(s.dtype),
        "inferred_type": infer_type(s),
        "n_unique": int(s.nunique(dropna=True)),
        "n_null": int(s.isna().sum()),
    }
    kind = out["inferred_type"]
    if kind == QUANTITATIVE and len(s.dropna()):
        out["min"] = _scalar(s.min())
        out["max"] = _scalar(s.max())
    elif kind == TEMPORAL and len(s.dropna()):
        out["min"] = str(s.min())
        out["max"] = str(s.max())
    else:
        vals = s.dropna().unique()[:examples]
        out["examples"] = [_scalar(v) for v in vals]
    return out


def _scalar(v):
    """Turn numpy/pandas scalars into JSON-serializable types."""
    if hasattr(v, "item"):
        try:
            return v.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)
