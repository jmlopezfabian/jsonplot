"""Stages 5 and 6: figure, facets, decoration and output.

Everything that is the same for every chart type lives here — axes, grid,
labels, legend, facets — so a renderer only has to draw marks.
"""

from __future__ import annotations

import base64
import io
import math

import matplotlib
import matplotlib.dates as mdates
import pandas as pd
from matplotlib.ticker import FuncFormatter

from ..binding.binder import BoundSpec
from ..binding.errors import SpecErrorGroup
from ..theme import themes
from . import mpl as _mpl_renderers  # noqa: F401  (registers the renderers)
from . import sns as _sns_renderers  # noqa: F401  (optional)
from .base import RenderContext
from .mpl._shared import fmt_number
from .registry import get_renderer

matplotlib.use("Agg", force=False)
import matplotlib.pyplot as plt  # noqa: E402

#: Above this many series the legend moves outside, to the right; below, on top.
LEGEND_INLINE_MAX = 4
#: Past this magnitude the axis switches to compact notation (12k, 3.4M).
COMPACT_ABOVE = 10_000


def render(bound: BoundSpec, pf: pd.DataFrame):
    """BoundSpec + plot frame -> matplotlib.figure.Figure."""
    renderer, err = get_renderer(bound.viz_type, bound.spec.backend)
    if renderer is None:
        raise SpecErrorGroup([err])

    style = bound.style
    with themes.applied(style.theme):
        mode = themes.mode_of(style.theme)
        ctx = RenderContext.build(bound, pf, mode)
        facets = _facet_values(pf)

        fig, axes = _make_axes(style, facets, bound)
        for ax, value in zip(axes, facets or [None]):
            sub = pf if value is None else pf[pf["facet"] == value]
            renderer.draw(ax, ctx.subset(sub))
            _drop_axes_legend(ax)
            _decorate_axes(ax, bound, single=not facets, faceted=bool(facets))
            if value is not None:
                ax.set_title(str(value), fontsize=11)

        _shared_labels(fig, axes, bound, facets)
        _header(fig, axes[0], style, faceted=bool(facets))
        fig.set_dpi(bound.spec.output.dpi)
    return fig


# --------------------------------------------------------------------------


def _facet_values(pf: pd.DataFrame) -> list:
    if "facet" not in pf.columns:
        return []
    return list(pd.Index(pf["facet"].drop_duplicates()))


def _make_axes(style, facets, bound):
    if not facets:
        fig, ax = plt.subplots(figsize=style.figsize)
        return fig, [ax]

    facet_ch = bound.spec.encoding.facet
    ncols = facet_ch.columns or min(3, len(facets))
    nrows = math.ceil(len(facets) / ncols)
    w, h = style.figsize
    fig, grid = plt.subplots(
        nrows, ncols, figsize=(w, h * nrows / max(1, min(2, nrows))),
        sharex=facet_ch.share_x, sharey=facet_ch.share_y, squeeze=False,
    )
    flat = list(grid.ravel())
    for ax in flat[len(facets):]:
        ax.set_visible(False)  # empty grid cells are hidden, not left blank
    return fig, flat[:len(facets)]


def _drop_axes_legend(ax) -> None:
    """The driver places the legend, once for the whole figure.

    Some backends (seaborn) draw their own inside the axes; it is removed here,
    keeping the artist labels, which is what is actually needed.
    """
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()


def _decorate_axes(ax, bound: BoundSpec, single: bool, faceted: bool = False) -> None:
    style = bound.style
    horizontal = style.orientation == "horizontal"

    if style.grid != "none":
        # the grid is requested per role ("y" = the measure axis); when the
        # chart is rotated, the measure changes axis and the grid follows it
        axis = style.grid if not horizontal else {"x": "y", "y": "x"}.get(style.grid, style.grid)
        ax.grid(axis="both" if axis == "both" else axis, zorder=0)
        ax.set_axisbelow(True)   # the grid always sits behind the marks

    # the scale travels with the channel too when the chart is rotated
    setters = {"x": ax.set_yscale, "y": ax.set_xscale} if horizontal else \
              {"x": ax.set_xscale, "y": ax.set_yscale}
    for role, setter in setters.items():
        ch = bound.get(role)
        if ch and ch.scale and ch.scale != "linear":
            setter(ch.scale)

    _format_temporal(ax, bound, faceted)
    _format_magnitude(ax, bound, horizontal)

    if single:
        x, y = _axis_labels(bound, horizontal)
        ax.set_xlabel(x)
        ax.set_ylabel(y)


