"""Dialect normalization.

The flat dialect ("viz_type" + "x_axis" + "y_axis") is what an agent writes
first, but it doesn't scale: once color, faceting, or per-channel aggregation
show up, every chart type ends up inventing its own keys. Here, and only here,
the sugar expands into the canonical spec. Everything downstream works on a
single shape.
"""

from __future__ import annotations

from typing import Any

#: flat key -> canonical path (list of segments).
_CHANNEL_KEYS: dict[str, tuple[str, ...]] = {
    "x_axis": ("encoding", "x", "field"),
    "xaxis": ("encoding", "x", "field"),
    "x": ("encoding", "x", "field"),
    "y_axis": ("encoding", "y", "field"),
    "yaxis": ("encoding", "y", "field"),
    "y": ("encoding", "y", "field"),
    "group_by": ("encoding", "color", "field"),
    "color_by": ("encoding", "color", "field"),
    "hue": ("encoding", "color", "field"),
    "series": ("encoding", "color", "field"),
    "size_by": ("encoding", "size", "field"),
    "style_by": ("encoding", "style", "field"),
    "facet_by": ("encoding", "facet", "field"),
    "facet": ("encoding", "facet", "field"),
    "agg": ("encoding", "y", "aggregate"),
    "aggregate": ("encoding", "y", "aggregate"),
    "aggregation": ("encoding", "y", "aggregate"),
    "time_unit": ("encoding", "x", "time_unit"),
    "freq": ("encoding", "x", "time_unit"),
    "bins": ("encoding", "x", "bin", "maxbins"),
}

_DATA_KEYS: dict[str, tuple[str, ...]] = {
    "filters": ("data", "filters"),
    "where": ("data", "filters"),
    "sort": ("data", "sort"),
    "sort_by": ("data", "sort"),
    "limit": ("data", "limit"),
    "top_n": ("data", "limit"),
}

#: Presentation shortcuts accepted at the top level of either dialect.
_STYLE_KEYS = (
    "title", "subtitle", "x_label", "y_label", "legend_title",
    "palette", "theme", "figsize", "grid", "legend", "stacked",
    "orientation", "annotate",
)

_OUTPUT_KEYS = {"dpi": "dpi", "path": "path", "transparent": "transparent"}

_VIZ_ALIASES = {"type": "viz_type", "chart_type": "viz_type", "kind": "viz_type",
                "plot_type": "viz_type"}

#: Common synonyms for viz_type.
_VIZ_VALUES = {
    "barplot": "bar", "bars": "bar", "column": "bar", "barh": "bar",
    "lineplot": "line", "linechart": "line", "timeseries": "line",
    "scatterplot": "scatter", "points": "scatter",
    "histogram": "hist", "histplot": "hist",
    "boxplot": "box", "violinplot": "violin",
    "areachart": "area",
}

#: Every key the normalizer understands (used for `did_you_mean`).
KNOWN_KEYS = (
    set(_CHANNEL_KEYS) | set(_DATA_KEYS) | set(_STYLE_KEYS) | set(_OUTPUT_KEYS)
    | set(_VIZ_ALIASES) | {"viz_type", "version", "backend", "encoding", "data",
                           "style", "output", "format"}
)


def is_canonical(raw: dict) -> bool:
    return "encoding" in raw


def normalize(raw: Any) -> dict:
    """Return the equivalent canonical spec. Does not validate: that's stage 2.

    Keys it doesn't recognize are left untouched, so validation reports them as
    UNKNOWN_FIELD with their exact path instead of swallowing them.
    """
    if not isinstance(raw, dict):
        return raw
    out: dict = {}

    for key, value in raw.items():
        if value is None:
            continue
        target = _VIZ_ALIASES.get(key, key)

        if target == "viz_type":
            out["viz_type"] = _canon_viz(value)
        elif target in ("encoding", "data", "style", "output"):
            _deep_merge(out, target, value)
        elif target in _CHANNEL_KEYS and not (
            # inside a canonical spec, bare "x"/"y" are not channel shortcuts
            is_canonical(raw) and target in ("x", "y", "facet")
        ):
            _merge(out, _CHANNEL_KEYS[target], value)
        elif target in _DATA_KEYS:
            _merge(out, _DATA_KEYS[target], value)
        elif target in _STYLE_KEYS:
            _merge(out, ("style", target), value)
        elif target in _OUTPUT_KEYS:
            _merge(out, ("output", _OUTPUT_KEYS[target]), value)
        elif target == "format":
            _merge(out, ("output", "format"), value)
        else:
            out[key] = value

    _infer_orientation(raw, out)
    return out


def _deep_merge(out: dict, key: str, value: Any) -> None:
    """Merge a canonical block over whatever the shortcuts already wrote.

    The canonical block wins: if a contract carries both a bare `title` and a
    `style.title`, the latter is kept.
    """
    if not isinstance(value, dict) or not isinstance(out.get(key), dict):
        out[key] = value
        return
    node = out[key]
    for k, v in value.items():
        if isinstance(v, dict) and isinstance(node.get(k), dict):
            _deep_merge(node, k, v)
        else:
            node[k] = v


def _canon_viz(value: Any) -> Any:
    if isinstance(value, str):
        key = value.strip().lower().replace(" ", "").replace("_", "")
        return _VIZ_VALUES.get(key, value.strip().lower())
    return value


def _infer_orientation(raw: dict, out: dict) -> None:
    """'barh' and 'horizontal_bar' carry the orientation in the name."""
    name = str(raw.get("viz_type") or raw.get("type") or "").lower()
    if name.replace("_", "") in ("barh", "horizontalbar", "hbar"):
        out.setdefault("style", {}).setdefault("orientation", "horizontal")


def _merge(out: dict, path: tuple[str, ...], value: Any) -> None:
    """Write `value` at `path` without overwriting what the user already set.

    The canonical spec always beats the flat shortcut: if someone sends both
    `encoding.y.aggregate` and `agg`, the former wins.
    """
    node = out
    for part in path[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {} if nxt is None else nxt
            if not isinstance(nxt, dict):
                return  # the user put a non-dict there; let pydantic report it
            node[part] = nxt
        node = nxt
    leaf = path[-1]
    if leaf in node and node[leaf] is not None:
        return
    node[leaf] = value
