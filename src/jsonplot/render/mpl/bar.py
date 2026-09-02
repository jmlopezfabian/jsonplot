"""Bars: grouped, stacked and horizontal."""

from __future__ import annotations

import numpy as np

from ...theme import themes
from ..base import RenderContext, Renderer
from ..registry import register
from . import _shared as sh


@register("bar", "matplotlib")
class BarRenderer(Renderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        pf = ctx.pf
        cats = sh.categories(pf, "x")
        pos = sh.positions(cats)
        horizontal = ctx.style.orientation == "horizontal"

        if ctx.style.stacked and ctx.has_color:
            self._stacked(ax, ctx, cats, pos, horizontal)
        else:
            self._grouped(ax, ctx, cats, pos, horizontal)

        ticks = np.arange(len(cats))
        labels = sh.tick_labels(cats, ctx.channel("x"))
        if horizontal:
            ax.set_yticks(ticks, labels)
            ax.invert_yaxis()  # first category on top
        else:
            ax.set_xticks(ticks, labels)
            _maybe_rotate(ax, labels)

    # ----------------------------------------------------------------

    def _grouped(self, ax, ctx, cats, pos, horizontal) -> None:
        groups = list(ctx.groups())
        slots = sh.bar_slots(len(groups))
        for (cat, part), (offset, width) in zip(groups, slots):
            xs = part["x"].map(pos).to_numpy(dtype=float) + offset
            ys = part["y"].to_numpy(dtype=float)
            color = ctx.color_for(cat) if cat is not None else ctx.base_color()
            label = str(cat) if cat is not None else None
            if horizontal:
                ax.barh(xs, ys, height=width, color=color, label=label, zorder=3)
            else:
                ax.bar(xs, ys, width=width, color=color, label=label, zorder=3)
            if ctx.style.annotate:
                sh.annotate_bars(ax, xs, ys, horizontal, themes.INK_SOFT)

    def _stacked(self, ax, ctx, cats, pos, horizontal) -> None:
        base = np.zeros(len(cats))
        for cat, part in ctx.groups():
            ys = (part.set_index("x")["y"]
                      .reindex(cats).fillna(0).to_numpy(dtype=float))
            xs = np.arange(len(cats))
            color = ctx.color_for(cat)
            # a sliver of surface between segments: separates them without
            # drawing a border
            edge = {"edgecolor": ax.get_facecolor(), "linewidth": 1.5}
            if horizontal:
                ax.barh(xs, ys, left=base, height=sh.GROUP_WIDTH, color=color,
                        label=str(cat), zorder=3, **edge)
            else:
                ax.bar(xs, ys, bottom=base, width=sh.GROUP_WIDTH, color=color,
                       label=str(cat), zorder=3, **edge)
            base = base + ys


def _maybe_rotate(ax, labels) -> None:
    """Rotate the tick labels only when they genuinely do not fit."""
    if len(labels) > 8 or max((len(s) for s in labels), default=0) > 8:
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(30)
            lbl.set_ha("right")
            lbl.set_rotation_mode("anchor")
