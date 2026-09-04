# Quickstart

## Install

=== "uv"

    ```bash
    uv add jsonplot            # or, in this repo: uv sync
    ```

=== "pip"

    ```bash
    pip install -e ".[seaborn,streamlit]"
    ```

`seaborn` and `streamlit` are optional: without them the library still draws
`bar`, `line`, `area`, `scatter`, `hist` and `box` on matplotlib.

## Draw something

```python
import pandas as pd
import jsonplot as jp

df = pd.read_csv("sales.csv")

fig = jp.plot({
    "viz_type": "bar",
    "x_axis": "region",
    "y_axis": "revenue",
    "agg": "sum",
    "title": "Revenue by region",
}, df)

fig.savefig("chart.png", dpi=150, bbox_inches="tight")
```

`plot` returns a `matplotlib.figure.Figure` unless the contract asks for
something else (`"format": "png" | "svg" | "base64"`).

## Three dialects, one meaning

The **flat** dialect is short and is what a model writes first:

```json
{"viz_type": "bar", "x_axis": "date", "y_axis": "revenue",
 "group_by": "region", "agg": "sum", "time_unit": "month"}
```

The **canonical** dialect is what the framework executes, and it is what scales
once color, faceting or per-channel aggregation appear:

```json
{
  "viz_type": "bar",
  "encoding": {
    "x":     {"field": "date",    "type": "temporal", "time_unit": "month"},
    "y":     {"field": "revenue", "type": "quantitative", "aggregate": "sum"},
    "color": {"field": "region",  "type": "nominal"}
  }
}
```

And **Vega-Lite** is accepted as well, because the canonical dialect was shaped
after it: `mark`, `timeUnit`, `shape`, `row`/`column`, `"type": "Q"`, a
channel-level `sort` or `stack`, `width`/`height` in pixels.

```json
{"mark": "bar",
 "encoding": {"x": {"field": "revenue", "type": "Q", "aggregate": "sum"},
              "y": {"field": "region", "type": "N"}}}
```

That draws horizontal bars: swapping the channels is how Vega-Lite says so.
What it has and this does not — `transform`, `layer`, `params`, a `data` source
— fails with a hint naming the nearest equivalent rather than being ignored.

All three are accepted everywhere, and they normalize into the canonical shape.
When a contract carries both spellings, the canonical one wins. The full
vocabulary is on [The contract](CONTRACT.md).

## Check before you draw

```python
errors = jp.validate(spec, df)      # -> list[SpecError], draws nothing
if errors:
    print(errors[0].code, errors[0].path, errors[0].did_you_mean)
    # COLUMN_NOT_FOUND encoding.y.field ['revenue']
```

`validate` returns every problem, not the first. With no DataFrame it checks the
shape alone. See [Errors](errors.md).

## See what it understood

`inspect` reports the normalized contract, what each channel resolved to, and
the exact frame that will be drawn — the fastest way to answer "why did it draw
*that*".

```python
report = jp.inspect(spec, df)
report["canonical"]      # the contract after normalization
report["channels"]       # dtype, inferred type and cardinality per channel
report["plot_frame"]     # columns and shape of the data being drawn
```

## The data that will be drawn

```python
jp.build_frame(spec, df)     # filters, aggregation, sorting and limits applied
#         x          y
# 0 Central  390340.21
# 1    East  412142.26
```

Useful for a table beside the chart, or for a test that asserts on numbers
rather than pixels.

## Next

- [Gallery](gallery.md) — every chart type, with its contract.
- [Driving it from an agent](agents.md) — the part this was built for.
- [From the terminal](cli.md) — the same thing without writing Python.
