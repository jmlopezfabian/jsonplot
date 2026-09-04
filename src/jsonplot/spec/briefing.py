"""The contract, written out for whoever has to produce one.

Everything here is derived by introspection from the definitions that the
framework actually executes: `CAPABILITIES`, the `Literal` vocabularies in
`models`, the alias tables in `dialects`, the installed renderers, the palettes
and themes. Nothing is transcribed by hand, so adding a chart type, an
aggregation or a palette updates what the model reads on the next call — a
briefing maintained separately would be stale by the second commit.

`coverage()` is the enforcement side of that promise: it reports every value in
the contract's vocabulary that the document fails to mention, and the test suite
fails when that set is non-empty.
"""

from __future__ import annotations

import json
from typing import Any, Literal, get_args, get_origin, get_type_hints

import pandas as pd

from ..theme import PALETTES, THEMES
from . import dialects, models
from .capabilities import CAPABILITIES, NUMERIC_ONLY
from .models import CHANNELS, Spec

__all__ = ["contract", "sections", "coverage", "vocabulary"]


def available() -> dict[str, list[str]]:
    """Installed renderers. Imported late: the registry reaches back into
    `spec` for capabilities, and importing it at module scope would close the
    cycle."""
    from ..render.registry import available as _available

    return _available()

Format = Literal["markdown", "json"]

#: Sections, in the order they are written. Selectable through `include`.
SECTION_NAMES = (
    "overview", "shape", "types", "channels", "data", "style", "output",
    "flat", "vega_lite", "rules", "example",
)


# --------------------------------------------------------------------------
# Vocabulary: every closed set the contract accepts
# --------------------------------------------------------------------------


def vocabulary() -> dict[str, tuple[str, ...]]:
    """Every enumerated value the contract accepts, read off the models.

    Walks the pydantic models rather than a list kept alongside them: a new
    `Literal` shows up here the moment it is declared.
    """
    out: dict[str, tuple[str, ...]] = {}
    for model in _models():
        hints = get_type_hints(model)
        for name, annotation in hints.items():
            if name.startswith("_") or name not in model.model_fields:
                continue
            values = _literal_values(annotation)
            if values:
                out.setdefault(f"{model.__name__}.{name}", values)
    out["palette"] = tuple(sorted(PALETTES))
    out["theme"] = tuple(sorted(THEMES))
    out["viz_type_installed"] = tuple(sorted(available()))
    return out


def _models() -> list[type]:
    return [obj for obj in vars(models).values()
            if isinstance(obj, type) and issubclass(obj, models.BaseModel)
            and obj.__module__ == models.__name__]


def _literal_values(annotation: Any) -> tuple[str, ...]:
    """The Literal members inside an annotation, unwrapping optionals."""
    if get_origin(annotation) is Literal:
        return tuple(str(v) for v in get_args(annotation))
    args = get_args(annotation)
    if not args:
        return ()
    found: list[str] = []
    for arg in args:
        found.extend(_literal_values(arg))
    return tuple(dict.fromkeys(found))


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


def _vocab(model: type, field: str) -> tuple[str, ...]:
    return _literal_values(get_type_hints(model)[field])


def _list(values) -> str:
    return ", ".join(f"`{v}`" for v in values)


def _overview() -> str:
    installed = available()
    backends = sorted({b for backs in installed.values() for b in backs})
    return "\n".join([
        "## What you are producing",
        "",
        "A **contract**: a JSON object that declares which column of an already-loaded",
        "DataFrame goes in which visual channel. You are not writing plotting code, and",
        "no code you write will be executed. The framework draws the figure.",
        "",
        "Answer with the JSON object and nothing else. Unknown keys are rejected with",
        "their exact path, so do not invent fields; every accepted key is listed below.",
        "",
        f"Backends installed here: {_list(backends)}.",
    ])


