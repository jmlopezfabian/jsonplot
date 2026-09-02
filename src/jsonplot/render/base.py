"""The interface that crosses the core's boundary.

A renderer receives the plot frame — columns already named by role — and a set
of axes. It never sees the original DataFrame, the raw contract, or the
filters: all of that was resolved earlier. That is why a new backend does not
force a single change to the core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

from ..binding.binder import BoundChannel, BoundSpec
from ..theme import palettes


@dataclass
class RenderContext:
    """Everything a renderer needs to know, already resolved."""

    bound: BoundSpec
    pf: pd.DataFrame
    mode: str = "light"
    series: list = field(default_factory=list)
    colors: dict = field(default_factory=dict)

    @classmethod
    def build(cls, bound: BoundSpec, pf: pd.DataFrame, mode: str) -> RenderContext:
        series, colors = [], {}
        color_ch = bound.get("color")
        # a quantitative color is resolved by the renderer with a continuous
        # ramp; only categorical slots are handed out here
        if "color" in pf.columns and color_ch is not None and color_ch.is_discrete:
            # order of appearance in the plot frame: color follows the entity,
            # not its rank within this particular chart
            series = list(pd.Index(pf["color"].drop_duplicates()))
            hexes = palettes.series_colors(bound.style.palette, len(series), mode)
            colors = dict(zip(series, hexes))
        return cls(bound=bound, pf=pf, mode=mode, series=series, colors=colors)

    def subset(self, pf: pd.DataFrame) -> RenderContext:
        """The same context over a different slice of data (one facet).

        Keeps `colors` so a category holds the same color across every facet,
        even one it does not appear in.
        """
        return RenderContext(self.bound, pf, self.mode, self.series, self.colors)

    # -- convenience accessors ---------------------------------------------

    @property
    def has_color(self) -> bool:
        return bool(self.series)

    @property
    def style(self):
        return self.bound.style

    def channel(self, role: str) -> BoundChannel | None:
        return self.bound.get(role)

    def color_for(self, category) -> str:
        return self.colors.get(category, palettes.get(self.style.palette).colors(self.mode)[0])

    def base_color(self) -> str:
        return palettes.get(self.style.palette).colors(self.mode)[0]

    def groups(self):
        """(category, sub-frame) per color series; a single one if no color."""
        if not self.has_color:
            yield None, self.pf
            return
        for cat in self.series:
            part = self.pf[self.pf["color"] == cat]
            if len(part):
                yield cat, part


class Renderer(ABC):
    """Draws one chart type onto a set of axes."""

    viz_type: str = ""
    backend: str = ""

    @abstractmethod
    def draw(self, ax, ctx: RenderContext) -> None:
        """Paint the marks. Titles, legend and grid are not its business: the
        driver handles those, identically for every type."""

    def x_is_categorical(self, ctx: RenderContext) -> bool:
        ch = ctx.channel("x")
        return bool(ch and ch.is_discrete)
