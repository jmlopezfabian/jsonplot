"""Themes: the rcParams that make a figure readable.

A theme touches neither the data nor the geometry, only the air around the
marks: a recessive grid, no top or right spine, quiet typography.
"""

from __future__ import annotations

from contextlib import contextmanager

import matplotlib as mpl

INK = "#1a1a19"
INK_SOFT = "#52514e"
GRID = "#e4e3df"
SURFACE = "#ffffff"

CLEAN = {
    "figure.facecolor": SURFACE,
    "figure.dpi": 110,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": "#c9c8c3",
    "axes.linewidth": 0.8,
    "axes.labelcolor": INK_SOFT,
    "axes.labelsize": 11,
    "axes.labelpad": 8,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "axes.titlepad": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "grid.alpha": 1.0,
    "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "xtick.major.pad": 6,
    "ytick.major.pad": 6,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "legend.labelcolor": INK_SOFT,
    "legend.title_fontsize": 10,
    "lines.linewidth": 2.0,          # thin marks, not heavy ones
    "lines.markersize": 6,
    "lines.solid_capstyle": "round",
    "patch.linewidth": 0,
    "font.size": 11,
    "savefig.bbox": "tight",
}

#: Variant for a dark surface. Series colors come from the palette, not from
#: the theme: only ink and background live here.
DARK = {
    **CLEAN,
    "figure.facecolor": "#1a1a19",
    "axes.facecolor": "#1a1a19",
    "axes.edgecolor": "#4a4a47",
    "axes.labelcolor": "#c3c2b7",
    "axes.titlecolor": "#ffffff",
    "grid.color": "#333330",
    "xtick.color": "#c3c2b7",
    "ytick.color": "#c3c2b7",
    "legend.labelcolor": "#c3c2b7",
    "text.color": "#ffffff",
    "savefig.facecolor": "#1a1a19",
}

THEMES = {"clean": CLEAN, "dark": DARK}


def mode_of(theme: str) -> str:
    """The theme's surface mode, which is what the palette needs."""
    return "dark" if theme == "dark" else "light"


@contextmanager
def applied(theme: str):
    params = THEMES.get(theme, CLEAN)
    with mpl.rc_context(params):
        yield params