def _shared_labels(fig, axes, bound, facets) -> None:
    """With facets, the axis label is written once for the whole figure."""
    if not facets:
        return
    x, y = _axis_labels(bound, bound.style.orientation == "horizontal")
    if x:
        fig.supxlabel(x, fontsize=11, color=themes.INK_SOFT)
    if y:
        fig.supylabel(y, fontsize=11, color=themes.INK_SOFT)


def _label(bound: BoundSpec, role: str, override: str | None) -> str:
    if override is not None:
        return override
    ch = bound.get(role)
    return ch.title if ch else ""


def _axis_labels(bound: BoundSpec, horizontal: bool) -> tuple[str, str]:
    """Labels for the physical axes.

    The contract talks about channels, not axes: in a horizontal chart the 'y'
    channel is drawn along the x axis, and its label has to travel with it.
    """
    style = bound.style
    x = _label(bound, "x", style.x_label)
    y = _label(bound, "y", style.y_label)
    return (y, x) if horizontal else (x, y)


def _format_temporal(ax, bound: BoundSpec, faceted: bool) -> None:
    """Readable dates, and few enough of them for the available width."""
    ch = bound.get("x")
    if ch is None or ch.type != "temporal" or bound.viz_type in ("bar", "box"):
        return
    locator = mdates.AutoDateLocator(minticks=2, maxticks=4 if faceted else 8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))


def _format_magnitude(ax, bound: BoundSpec, horizontal: bool) -> None:
    """Compact notation on the measure axis: 650000 reads worse than 650k."""
    ch = bound.get("y")
    if ch is None or ch.type != "quantitative":
        return
    axis = ax.xaxis if horizontal else ax.yaxis
    lo, hi = (ax.get_xlim() if horizontal else ax.get_ylim())
    if max(abs(lo), abs(hi)) < COMPACT_ABOVE:
        return
    axis.set_major_formatter(FuncFormatter(lambda v, _: fmt_number(v)))


def _header(fig, ax, style, faceted: bool = False) -> None:
    """Title, subtitle and legend share the top band.

    They are placed with a single descending cursor so they can never collide,
    which is what happens when each picks its own height independently.
    """
    ink = themes.THEMES.get(style.theme, themes.CLEAN)["axes.titlecolor"]
    y = 1.0

    if style.title:
        fig.suptitle(style.title, x=0.02, ha="left", fontsize=15,
                     fontweight="bold", y=y, color=ink)
        y -= 0.055
    if style.subtitle:
        fig.text(0.02, y, style.subtitle, ha="left", va="top", fontsize=11,
                 color=themes.INK_SOFT)
        y -= 0.05

    placement = _legend(fig, ax, style, y)
    if placement == "top":
        y -= 0.06
    if y < 1.0:
        # with facets, room is also needed for each facet's own title
        reserve = 0.02 + (0.05 if faceted else 0.0)
        fig.subplots_adjust(top=max(0.6, y - reserve))


def _legend(fig, ax, style, y: float) -> str | None:
    """Present whenever there are two or more series: identity is never
    carried by color alone."""
    if style.legend == "none":
        return None
    handles, labels = ax.get_legend_handles_labels()
    pairs = {l: h for h, l in zip(handles, labels) if l and not l.startswith("_")}
    if len(pairs) < 2:
        return None

    placement = style.legend
    if placement == "auto":
        placement = "top" if len(pairs) <= LEGEND_INLINE_MAX else "right"

    common = {"handles": list(pairs.values()), "labels": list(pairs.keys()),
              "title": style.legend_title, "frameon": False}
    if placement == "top":
        fig.legend(**common, loc="upper left", bbox_to_anchor=(0.02, y),
                   ncol=min(len(pairs), 4))
    else:
        fig.legend(**common, loc="upper left", bbox_to_anchor=(1.005, 0.95))
    return placement


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def export(fig, output):
    """Return the figure, or serialize it according to `output.format`."""
    if output.format == "figure":
        if output.path:
            fig.savefig(output.path, dpi=output.dpi, transparent=output.transparent)
        return fig

    buf = io.BytesIO()
    fig.savefig(buf, format=output.format if output.format != "base64" else "png",
                dpi=output.dpi, transparent=output.transparent, bbox_inches="tight")
    data = buf.getvalue()
    if output.path:
        with open(output.path, "wb") as fh:
            fh.write(data)
    if output.format == "svg":
        return data.decode("utf-8")
    if output.format == "base64":
        return base64.b64encode(data).decode("ascii")
    return data
