"""Distributions: histogram and box plot."""

from __future__ import annotations

import matplotlib
import numpy as np

from ...theme import themes
from ..base import RenderContext, Renderer
from ..registry import register
from . import _shared as sh


@register("hist", "matplotlib")
class HistRenderer(Renderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        ch = ctx.channel("x")
        bins = ch.bin.maxbins if ch and ch.bin else "auto"
        values = [part["x"].to_numpy() for _, part in ctx.groups()]
        labels = [str(cat) if cat is not None else None for cat, _ in ctx.groups()]
        colors = [ctx.color_for(c) if c is not None else ctx.base_color()
                  for c in [cat for cat, _ in ctx.groups()]]

        edges = np.histogram_bin_edges(np.concatenate(values), bins=bins)
        ax.hist(values, bins=edges, color=colors, label=labels, zorder=3,
                histtype="bar" if len(values) == 1 else "barstacked",
                edgecolor=ax.get_facecolor(), linewidth=1.0)
        ax.set_ylabel(ctx.style.y_label or "frequency")


@register("box", "matplotlib")
class BoxRenderer(Renderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        horizontal = ctx.style.orientation == "horizontal"
        if "x" in ctx.pf.columns:
            cats = sh.categories(ctx.pf, "x")
            data = [ctx.pf.loc[ctx.pf["x"] == c, "y"].dropna().to_numpy() for c in cats]
            labels = sh.tick_labels(cats, ctx.channel("x"))
        else:
            data, labels = [ctx.pf["y"].dropna().to_numpy()], [ctx.channel("y").title]

        color = ctx.base_color()
        bp = ax.boxplot(
            data, tick_labels=labels, patch_artist=True,
            **_orientation(horizontal),
            widths=0.55, zorder=3,
            medianprops={"color": themes.INK, "linewidth": 1.6},
            whiskerprops={"color": themes.INK_SOFT, "linewidth": 1.0},
            capprops={"color": themes.INK_SOFT, "linewidth": 1.0},
            flierprops={"marker": "o", "markersize": 3.5, "alpha": 0.5,
                        "markerfacecolor": themes.INK_SOFT, "markeredgecolor": "none"},
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.45)
            patch.set_edgecolor(color)
            patch.set_linewidth(1.2)
        if not horizontal and (
            len(labels) > 8 or max((len(s) for s in labels), default=0) > 8
        ):
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(30)
                lbl.set_ha("right")
                lbl.set_rotation_mode("anchor")


def _orientation(horizontal: bool) -> dict:
    """matplotlib 3.11 replaced `vert` with `orientation`."""
    if tuple(int(p) for p in matplotlib.__version__.split(".")[:2]) >= (3, 11):
        return {"orientation": "horizontal" if horizontal else "vertical"}
    return {"vert": not horizontal}
