"""Palettes.

Hue order is not cosmetic: it is the mechanism that keeps series distinguishable
for viewers with a color vision deficiency. Hues are assigned **in fixed order
and never recycled**; when there are more series than slots, the right answer is
to fold the tail into "Other" or to facet, not to generate a new color.

The default palette is validated (lightness band, chroma floor, CVD separation
and contrast) against both a light and a dark surface. If you swap it, validate
yours the same way instead of picking by eye.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.colors as mcolors


@dataclass(frozen=True)
class Palette:
    name: str
    light: tuple[str, ...]
    dark: tuple[str, ...]
    #: Series that stay distinguishable when every pair is compared against
    #: every other (scatter, bubble). In bars and lines only neighbors compete.
    all_pairs_cap: int = 3

    def colors(self, mode: str = "light") -> tuple[str, ...]:
        return self.dark if mode == "dark" else self.light

    def __len__(self) -> int:
        return len(self.light)


#: Eight hues in an order that clears the adjacent-pair separation thresholds
#: in both modes.
DEFAULT = Palette(
    name="default",
    light=("#2a78d6", "#eb6834", "#1baf7a", "#eda100",
           "#e87ba4", "#008300", "#4a3aa7", "#e34948"),
    dark=("#3987e5", "#d95926", "#199e70", "#c98500",
          "#d55181", "#008300", "#9085e9", "#e66767"),
)

#: The first three slots, which clear the threshold with all pairs in play.
SAFE3 = Palette(
    name="safe3",
    light=DEFAULT.light[:3],
    dark=DEFAULT.dark[:3],
)

PALETTES: dict[str, Palette] = {
    "default": DEFAULT,
    "muted": DEFAULT,   # legacy alias from the flat dialect
    "safe3": SAFE3,
}

#: Single-hue sequential ramp, light -> dark. For continuous magnitude.
SEQUENTIAL_BLUE = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
)

#: Diverging: two opposite poles with a neutral gray in the middle.
DIVERGING = {
    "light": ("#0d366b", "#2a78d6", "#9ec5f4", "#f0efec", "#f0a3a2", "#e34948", "#8c1f1e"),
    "dark": ("#0d366b", "#3987e5", "#9ec5f4", "#383835", "#f0a3a2", "#e66767", "#8c1f1e"),
}

MAX_SERIES = len(DEFAULT)


def get(name: str) -> Palette:
    return PALETTES.get(name, DEFAULT)


def series_colors(name: str, n: int, mode: str = "light") -> list[str]:
    """The first n colors, in fixed order.

    Color follows the entity, not its rank: filtering series must not repaint
    the survivors, so callers must always pass categories in the same order.
    """
    pal = get(name).colors(mode)
    if n > len(pal):
        raise ValueError(
            f"{n} series with a palette of {len(pal)}: fold into 'Other' or facet"
        )
    return list(pal[:n])


def sequential_cmap(name: str = "blue"):
    """Single-hue continuous map for magnitude."""
    if name in ("blue", "default", "muted"):
        return mcolors.LinearSegmentedColormap.from_list("jp_seq", SEQUENTIAL_BLUE)
    return name  # let any matplotlib colormap name through


def diverging_cmap(mode: str = "light"):
    return mcolors.LinearSegmentedColormap.from_list("jp_div", DIVERGING[mode])
