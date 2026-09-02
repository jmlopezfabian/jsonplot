"""Lines and areas."""

from __future__ import annotations

import numpy as np

from ..base import RenderContext, Renderer
from ..registry import register
from . import _shared as sh

DASHES = ("-", "--", "-.", ":")


@register("line", "matplotlib")
class LineRenderer(Renderer):
    fill = False

    def draw(self, ax, ctx: RenderContext) -> None:
        cats = sh.categories(ctx.pf, "x") if self.x_is_categorical(ctx) else None
        styles = sh.categories(ctx.pf, "style")

        for cat, part in ctx.groups():
            part = part.sort_values("x", kind="stable")
            color = ctx.color_for(cat) if cat is not None else ctx.base_color()
            for dash_i, sub in _by_style(part, styles):
                xs = _xs(sub, cats)
                ys = sub["y"].to_numpy(dtype=float)
                label = _label(cat, sub, styles)
                ax.plot(xs, ys, color=color, linestyle=DASHES[dash_i % len(DASHES)],
                        label=label, zorder=3, solid_capstyle="round")
                if self.fill:
                    ax.fill_between(xs, ys, color=color, alpha=0.18, zorder=2,
                                    linewidth=0)

        if cats is not None:
            ax.set_xticks(np.arange(len(cats)), sh.tick_labels(cats, ctx.channel("x")))


@register("area", "matplotlib")
class AreaRenderer(LineRenderer):
    fill = True

    def draw(self, ax, ctx: RenderContext) -> None:
        if ctx.style.stacked and ctx.has_color:
            self._stacked(ax, ctx)
        else:
            super().draw(ax, ctx)

    def _stacked(self, ax, ctx: RenderContext) -> None:
        xs_index = sh.categories(ctx.pf, "x")
        base = np.zeros(len(xs_index))
        for cat, part in ctx.groups():
            ys = (part.set_index("x")["y"].reindex(xs_index)
                      .fillna(0).to_numpy(dtype=float))
            color = ctx.color_for(cat)
            ax.fill_between(xs_index, base, base + ys, color=color, alpha=0.9,
                            label=str(cat), zorder=3, linewidth=0)
            base = base + ys


def _by_style(part, styles):
    if not styles:
        yield 0, part
        return
    for i, s in enumerate(styles):
        sub = part[part["style"] == s]
        if len(sub):
            yield i, sub


def _label(cat, sub, styles):
    if cat is None and not styles:
        return None
    bits = [str(cat)] if cat is not None else []
    if styles:
        bits.append(str(sub["style"].iloc[0]))
    return " · ".join(bits)


def _xs(sub, cats):
    if cats is None:
        return sub["x"].to_numpy()
    return sub["x"].map(sh.positions(cats)).to_numpy(dtype=float)