def _shape() -> str:
    return "\n".join([
        "## Shape",
        "",
        "```json",
        json.dumps({
            "viz_type": "bar",
            "backend": "matplotlib",
            "encoding": {
                "x": {"field": "<column>", "type": "nominal"},
                "y": {"field": "<column>", "type": "quantitative",
                      "aggregate": "sum"},
            },
            "data": {"filters": [], "sort": None, "limit": None},
            "style": {"title": "<text>"},
            "output": {"format": "figure"},
        }, indent=2),
        "```",
        "",
        "Only `viz_type` and `encoding` are required; every other block has "
        "defaults. Note the `aggregate` on `y`: on a `bar` it is not optional "
        "(rule 5).",
        f"`version` is `{Spec.model_fields['version'].default}` and may be omitted; "
        f"`backend` defaults to `{Spec.model_fields['backend'].default}`; the "
        "`data`, `style` and `output` blocks are optional.",
        f"A channel may be written as a bare string — `\"x\": \"region\"` means",
        "`{\"field\": \"region\"}`. `type` is inferred from the column dtype when omitted.",
    ])


def _types() -> str:
    installed = available()
    lines = [
        "## Chart types",
        "",
        "| viz_type | required | optional | aggregates | backends |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, cap in CAPABILITIES.items():
        backends = installed.get(name)
        lines.append(
            f"| `{name}` | {_list(cap.required)} | {_list(cap.optional) or '—'} "
            f"| {'yes, over ' + f'`{cap.measure}`' if cap.aggregates else 'no'} "
            f"| {_list(backends) if backends else '**not installed**'} |"
        )
    aggregating = [n for n, c in CAPABILITIES.items() if c.aggregates]
    lines += [
        "",
        f"Aggregating types ({_list(aggregating)}) need an `aggregate` on their "
        "measure — see rule 5. The others draw one mark per row.",
        "",
        "What each one is for:",
        "",
    ]
    for name, cap in CAPABILITIES.items():
        lines.append(f"- `{name}` — {cap.description}")
    return "\n".join(lines)


def _channels() -> str:
    lines = [
        "## Channels",
        "",
        f"Roles: {_list(CHANNELS)}. Which ones a chart accepts is in the table above.",
        "",
        "Accepted scale types per role, by chart type (a role not listed accepts any):",
        "",
    ]
    for name, cap in CAPABILITIES.items():
        if not cap.accepts:
            continue
        parts = [f"{role}: {'/'.join(types)}" for role, types in cap.accepts.items()]
        lines.append(f"- `{name}` — " + "; ".join(parts))
    lines += [
        "",
        "Keys inside a channel object:",
        "",
        f"- `field` — the column name. Required, except with `aggregate: \"count\"`.",
        f"- `type` — one of {_list(_vocab(models.Channel, 'type'))}.",
        f"- `aggregate` — one of {_list(_vocab(models.Channel, 'aggregate'))}.",
        f"- `time_unit` — one of {_list(_vocab(models.Channel, 'time_unit'))}; "
        "buckets a temporal field.",
        "- `bin` — `true`, an integer (max number of bins), or "
        "`{\"maxbins\": 10, \"step\": 5}`.",
        f"- `scale` — one of {_list(_vocab(models.Channel, 'scale'))}.",
        "- `title` — axis or legend label for this channel.",
        "",
        "Extra keys on specific roles: `color.scheme` (palette override), "
        "`size.range` ([min, max] marker area in points²), `facet.columns` "
        "(0 = automatic grid), `facet.share_x`, `facet.share_y`.",
    ]
    return "\n".join(lines)


def _data() -> str:
    return "\n".join([
        "## data — filtering, sorting, limiting",
        "",
        "```json",
        json.dumps({"data": {
            "filters": [{"field": "region", "op": "in", "value": ["North", "South"]}],
            "sort": "-y",
            "limit": 10,
        }}, indent=2),
        "```",
        "",
        f"- `filters[].op` — one of {_list(_vocab(models.Filter, 'op'))}.",
        "  `in`/`not_in` take a list; `between` takes `[min, max]`; "
        "`isnull`/`notnull` take no `value`.",
        "- `sort` — an object with `by` (`\"x\"`, `\"y\"`, or a column name) and "
        f"`order` ({_list(_vocab(models.Sort, 'order'))}), or the shorthand "
        "`\"-y\"` for descending by `y`.",
        "- `limit` — keeps the first N categories **after** sorting. "
        "Use it with `sort` for a top-N.",
    ])


def _style() -> str:
    style_fields = models.Style.model_fields
    lines = ["## style — presentation", "", "| key | values | default |",
             "| --- | --- | --- |"]
    enum_hints = {
        "palette": tuple(sorted(PALETTES)),
        "theme": tuple(sorted(THEMES)),
    }
    for name, info in style_fields.items():
        values = enum_hints.get(name) or _vocab(models.Style, name)
        if values:
            shown = _list(values)
        elif name == "figsize":
            shown = "[width, height] in inches"
        elif info.annotation is bool:
            shown = "`true` / `false`"
        else:
            shown = "free text"
        lines.append(f"| `{name}` | {shown} | `{info.default!r}` |")
    lines += [
        "",
        "`stacked` applies to `bar` and `area`; `orientation: \"horizontal\"` "
        "flips the bars (long category labels read better that way).",
    ]
    return "\n".join(lines)


def _output() -> str:
    fields = models.Output.model_fields
    return "\n".join([
        "## output",
        "",
        f"- `format` — one of {_list(_vocab(models.Output, 'format'))}. "
        f"Default `{fields['format'].default}`.",
        f"- `dpi` — {fields['dpi'].default} by default.",
        "- `path` — write the file here.",
        "- `transparent` — draw on a transparent surface.",
    ])


def _flat() -> str:
    by_target: dict[str, list[str]] = {}
    for alias, path in dialects._CHANNEL_KEYS.items():
        by_target.setdefault(".".join(path), []).append(alias)
    for alias, path in dialects._DATA_KEYS.items():
        by_target.setdefault(".".join(path), []).append(alias)

    lines = [
        "## The flat dialect",
        "",
        "A shorter form is accepted and normalized into the shape above. Both are",
        "equally valid; when a contract carries both, the canonical block wins.",
        "",
        "```json",
        json.dumps({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                    "agg": "sum", "title": "Revenue by region"}, indent=2),
        "```",
        "",
        "| canonical path | accepted top-level keys |",
        "| --- | --- |",
    ]
    for target, aliases in by_target.items():
        lines.append(f"| `{target}` | {_list(sorted(aliases))} |")
    lines += [
        "",
        f"`viz_type` itself may be spelled "
        + ", ".join(f"`{k}`" for k in sorted(dialects._VIZ_ALIASES)) + ".",
        "",
        "`viz_type` synonyms: "
        + ", ".join(f"`{k}` → `{v}`" for k, v in sorted(dialects._VIZ_VALUES.items()))
        + ".",
        "",
        f"These `style` keys are also accepted at the top level: "
        f"{_list(dialects._STYLE_KEYS)}. "
        f"And these `output` keys: {_list(sorted(dialects._OUTPUT_KEYS))}, `format`.",
    ]
    return "\n".join(lines)


def _vega_lite() -> str:
    """The Vega-Lite section — the tables in `dialects`, rendered.

    Worth its space only when the contract goes through `normalize()`. An agent
    whose output is parsed straight into `Spec` (a pydantic `output_type`, say)
    should leave this section out: there the canonical spelling is the only one
    that exists.
    """
    lines = [
        "## Vega-Lite spellings",
        "",
        "If you know Vega-Lite, write it and it will be translated. The canonical",
        "spec above is deliberately shaped like it — same `encoding`, same channel",
        "roles, same field definitions — so most of a Vega-Lite chart already is a",
        "valid contract.",
        "",
        "Accepted, and what each becomes:",
        "",
        "| Vega-Lite | here |",
        "| --- | --- |",
        "| `mark` (a string, or `{\"type\": ...}`) | `viz_type` |",
    ]
    marks = sorted(dialects._VL_MARK_VALUES)
    for mark in sorted(dialects._VL_MARK_VALUES):
        lines.append(f"| `\"mark\": \"{mark}\"` | "
                     f"`\"viz_type\": \"{dialects._VIZ_VALUES[mark]}\"` |")
    for name, role in sorted(dialects._VL_CHANNELS.items()):
        lines.append(f"| `encoding.{name}` | `encoding.{role}` |")
    lines += [
        "| `timeUnit` | `time_unit`; the `year…` forms map to the bucket they name |",
        f"| `\"type\": \"Q\"` / `\"N\"` / `\"O\"` / `\"T\"` | "
        f"{_list(_vocab(models.Channel, 'type'))} |",
        f"| {_list(sorted(dialects._VL_AGGREGATES))} | "
        + ", ".join(f"`{dialects._VL_AGGREGATES[a]}`"
                    for a in sorted(dialects._VL_AGGREGATES)) + " |",
        "| `scale: {\"type\": \"log\"}` | `scale: \"log\"` |",
        "| `axis: {\"title\": …}`, `legend: {\"title\": …}` | the channel's `title` |",
        "| a channel's `sort` (`\"-y\"`, `\"descending\"`, `{\"field\": …}`) | `data.sort` |",
        "| a channel's `stack` | `style.stacked` |",
        f"| `width` and `height`, in pixels | `style.figsize`, in inches "
        f"(at {dialects.VL_PIXELS_PER_INCH:.0f} px/inch) |",
        "| `$schema` | dropped; it names a Vega-Lite version, and this is not one |",
        "",
        "**Not accepted**, because there is no equivalent — each fails with a hint",
        "pointing at the nearest thing that exists:",
        "",
    ]
    for name, instead in dialects.VL_UNSUPPORTED.items():
        lines.append(f"- `{name}` — {instead}")
    lines += [
        "",
        "And `data` here is not Vega-Lite's `data`: the DataFrame is passed to the",
        "renderer separately, so this block holds filters, sorting and limits only.",
    ]
    return "\n".join(lines)


def _rules() -> str:
    return "\n".join([
        "## Rules the validator enforces",
        "",
        "1. Every `field` must be a column that exists in the DataFrame. "
        "This is the most common failure; use the column list verbatim, "
        "including its capitalization.",
        "2. Unknown keys are rejected — the contract is closed, not a free-form object.",
        "3. A channel needs `field` unless its `aggregate` is `count`.",
        f"4. {_list(sorted(NUMERIC_ONLY))} only apply to numeric columns; "
        "`count` and `nunique` work on anything.",
        "5. **On a chart marked `aggregates` above, set the measure's "
        "`aggregate`.** The data is one row per record, so a category or a date "
        "appears many times and there is no single value to draw. `sum` is the "
        "right default for amounts and counts of things, `mean` for rates, "
        "scores and ratios. `scatter` and `hist` are the exception: they draw "
        "rows, and must not aggregate.",
        "6. A channel's `type` must be one the chart accepts for that role "
        "(see the per-type list above).",
        "7. `time_unit` and `scale: log` require a temporal and a positive "
        "numeric column respectively.",
        "",
        "Errors come back as objects with `code`, `path`, `message`, `hint` and",
        "`did_you_mean`. When you receive them, fix the contract at `path` and",
        "resend the whole contract — do not explain, do not apologize.",
    ])


def _example() -> str:
    return "\n".join([
        "## A worked example",
        "",
        "*\"monthly revenue by region for the last two regions, biggest first\"*",
        "",
        "```json",
        json.dumps({
            "viz_type": "line",
            "encoding": {
                "x": {"field": "date", "type": "temporal", "time_unit": "month"},
                "y": {"field": "revenue", "type": "quantitative", "aggregate": "sum"},
                "color": {"field": "region", "type": "nominal"},
            },
            "data": {"sort": {"by": "y", "order": "desc"}, "limit": 2},
            "style": {"title": "Monthly revenue by region"},
        }, indent=2),
        "```",
    ])


_SECTIONS = {
    "overview": _overview,
    "shape": _shape,
    "types": _types,
    "channels": _channels,
    "data": _data,
    "style": _style,
    "output": _output,
    "flat": _flat,
    "vega_lite": _vega_lite,
    "rules": _rules,
    "example": _example,
}


def sections(include: tuple[str, ...] | None = None) -> dict[str, str]:
    """Each section of the briefing, rendered, in order."""
    names = include or SECTION_NAMES
    unknown = set(names) - set(_SECTIONS)
    if unknown:
        raise ValueError(f"unknown section(s): {sorted(unknown)}; "
                         f"available: {list(SECTION_NAMES)}")
    return {name: _SECTIONS[name]() for name in SECTION_NAMES if name in names}


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def contract(
    df: pd.DataFrame | None = None,
    *,
    format: Format = "markdown",
    include: tuple[str, ...] | None = None,
    examples: int = 3,
) -> str | dict:
    """The whole contract, ready to put in a prompt.

    With a `df`, the real columns are described first: naming them removes most
    COLUMN_NOT_FOUND failures, which dominate everything else.
    """
    if format == "json":
        return {
            "version": Spec.model_fields["version"].default,
            "schema": Spec.model_json_schema(mode="validation"),
            "capabilities": _capabilities_json(),
            "vocabulary": {k: list(v) for k, v in vocabulary().items()},
            "flat_dialect": _flat_json(),
            "data": _dataframe_json(df, examples) if df is not None else None,
        }
    if format != "markdown":
        raise ValueError(f"unknown format {format!r}; use 'markdown' or 'json'")

    parts = ["# The visualization contract", ""]
    if df is not None:
        parts += [_dataframe_section(df, examples), ""]
    for text in sections(include).values():
        parts += [text, ""]
    return "\n".join(parts).rstrip() + "\n"


def _capabilities_json() -> dict:
    installed = available()
    return {
        name: {
            "required": list(cap.required),
            "optional": list(cap.optional),
            "accepts": {k: list(v) for k, v in cap.accepts.items()},
            "aggregates": cap.aggregates,
            "measure": cap.measure,
            "description": cap.description,
            "backends": installed.get(name, []),
        }
        for name, cap in CAPABILITIES.items()
    }


def _flat_json() -> dict:
    return {
        "channel_keys": {k: list(v) for k, v in dialects._CHANNEL_KEYS.items()},
        "data_keys": {k: list(v) for k, v in dialects._DATA_KEYS.items()},
        "style_keys": list(dialects._STYLE_KEYS),
        "output_keys": list(dialects._OUTPUT_KEYS),
        "viz_type_aliases": dict(dialects._VIZ_ALIASES),
        "viz_type_synonyms": dict(dialects._VIZ_VALUES),
    }


def _dataframe_json(df: pd.DataFrame, examples: int) -> dict:
    from ..api import describe_dataframe

    return describe_dataframe(df, examples)


def _dataframe_section(df: pd.DataFrame, examples: int) -> str:
    from ..agent import columns

    return ("## The data\n\n```\n" + columns(df, examples)
            + "\n```\n\nUse these column names exactly as written, "
              "capitalization included.")


# --------------------------------------------------------------------------
# The guarantee that the document keeps up
# --------------------------------------------------------------------------


def coverage() -> dict[str, list[str]]:
    """Vocabulary values the briefing never mentions, per group.

    Empty means the document covers everything the contract accepts. A test
    asserts that, so declaring a new `Literal` member and leaving it out of the
    briefing breaks the build instead of silently shipping a prompt that hides
    a feature from the model.
    """
    text = contract()
    assert isinstance(text, str)
    missing: dict[str, list[str]] = {}
    for group, values in vocabulary().items():
        absent = [v for v in values if f"`{v}`" not in text]
        if absent:
            missing[group] = absent
    for key in list(dialects.KNOWN_KEYS) + list(CAPABILITIES):
        if f"`{key}`" not in text:
            missing.setdefault("keys", []).append(key)
    return missing
