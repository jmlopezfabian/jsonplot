"""Stage 3: confront the spec with the DataFrame.

This is where the contract meets the real data. Anything that can fail because
of the contract fails here or in schema validation, never inside matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..spec.capabilities import CAPABILITIES, Capability
from ..spec.models import Bin, Channel, Spec
from ..theme import palettes
from ..transform import ops
from . import dtypes
from .errors import Code, SpecError, close_matches

#: Cardinality ceilings. Past these, the chart stops communicating anything.
#: The color one is not cosmetic: hues are assigned in fixed order and never
#: recycled, so the palette is the hard limit on distinguishable series.
MAX_COLOR = palettes.MAX_SERIES
MAX_FACET = 16
MAX_X_DISCRETE = 300

#: Aggregations whose result is a number whatever the source column is.
COUNTING = frozenset({"count", "nunique"})


@dataclass
class BoundChannel:
    """A channel already resolved against a concrete column."""

    role: str
    field: str | None
    type: str
    title: str
    aggregate: str | None = None
    bin: Bin | None = None
    time_unit: str | None = None
    scale: str | None = None
    n_unique: int | None = None
    dtype: str | None = None

    @property
    def is_discrete(self) -> bool:
        return self.type in ("nominal", "ordinal")

    @property
    def is_measure(self) -> bool:
        return self.aggregate is not None


@dataclass
class BoundSpec:
    """The spec and the data, married and verified."""

    spec: Spec
    frame: pd.DataFrame  # the df with filters already applied
    channels: dict[str, BoundChannel]
    capability: Capability
    needs_aggregation: bool = False
    source_columns: list[str] = field(default_factory=list)

    @property
    def viz_type(self) -> str:
        return self.spec.viz_type

    @property
    def style(self):
        return self.spec.style

    def get(self, role: str) -> BoundChannel | None:
        return self.channels.get(role)

    @property
    def group_roles(self) -> list[str]:
        """Channels that define groups: discrete and without their own aggregate."""
        return [r for r, ch in self.channels.items()
                if not ch.is_measure and r != "size" and ch.field is not None]

    @property
    def measure_roles(self) -> list[str]:
        return [r for r, ch in self.channels.items() if ch.is_measure]


# --------------------------------------------------------------------------


def bind(spec: Spec, df: pd.DataFrame) -> tuple[BoundSpec | None, list[SpecError]]:
    """Spec × DataFrame -> BoundSpec. Collects every error it finds."""
    errors: list[SpecError] = []
    cap = CAPABILITIES[spec.viz_type]
    columns = list(df.columns)

    _check_channel_set(spec, cap, errors)
    frame = _apply_filters(spec, df, columns, errors)

    channels: dict[str, BoundChannel] = {}
    for role, ch in spec.encoding.items():
        if role not in cap.channels:
            continue  # already reported as CHANNEL_NOT_SUPPORTED
        bound = _bind_channel(role, ch, frame, columns, cap, errors)
        if bound is not None:
            channels[role] = bound

    needs_agg = _check_aggregation(spec, cap, channels, frame, errors)
    _check_cardinality(channels, errors)

    if errors:
        return None, errors
    return BoundSpec(
        spec=spec, frame=frame, channels=channels, capability=cap,
        needs_aggregation=needs_agg, source_columns=columns,
    ), []


# --------------------------------------------------------------------------


def _check_channel_set(spec: Spec, cap: Capability, errors: list[SpecError]) -> None:
    present = {role for role, _ in spec.encoding.items()}
    for role in cap.required:
        if role not in present:
            errors.append(SpecError(
                Code.MISSING_CHANNEL, f"encoding.{role}",
                f"'{spec.viz_type}' needs the '{role}' channel",
                hint=f"'{spec.viz_type}' channels: required {list(cap.required)}, "
                     f"optional {list(cap.optional)}",
            ))
    for role in present - set(cap.channels):
        errors.append(SpecError(
            Code.CHANNEL_NOT_SUPPORTED, f"encoding.{role}",
            f"'{spec.viz_type}' does not support the '{role}' channel",
            hint=f"supported channels: {', '.join(cap.channels)}",
            did_you_mean=close_matches(role, cap.channels),
        ))


def _apply_filters(spec: Spec, df: pd.DataFrame, columns, errors) -> pd.DataFrame:
    """Filters run here rather than later because the duplicate, cardinality
    and empty-result checks have to see the rows that will actually be drawn."""
    usable = []
    for i, f in enumerate(spec.data.filters):
        if f.field not in columns:
            errors.append(_column_error(f.field, columns, f"data.filters[{i}].field"))
        else:
            usable.append(f)
    if not usable:
        return df
    try:
        out = ops.apply_filters(df, usable)
    except (TypeError, ValueError) as exc:
        errors.append(SpecError(Code.INVALID_VALUE, "data.filters",
                                f"could not apply the filter: {exc}"))
        return df
    if out.empty and not df.empty:
        worst = max(usable, key=lambda f: ops.rows_removed(df, f))
        errors.append(SpecError(
            Code.EMPTY_RESULT, "data.filters",
            "the filters leave zero rows",
            hint=f"the filter on '{worst.field}' ({worst.op}) removes "
                 f"{ops.rows_removed(df, worst)} of {len(df)} rows",
        ))
    return out


def _bind_channel(role, ch: Channel, frame, columns, cap, errors) -> BoundChannel | None:
    if ch.field is None:  # only valid with aggregate="count"
        return BoundChannel(role=role, field=None, type="quantitative",
                            title=ch.title or "count", aggregate="count")

    if ch.field not in columns:
        errors.append(_column_error(ch.field, columns, f"encoding.{role}.field"))
        return None

    series = frame[ch.field]
    inferred = dtypes.infer_type(series)

    # a channel's type describes what gets drawn, not the source column:
    # counting text produces numbers
    if ch.aggregate in COUNTING:
        ctype = "quantitative"
        if ch.type and ch.type != "quantitative":
            errors.append(SpecError(
                Code.TYPE_MISMATCH, f"encoding.{role}.type",
                f"{ch.aggregate!r} produces a number, not a {ch.type!r} channel",
                hint="drop 'type' to let it be inferred, or declare 'quantitative'",
            ))
            return None
    else:
        ctype = ch.type or inferred
        if ch.type and not dtypes.is_compatible(ch.type, series):
            errors.append(SpecError(
                Code.TYPE_MISMATCH, f"encoding.{role}.type",
                f"'{ch.field}' is {series.dtype}, it cannot be treated as {ch.type!r}",
                hint=f"valid types for that column: "
                     f"{', '.join(dtypes.allowed_types(series))}",
            ))
            return None

    if ch.bin is not None:
        ctype = "quantitative"
    if ch.time_unit is not None and inferred != "temporal":
        errors.append(SpecError(
            Code.TYPE_MISMATCH, f"encoding.{role}.time_unit",
            f"'{ch.field}' is not a temporal column ({series.dtype})",
            hint="convert it with pd.to_datetime before using time_unit",
        ))
        return None

    if not cap.accepts_type(role, ctype):
        allowed = cap.accepts.get(role, ())
        errors.append(SpecError(
            Code.TYPE_MISMATCH, f"encoding.{role}",
            f"'{cap_name(cap)}' does not accept a {ctype!r} '{role}' channel "
            f"(column '{ch.field}')",
            hint=f"'{role}' accepts: {', '.join(allowed)}",
        ))
        return None

    if ch.aggregate and not dtypes.aggregate_is_valid(ch.aggregate, series):
        errors.append(SpecError(
            Code.AGGREGATE_INVALID, f"encoding.{role}.aggregate",
            f"cannot apply {ch.aggregate!r} to '{ch.field}' ({series.dtype})",
            hint=f"valid aggregates for that column: "
                 f"{', '.join(dtypes.valid_aggregates(series))}",
        ))
        return None

    return BoundChannel(
        role=role, field=ch.field, type=ctype,
        title=ch.title or _default_title(ch),
        aggregate=ch.aggregate, bin=ch.bin, time_unit=ch.time_unit, scale=ch.scale,
        n_unique=int(series.nunique(dropna=True)), dtype=str(series.dtype),
    )


def _check_aggregation(spec, cap, channels, frame, errors) -> bool:
    """Does this need aggregating, and can it be done?

    If the chart type aggregates and rows repeat for the same combination of
    categories, drawing without aggregating produces a silently wrong figure
    (overlapping bars). That is an error, not a warning.
    """
    if not cap.aggregates or cap.measure not in channels:
        return any(ch.is_measure for ch in channels.values())

    measure = channels[cap.measure]
    if measure.aggregate:
        return True

    group_fields = [ch.field for r, ch in channels.items()
                    if r != cap.measure and ch.field and r != "size"]
    if not group_fields or frame.empty:
        return False
    if not frame.duplicated(subset=group_fields).any():
        return False

    dups = int(frame.duplicated(subset=group_fields).sum())
    series = frame[measure.field] if measure.field in frame else None
    valid = dtypes.valid_aggregates(series) if series is not None else ("sum", "mean", "count")
    errors.append(SpecError(
        Code.AGGREGATE_REQUIRED, f"encoding.{cap.measure}.aggregate",
        f"{dups} rows repeat for the same combination of {group_fields}; "
        f"without 'aggregate' the marks would overlap",
        hint=f"add an aggregate; for that column these work: {', '.join(valid)}",
    ))
    return True


def _check_cardinality(channels, errors) -> None:
    limits = {"color": MAX_COLOR, "facet": MAX_FACET}
    for role, cap_n in limits.items():
        ch = channels.get(role)
        # a quantitative color goes to a continuous ramp: it is not series
        if ch and ch.is_discrete and ch.n_unique and ch.n_unique > cap_n:
            errors.append(SpecError(
                Code.CARDINALITY_TOO_HIGH, f"encoding.{role}.field",
                f"'{ch.field}' has {ch.n_unique} categories, more than the "
                f"{cap_n} that '{role}' can tell apart",
                hint=f"fold the tail into 'Other', filter with data.filters, "
                     f"trim with data.limit, or split with encoding.facet",
            ))
    x = channels.get("x")
    if x and x.is_discrete and x.n_unique and x.n_unique > MAX_X_DISCRETE:
        errors.append(SpecError(
            Code.CARDINALITY_TOO_HIGH, "encoding.x.field",
            f"'{x.field}' has {x.n_unique} categories on the x axis",
            hint="use data.limit to keep the first N, or group with time_unit/bin",
        ))


def _column_error(name: str, columns, path: str) -> SpecError:
    return SpecError(
        Code.COLUMN_NOT_FOUND, path,
        f"column {name!r} is not in the DataFrame",
        hint="use one of the columns returned by describe_dataframe(df)",
        did_you_mean=close_matches(name, columns),
    )


def _default_title(ch: Channel) -> str:
    base = ch.field or "count"
    if ch.aggregate == "count":
        return "count"
    if ch.aggregate:
        return f"{ch.aggregate}({base})"
    return base


def cap_name(cap: Capability) -> str:
    for name, c in CAPABILITIES.items():
        if c is cap:
            return name
    return "?"
