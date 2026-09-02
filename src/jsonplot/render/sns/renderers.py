"""seaborn backend.

It gets exactly the same plot frame as the matplotlib backend — columns "x",
"y", "color" — so these renderers are thin by construction: all the data logic
already happened before the boundary. If one of them needed to filter or
aggregate something, the abstraction would be in the wrong place.
"""

from __future__ import annotations

import seaborn as sns

from ..base import RenderContext, Renderer
from ..registry import register
from ..mpl import _shared as sh


class _SnsRenderer(Renderer):
    def common(self, ctx: RenderContext) -> dict:
        # seaborn's legend is left on: it labels the artists, and the driver
        # removes the box to draw its own
        kw: dict = {"data": ctx.pf}
        if ctx.has_color:
            kw["hue"] = "color"
            kw["hue_order"] = ctx.series
            kw["palette"] = ctx.colors
        else:
            kw["color"] = ctx.base_color()
        return kw


@register("bar", "seaborn")
class SnsBar(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        horizontal = ctx.style.orientation == "horizontal"
        axes = {"y": "x", "x": "y"} if horizontal else {"x": "x", "y": "y"}
        # saturation=1: the palette colors are already validated, seaborn must
        # not desaturate them on its own
        sns.barplot(ax=ax, errorbar=None, saturation=1, **axes, **self.common(ctx))
        _relabel(ax, ctx, horizontal)


@register("line", "seaborn")
class SnsLine(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        kw = self.common(ctx)
        if "style" in ctx.pf.columns:
            kw["style"] = "style"
        sns.lineplot(ax=ax, x="x", y="y", errorbar=None, **kw)


@register("scatter", "seaborn")
class SnsScatter(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        kw = self.common(ctx)
        if "style" in ctx.pf.columns:
            kw["style"] = "style"
        if "size" in ctx.pf.columns:
            kw["size"] = "size"
            kw["sizes"] = tuple(ctx.bound.spec.encoding.size.range)
        sns.scatterplot(ax=ax, x="x", y="y", **kw)


@register("hist", "seaborn")
class SnsHist(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        ch = ctx.channel("x")
        kw = self.common(ctx)
        sns.histplot(ax=ax, x="x", bins=(ch.bin.maxbins if ch and ch.bin else "auto"),
                     multiple="stack", **kw)
        ax.set_ylabel(ctx.style.y_label or "frequency")


@register("box", "seaborn")
class SnsBox(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        _categorical(sns.boxplot, ax, ctx, fliersize=3)


@register("violin", "seaborn")
class SnsViolin(_SnsRenderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        _categorical(sns.violinplot, ax, ctx, cut=0, inner="quartile")


def _categorical(fn, ax, ctx: RenderContext, **extra) -> None:
    horizontal = ctx.style.orientation == "horizontal"
    kw = {"data": ctx.pf}
    if ctx.has_color:
        kw.update(hue="color", hue_order=ctx.series, palette=ctx.colors)
    else:
        kw["color"] = ctx.base_color()
    axes = {"y": "y"} if "x" not in ctx.pf.columns else (
        {"x": "y", "y": "x"} if horizontal else {"x": "x", "y": "y"})
    fn(ax=ax, **axes, **kw, **extra)
    _relabel(ax, ctx, horizontal)


def _relabel(ax, ctx: RenderContext, horizontal: bool) -> None:
    """Readable labels on the discrete axis; the driver sets the axis titles."""
    axis = ax.yaxis if horizontal else ax.xaxis
    ch = ctx.channel("x")
    if ch is None or ch.type != "temporal":
        return
    cats = sh.categories(ctx.pf, "x")
    axis.set_ticks(range(len(cats)), sh.tick_labels(cats, ch))
