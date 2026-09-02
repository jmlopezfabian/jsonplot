"""Scatter: one mark per row."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ...theme import palettes
from ..base import RenderContext, Renderer
from ..registry import register

MARKERS = ("o", "s", "^", "D", "v", "P")
#: Default mark area when there is no size channel, in points².
DEFAULT_SIZE = 48.0


@register("scatter", "matplotlib")
class ScatterRenderer(Renderer):
    def draw(self, ax, ctx: RenderContext) -> None:
        sizes = self._sizes(ctx)
        color_ch = ctx.channel("color")

        # continuous color: a single-hue ramp, not a categorical scale
        if color_ch is not None and color_ch.type == "quantitative":
            sc = ax.scatter(ctx.pf["x"], ctx.pf["y"], c=ctx.pf["color"],
                            s=_sizes_for(sizes, ctx.pf.index),
                            cmap=palettes.sequential_cmap(), zorder=3,
                            edgecolors=ax.get_facecolor(), linewidths=0.8)
            cbar = ax.figure.colorbar(sc, ax=ax, pad=0.02, fraction=0.045)
            cbar.set_label(color_ch.title)
            cbar.outline.set_visible(False)
            return

        styles = list(dict.fromkeys(ctx.pf["style"])) if "style" in ctx.pf else []
        for cat, part in ctx.groups():
            color = ctx.color_for(cat) if cat is not None else ctx.base_color()
            for i, sub in _by_style(part, styles):
                # a ring in the surface color keeps overlapping marks from
                # melting into one blob
                ax.scatter(sub["x"], sub["y"], s=_sizes_for(sizes, sub.index), color=color,
                           marker=MARKERS[i % len(MARKERS)],
                           label=_label(cat, sub, styles), alpha=0.85, zorder=3,
                           edgecolors=ax.get_facecolor(), linewidths=0.8)

    def _sizes(self, ctx: RenderContext) -> pd.Series | None:
        """Each mark's area, index-aligned to the plot frame.

        Returned as a Series rather than an array so that slicing by series or
        by style does not depend on row position.
        """
        ch = ctx.channel("size")
        if ch is None or "size" not in ctx.pf:
            return None
        v = ctx.pf["size"].to_numpy(dtype=float)
        lo, hi = np.nanmin(v), np.nanmax(v)
        rng = ctx.bound.spec.encoding.size.range
        scaled = (np.full(len(v), float(np.mean(rng)))
                  if not np.isfinite(lo) or hi == lo
                  else np.interp(v, (lo, hi), rng))
        return pd.Series(scaled, index=ctx.pf.index)


def _sizes_for(sizes: pd.Series | None, index) -> float | np.ndarray:
    if sizes is None:
        return DEFAULT_SIZE
    return sizes.loc[index].to_numpy()


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
