"""Which channels each chart type accepts.

Declared in one place because it feeds validation, error messages, and the
documentation alike. Adding a viz_type starts with adding a row here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

QUANT = ("quantitative",)
CATEG = ("nominal", "ordinal")
DISCRETE = ("nominal", "ordinal", "temporal")
ANY = ("quantitative", "nominal", "ordinal", "temporal")


@dataclass(frozen=True)
class Capability:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    #: Types accepted per channel; unlisted channels accept anything.
    accepts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: When True, repeated rows on the discrete axis require an `aggregate`.
    aggregates: bool = False
    #: The role whose value gets aggregated (the measure).
    measure: str | None = None
    description: str = ""

    @property
    def channels(self) -> tuple[str, ...]:
        return self.required + self.optional

    def accepts_type(self, role: str, channel_type: str) -> bool:
        allowed = self.accepts.get(role)
        return allowed is None or channel_type in allowed


CAPABILITIES: dict[str, Capability] = {
    "bar": Capability(
        required=("x", "y"),
        optional=("color", "facet"),
        accepts={"x": DISCRETE + QUANT, "y": QUANT, "color": DISCRETE, "facet": DISCRETE},
        aggregates=True,
        measure="y",
        description="Grouped or stacked bars over a discrete axis.",
    ),
    "line": Capability(
        required=("x", "y"),
        optional=("color", "style", "facet"),
        accepts={"y": QUANT, "color": DISCRETE, "style": DISCRETE, "facet": DISCRETE},
        aggregates=True,
        measure="y",
        description="A continuous series; one line per color category.",
    ),
    "area": Capability(
        required=("x", "y"),
        optional=("color", "facet"),
        accepts={"y": QUANT, "color": DISCRETE, "facet": DISCRETE},
        aggregates=True,
        measure="y",
        description="Like line, filled below the curve; supports stacking.",
    ),
    "scatter": Capability(
        required=("x", "y"),
        optional=("color", "size", "style", "facet"),
        accepts={"x": QUANT + ("temporal",), "y": QUANT, "size": QUANT,
                 "color": ANY, "style": DISCRETE, "facet": DISCRETE},
        description="One mark per row; no implicit aggregation.",
    ),
    "hist": Capability(
        required=("x",),
        optional=("color", "facet"),
        accepts={"x": QUANT + ("temporal",), "color": DISCRETE, "facet": DISCRETE},
        description="Distribution of a quantitative field.",
    ),
    "box": Capability(
        required=("y",),
        optional=("x", "color", "facet"),
        accepts={"x": CATEG, "y": QUANT, "color": DISCRETE, "facet": DISCRETE},
        description="Five-number summary per category.",
    ),
    "violin": Capability(
        required=("y",),
        optional=("x", "color", "facet"),
        accepts={"x": CATEG, "y": QUANT, "color": DISCRETE, "facet": DISCRETE},
        description="Density per category. Requires the seaborn backend.",
    ),
}

#: Aggregations that only make sense over numbers.
NUMERIC_ONLY = frozenset({"sum", "mean", "median", "std"})
