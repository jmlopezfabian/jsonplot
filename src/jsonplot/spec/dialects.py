"""Dialect normalization.

Three dialects come in and one shape comes out.

The **flat** dialect ("viz_type" + "x_axis" + "y_axis") is what an agent writes
first, but it doesn't scale: once color, faceting, or per-channel aggregation
show up, every chart type ends up inventing its own keys.

**Vega-Lite** is the one a model has actually read the most of — it is a decade
old and all over the training data — and the canonical spec is deliberately
shaped like it. Accepting its spelling costs a lookup table and saves a repair
round: `mark`, `timeUnit`, `shape`, `row`/`column`, `"type": "Q"`, a channel-level
`sort`, `stack`, `scale: {"type": "log"}`. What has no equivalent here (`layer`,
`transform`, `params`, a `data` source) is *not* silently dropped: it fails with
a hint naming what to use instead, in `parse.py`.

Here, and only here, all of that expands into the canonical spec. Everything
downstream works on a single shape.
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
                "plot_type": "viz_type", "mark": "viz_type"}

#: Common synonyms for viz_type.
_VIZ_VALUES = {
    "barplot": "bar", "bars": "bar", "column": "bar", "barh": "bar",
    "lineplot": "line", "linechart": "line", "timeseries": "line",
    "scatterplot": "scatter", "points": "scatter",
    "histogram": "hist", "histplot": "hist",
    "boxplot": "box", "violinplot": "violin",
    "areachart": "area",
    # Vega-Lite marks
    "point": "scatter", "circle": "scatter", "square": "scatter", "tick": "scatter",
    "trail": "line",
}

#: Which of those synonyms came from Vega-Lite (`boxplot` predates it here).
_VL_MARK_VALUES = ("point", "circle", "square", "tick", "trail", "boxplot")

# --------------------------------------------------------------------------
# Vega-Lite
# --------------------------------------------------------------------------

#: The channel types that can only be a category, used to recognize a Vega-Lite
#: horizontal bar chart.
CATEGORICAL = ("nominal", "ordinal")

#: Channel roles it spells differently. `shape` and `strokeDash` are both the
#: second categorical dimension, which here is one channel: `style`.
_VL_CHANNELS = {"shape": "style", "strokeDash": "style",
                "row": "facet", "column": "facet"}

#: Its single-letter type shorthand.
_VL_TYPES = {"q": "quantitative", "n": "nominal", "o": "ordinal", "t": "temporal"}

#: Its time units. The `year*` forms bucket a timeline, which is what `time_unit`
#: does; the bare ones are cyclic in Vega-Lite (month-of-year) and are mapped to
#: the closest thing here rather than refused.
_VL_TIME_UNITS = {
    "yearmonth": "month", "yearquarter": "quarter", "yearmonthdate": "day",
    "yearweek": "week", "yearday": "day", "yeardate": "day",
    "utcyearmonth": "month", "utcyearquarter": "quarter", "utcyearmonthdate": "day",
    "date": "day", "monthdate": "day",
}

#: Its aggregation names.
_VL_AGGREGATES = {"average": "mean", "distinct": "nunique",
                  "stdev": "std", "stdevp": "std"}

#: Top-level keys that carry no information for this framework. `$schema` says
#: which Vega-Lite version the contract was written against; the answer here is
#: always "none of them", so it is dropped rather than reported.
_VL_IGNORED = ("$schema",)

#: Keys that mean something real in Vega-Lite and nothing here. They are left in
#: place on purpose so validation reports them; `parse.py` turns each into a
#: hint naming the nearest thing this framework does have.
VL_UNSUPPORTED = {
    "transform": "use aggregate, bin or time_unit on the channel, and "
                 "data.filters, data.sort and data.limit for the rest",
    "layer": "one chart per contract; draw the second one separately",
    "hconcat": "one chart per contract; draw the second one separately",
    "vconcat": "one chart per contract; draw the second one separately",
    "concat": "one chart per contract; draw the second one separately",
    "repeat": "use encoding.facet",
    "params": "this framework draws static figures",
    "selection": "this framework draws static figures",
    "config": "use the style block",
    "resolve": "use facet.share_x and facet.share_y",
    "projection": "there are no map projections here",
}

#: Data-source keys. Here the DataFrame is an argument to `plot`, so a `data`
#: block naming a source is a category error worth an explicit message.
VL_DATA_SOURCE_KEYS = frozenset({"url", "values", "name", "format", "sequence",
                                 "graticule", "sphere"})

#: Pixels per inch assumed when translating Vega-Lite's `width`/`height`, which
#: are pixels, into `figsize`, which is inches.
VL_PIXELS_PER_INCH = 100.0


def _from_vega_lite(raw: dict) -> dict:
    """Rewrite Vega-Lite spellings into this framework's own.

    Emits the flat dialect where that is the shortest path — a channel-level
    `sort` becomes a top-level `sort`, which the main pass already knows how to
    place — so the translation stays in one direction and one place.
    """
    out = {k: v for k, v in raw.items() if k not in _VL_IGNORED}

    width, height = out.get("width"), out.get("height")
    if _is_number(width) and _is_number(height):
        out.pop("width"), out.pop("height")
        out.setdefault("figsize", [width / VL_PIXELS_PER_INCH,
                                   height / VL_PIXELS_PER_INCH])

    encoding = out.get("encoding")
    if isinstance(encoding, dict):
        out["encoding"] = _vl_encoding(encoding, out)
        _vl_horizontal(out)
    return out


def _vl_horizontal(out: dict) -> None:
    """Vega-Lite says "horizontal bars" by swapping the channels; here there is
    a `style.orientation` for it.

    A bar chart whose x is the measure and whose y is the category is not
    ambiguous — it is the only thing it can be — but the translation only fires
    when the contract says so itself, through the declared types or an
    aggregate on x. Guessing from the data would belong in the binder, not in a
    dialect.
    """
    encoding = out.get("encoding")
    if not isinstance(encoding, dict):
        return
    if _canon_viz(out.get("viz_type") or out.get("mark") or "") not in ("bar", "area"):
        return
    x, y = encoding.get("x"), encoding.get("y")
    if not isinstance(x, dict) or not isinstance(y, dict):
        return
    if y.get("type") not in CATEGORICAL:
        return
    if x.get("type") != "quantitative" and "aggregate" not in x:
        return
    encoding["x"], encoding["y"] = y, x
    out.setdefault("orientation", "horizontal")


def _vl_encoding(encoding: dict, out: dict) -> dict:
    """Rename the channels, then translate what is inside each one.

    When two Vega-Lite channels land on the same role — `row` and `column` are
    both `facet` here — the first one wins and the second is dropped rather than
    silently overwriting it.
    """
    translated: dict = {}
    for name, channel in encoding.items():
        role = _VL_CHANNELS.get(name, name)
        if role in translated:
            continue
        translated[role] = _vl_channel(role, channel, out)
    return translated


def _vl_channel(role: str, channel: Any, out: dict) -> Any:
    """One channel. Hoists into `out` the parts that live elsewhere here."""
    if not isinstance(channel, dict):
        return channel
    ch = dict(channel)

    if isinstance(ch.get("type"), str):
        ch["type"] = _VL_TYPES.get(ch["type"].lower(), ch["type"])

    if "timeUnit" in ch:
        # the canonical spelling wins, as it does everywhere else in here
        ch.setdefault("time_unit", ch["timeUnit"])
        ch.pop("timeUnit")
    if isinstance(ch.get("time_unit"), str):
        unit = ch["time_unit"].lower()
        ch["time_unit"] = _VL_TIME_UNITS.get(unit, unit)

    if isinstance(ch.get("aggregate"), str):
        agg = ch["aggregate"].lower()
        ch["aggregate"] = _VL_AGGREGATES.get(agg, agg)

    # scale: {"type": "log"} -> scale: "log". Anything else in there is a real
    # scale configuration this framework does not have; leave it to be reported.
    scale = ch.get("scale")
    if isinstance(scale, dict) and set(scale) == {"type"}:
        ch["scale"] = scale["type"]

    # axis/legend carry a title here, and only a title.
    for block in ("axis", "legend"):
        value = ch.get(block)
        if isinstance(value, dict) and set(value) <= {"title"}:
            ch.pop(block)
            if "title" in value:
                ch.setdefault("title", value["title"])

    # These two are per-channel in Vega-Lite and global here.
    if "sort" in ch:
        order = _vl_sort(ch.pop("sort"), role)
        if order is not None:
            out.setdefault("sort", order)
    if "stack" in ch:
        stack = ch.pop("stack")
        out.setdefault("stacked", bool(stack) and stack != "none")

    return ch


def _vl_sort(value: Any, role: str) -> Any:
    """`{"x": {"sort": "-y"}}` -> `{"sort": {"by": "y", "order": "desc"}}`."""
    if value is None:
        return None
    if isinstance(value, str):
        if value.lower() in ("ascending", "descending"):
            return {"by": role, "order": "asc" if value.lower() == "ascending" else "desc"}
        return value                      # "-y" / "y": the flat shorthand already
    if isinstance(value, dict):
        by = value.get("field") or value.get("encoding")
        order = str(value.get("order", "ascending")).lower()
        if by is None:
            return None
        return {"by": by, "order": "desc" if order.startswith("desc") else "asc"}
    return value                          # a list of categories: not supported here


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


#: Every key the normalizer understands (used for `did_you_mean`).
KNOWN_KEYS = (
    set(_CHANNEL_KEYS) | set(_DATA_KEYS) | set(_STYLE_KEYS) | set(_OUTPUT_KEYS)
    | set(_VIZ_ALIASES) | {"viz_type", "version", "backend", "encoding", "data",
                           "style", "output", "format", "width", "height"}
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
    raw = _from_vega_lite(raw)
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
    if isinstance(value, dict):
        # Vega-Lite: {"mark": {"type": "bar", "point": true, ...}}
        value = value.get("type", value)
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
