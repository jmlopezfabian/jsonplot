"""The canonical contract.

This is the single source of truth for the shape of a spec: runtime validation,
Python types, and the JSON Schema the agent consumes all come from here. If
something isn't described in this file, it isn't part of the contract.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

ChannelType = Literal["quantitative", "nominal", "ordinal", "temporal"]
Aggregate = Literal["sum", "mean", "median", "min", "max", "count", "nunique", "std"]
TimeUnit = Literal["day", "week", "month", "quarter", "year"]
ScaleType = Literal["linear", "log", "symlog"]
VizType = Literal["bar", "line", "area", "scatter", "hist", "box", "violin"]
Backend = Literal["matplotlib", "seaborn"]
FilterOp = Literal[
    "eq", "ne", "gt", "gte", "lt", "lte",
    "in", "not_in", "between", "contains", "isnull", "notnull",
]

#: Channel roles, in the order they are resolved.
CHANNELS = ("x", "y", "color", "size", "style", "facet")


class _Strict(BaseModel):
    """Shared base: rejects unknown fields so the agent gets a located error
    instead of having its key silently ignored."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------
# Channels
# --------------------------------------------------------------------------


class Bin(_Strict):
    """Discretizes a quantitative field. `bin: true` means maxbins=10."""

    maxbins: int = Field(default=10, ge=2, le=200)
    step: float | None = Field(default=None, gt=0)

    @model_validator(mode="before")
    @classmethod
    def _from_shorthand(cls, v: Any) -> Any:
        if v is True:
            return {}
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return {"maxbins": int(v)}
        return v


class Channel(_Strict):
    """A DataFrame field mapped onto a visual channel."""

    field: str | None = Field(
        default=None,
        validation_alias=AliasChoices("field", "column"),
        description="DataFrame column name. Optional only with aggregate=count.",
    )
    type: ChannelType | None = Field(
        default=None,
        description="Scale type. Inferred from the column dtype when omitted.",
    )
    aggregate: Aggregate | None = None
    bin: Bin | None = None
    time_unit: TimeUnit | None = None
    scale: ScaleType | None = None
    title: str | None = Field(default=None, description="Axis or legend label.")

    @model_validator(mode="before")
    @classmethod
    def _from_shorthand(cls, v: Any) -> Any:
        # "x": "date" is sugar for {"field": "date"}
        if isinstance(v, str):
            return {"field": v}
        if isinstance(v, dict) and v.get("bin") is False:
            v = {**v, "bin": None}
        return v

    @model_validator(mode="after")
    def _needs_field(self) -> Channel:
        if self.field is None and self.aggregate != "count":
            raise ValueError("a channel needs 'field' unless aggregate='count'")
        return self


class ColorChannel(Channel):
    scheme: str | None = Field(
        default=None, description="Explicit palette; defaults to the theme's."
    )


class SizeChannel(Channel):
    range: tuple[float, float] = Field(
        default=(20.0, 320.0), description="Marker area range, in points²."
    )


class StyleChannel(Channel):
    """A second categorical dimension: dash pattern or marker shape."""


class FacetChannel(Channel):
    columns: int = Field(default=0, ge=0, description="0 = automatic grid.")
    share_y: bool = True
    share_x: bool = True


class Encoding(_Strict):
    x: Channel | None = None
    y: Channel | None = None
    color: ColorChannel | None = None
    size: SizeChannel | None = None
    style: StyleChannel | None = None
    facet: FacetChannel | None = None

    def items(self) -> list[tuple[str, Channel]]:
        """The channels that are present, in resolution order."""
        return [(r, ch) for r in CHANNELS if (ch := getattr(self, r)) is not None]


# --------------------------------------------------------------------------
# Data operations
# --------------------------------------------------------------------------


class Filter(_Strict):
    field: str
    op: FilterOp
    value: Any = None

    @model_validator(mode="after")
    def _value_required(self) -> Filter:
        if self.op in ("isnull", "notnull"):
            return self
        if self.value is None:
            raise ValueError(f"operator '{self.op}' needs 'value'")
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"operator '{self.op}' needs a list in 'value'")
        if self.op == "between" and (
            not isinstance(self.value, list) or len(self.value) != 2
        ):
            raise ValueError("operator 'between' needs [min, max] in 'value'")
        return self


class Sort(_Strict):
    by: str = Field(
        default="x", description="'x', 'y', or a DataFrame column name."
    )
    order: Literal["asc", "desc"] = "asc"

    @model_validator(mode="before")
    @classmethod
    def _from_shorthand(cls, v: Any) -> Any:
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("-"):
                return {"by": s[1:], "order": "desc"}
            return {"by": s}
        return v


class DataOps(_Strict):
    filters: list[Filter] = Field(default_factory=list)
    sort: Sort | None = None
    limit: int | None = Field(
        default=None, gt=0, description="Keeps the first N categories after sorting."
    )


# --------------------------------------------------------------------------
# Presentation and output
# --------------------------------------------------------------------------


class Style(_Strict):
    title: str | None = None
    subtitle: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    legend_title: str | None = None
    palette: str = "default"
    theme: str = "clean"
    figsize: tuple[float, float] = (10.0, 6.0)
    grid: Literal["none", "x", "y", "both"] = "y"
    legend: Literal["auto", "right", "top", "none"] = "auto"
    stacked: bool = False
    orientation: Literal["vertical", "horizontal"] = "vertical"
    annotate: bool = Field(default=False, description="Write the value on each mark.")


class Output(_Strict):
    format: Literal["figure", "png", "svg", "base64"] = "figure"
    dpi: int = Field(default=150, ge=36, le=600)
    path: str | None = None
    transparent: bool = False


# --------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------


class Spec(_Strict):
    """A complete, normalized visualization contract."""

    version: Literal["1.0"] = "1.0"
    viz_type: VizType
    backend: Backend = "matplotlib"
    data: DataOps = Field(default_factory=DataOps)
    encoding: Encoding
    style: Style = Field(default_factory=Style)
    output: Output = Field(default_factory=Output)


SpecInput = Annotated[Spec, "already-normalized canonical spec"]
