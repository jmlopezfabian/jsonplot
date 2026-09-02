# jsonplot

A JSON contract and a `DataFrame` go in; a matplotlib figure comes out.

```python
import jsonplot as jp

spec = {
    "viz_type": "bar",
    "x_axis": "region",
    "y_axis": "revenue",
    "agg": "sum",
    "title": "Revenue by region",
}
fig = jp.plot(spec, df)
```

Built for contracts written by an agent: a spec can be validated before anything
is drawn, and failures come back as structured objects (`code`, `path`, `hint`,
`did_you_mean`) rather than tracebacks.

```python
errs = jp.validate(spec, df)          # -> list[SpecError], draws nothing
ctx  = jp.describe_dataframe(df)      # -> column summary for the prompt
```

## Why a contract instead of generated code

Asking a model for a chart usually means asking it for matplotlib code: you
execute arbitrary code, it fails in unpredictable ways, and there is no way to
check the request before running it. A contract inverts that. The agent produces
**data**, not code — an object declaring the chart type and which column goes in
which visual channel — and the framework is the only thing that touches
matplotlib. That buys three things generated code cannot: the request can be
validated up front, it can be versioned and cached like any other data, and when
it is wrong the failure is actionable.

## Install

```bash
uv sync            # or: pip install -e ".[seaborn]"
```

## Two dialects

The flat dialect is what an agent writes first. It normalizes into the canonical
spec, which is what the framework actually executes:

```json
{"viz_type": "bar", "x_axis": "date", "y_axis": "revenue",
 "group_by": "region", "agg": "sum"}
```

```json
{
  "viz_type": "bar",
  "encoding": {
    "x":     {"field": "date",    "type": "temporal"},
    "y":     {"field": "revenue", "type": "quantitative", "aggregate": "sum"},
    "color": {"field": "region",  "type": "nominal"}
  }
}
```

Both are accepted everywhere. When a contract carries both, the canonical block
wins.

## Chart types

`bar`, `line`, `area`, `scatter`, `hist`, `box` on matplotlib; `bar`, `line`,
`scatter`, `hist`, `box`, `violin` on seaborn. Channels: `x`, `y`, `color`,
`size`, `style`, `facet`, with aggregation, `time_unit`, `bin`, filters, sorting,
limits, stacking and horizontal orientation.

## From the terminal

```bash
jsonplot render contract.json data.csv -o chart.png
jsonplot validate contract.json data.csv   # exits 1 and writes the errors as JSON
jsonplot describe data.csv                 # the context block for the prompt
jsonplot schema                            # the contract's JSON Schema
jsonplot types                             # available types and backends
```

## Examples

```bash
uv run python examples/gallery.py out/
```

## Tests

```bash
uv run pytest
```

See `docs/architecture.md` for the pipeline, the error model, and how to add a
chart type or a backend.
