# The visualization contract

## What you are producing

A **contract**: a JSON object that declares which column of an already-loaded
DataFrame goes in which visual channel. You are not writing plotting code, and
no code you write will be executed. The framework draws the figure.

Answer with the JSON object and nothing else. Unknown keys are rejected with
their exact path, so do not invent fields; every accepted key is listed below.

Backends installed here: `matplotlib`, `seaborn`.

## Shape

```json
{
  "viz_type": "bar",
  "backend": "matplotlib",
  "encoding": {
    "x": {
      "field": "<column>",
      "type": "nominal"
    },
    "y": {
      "field": "<column>",
      "type": "quantitative",
      "aggregate": "sum"
    }
  },
  "data": {
    "filters": [],
    "sort": null,
    "limit": null
  },
  "style": {
    "title": "<text>"
  },
  "output": {
    "format": "figure"
  }
}
```

Only `viz_type` and `encoding` are required; every other block has defaults. Note the `aggregate` on `y`: on a `bar` it is not optional (rule 5).
`version` is `1.0` and may be omitted; `backend` defaults to `matplotlib`; the `data`, `style` and `output` blocks are optional.
A channel may be written as a bare string — `"x": "region"` means
`{"field": "region"}`. `type` is inferred from the column dtype when omitted.

## Chart types

| viz_type | required | optional | aggregates | backends |
| --- | --- | --- | --- | --- |
| `bar` | `x`, `y` | `color`, `facet` | yes, over `y` | `matplotlib`, `seaborn` |
| `line` | `x`, `y` | `color`, `style`, `facet` | yes, over `y` | `matplotlib`, `seaborn` |
| `area` | `x`, `y` | `color`, `facet` | yes, over `y` | `matplotlib` |
| `scatter` | `x`, `y` | `color`, `size`, `style`, `facet` | no | `matplotlib`, `seaborn` |
| `hist` | `x` | `color`, `facet` | no | `matplotlib`, `seaborn` |
| `box` | `y` | `x`, `color`, `facet` | no | `matplotlib`, `seaborn` |
| `violin` | `y` | `x`, `color`, `facet` | no | `seaborn` |

Aggregating types (`bar`, `line`, `area`) need an `aggregate` on their measure — see rule 5. The others draw one mark per row.

What each one is for:

- `bar` — Grouped or stacked bars over a discrete axis.
- `line` — A continuous series; one line per color category.
- `area` — Like line, filled below the curve; supports stacking.
- `scatter` — One mark per row; no implicit aggregation.
- `hist` — Distribution of a quantitative field.
- `box` — Five-number summary per category.
- `violin` — Density per category. Requires the seaborn backend.

## Channels

Roles: `x`, `y`, `color`, `size`, `style`, `facet`. Which ones a chart accepts is in the table above.

Accepted scale types per role, by chart type (a role not listed accepts any):

- `bar` — x: nominal/ordinal/temporal/quantitative; y: quantitative; color: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `line` — y: quantitative; color: nominal/ordinal/temporal; style: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `area` — y: quantitative; color: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `scatter` — x: quantitative/temporal; y: quantitative; size: quantitative; color: quantitative/nominal/ordinal/temporal; style: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `hist` — x: quantitative/temporal; color: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `box` — x: nominal/ordinal; y: quantitative; color: nominal/ordinal/temporal; facet: nominal/ordinal/temporal
- `violin` — x: nominal/ordinal; y: quantitative; color: nominal/ordinal/temporal; facet: nominal/ordinal/temporal

Keys inside a channel object:

- `field` — the column name. Required, except with `aggregate: "count"`.
- `type` — one of `quantitative`, `nominal`, `ordinal`, `temporal`.
- `aggregate` — one of `sum`, `mean`, `median`, `min`, `max`, `count`, `nunique`, `std`.
- `time_unit` — one of `day`, `week`, `month`, `quarter`, `year`; buckets a temporal field.
- `bin` — `true`, an integer (max number of bins), or `{"maxbins": 10, "step": 5}`.
- `scale` — one of `linear`, `log`, `symlog`.
- `title` — axis or legend label for this channel.

Extra keys on specific roles: `color.scheme` (palette override), `size.range` ([min, max] marker area in points²), `facet.columns` (0 = automatic grid), `facet.share_x`, `facet.share_y`.

## data — filtering, sorting, limiting

```json
{
  "data": {
    "filters": [
      {
        "field": "region",
        "op": "in",
        "value": [
          "North",
          "South"
        ]
      }
    ],
    "sort": "-y",
    "limit": 10
  }
}
```

- `filters[].op` — one of `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `between`, `contains`, `isnull`, `notnull`.
  `in`/`not_in` take a list; `between` takes `[min, max]`; `isnull`/`notnull` take no `value`.
- `sort` — an object with `by` (`"x"`, `"y"`, or a column name) and `order` (`asc`, `desc`), or the shorthand `"-y"` for descending by `y`.
- `limit` — keeps the first N categories **after** sorting. Use it with `sort` for a top-N.

## style — presentation

| key | values | default |
| --- | --- | --- |
| `title` | free text | `None` |
| `subtitle` | free text | `None` |
| `x_label` | free text | `None` |
| `y_label` | free text | `None` |
| `legend_title` | free text | `None` |
| `palette` | `default`, `muted`, `safe3` | `'default'` |
| `theme` | `clean`, `dark` | `'clean'` |
| `figsize` | [width, height] in inches | `(10.0, 6.0)` |
| `grid` | `none`, `x`, `y`, `both` | `'y'` |
| `legend` | `auto`, `right`, `top`, `none` | `'auto'` |
| `stacked` | `true` / `false` | `False` |
| `orientation` | `vertical`, `horizontal` | `'vertical'` |
| `annotate` | `true` / `false` | `False` |

`stacked` applies to `bar` and `area`; `orientation: "horizontal"` flips the bars (long category labels read better that way).

## output

- `format` — one of `figure`, `png`, `svg`, `base64`. Default `figure`.
- `dpi` — 150 by default.
- `path` — write the file here.
- `transparent` — draw on a transparent surface.

## The flat dialect

A shorter form is accepted and normalized into the shape above. Both are
equally valid; when a contract carries both, the canonical block wins.

```json
{
  "viz_type": "bar",
  "x_axis": "region",
  "y_axis": "revenue",
  "agg": "sum",
  "title": "Revenue by region"
}
```

| canonical path | accepted top-level keys |
| --- | --- |
| `encoding.x.field` | `x`, `x_axis`, `xaxis` |
| `encoding.y.field` | `y`, `y_axis`, `yaxis` |
| `encoding.color.field` | `color_by`, `group_by`, `hue`, `series` |
| `encoding.size.field` | `size_by` |
| `encoding.style.field` | `style_by` |
| `encoding.facet.field` | `facet`, `facet_by` |
| `encoding.y.aggregate` | `agg`, `aggregate`, `aggregation` |
| `encoding.x.time_unit` | `freq`, `time_unit` |
| `encoding.x.bin.maxbins` | `bins` |
| `data.filters` | `filters`, `where` |
| `data.sort` | `sort`, `sort_by` |
| `data.limit` | `limit`, `top_n` |

`viz_type` itself may be spelled `chart_type`, `kind`, `plot_type`, `type`.

`viz_type` synonyms: `areachart` → `area`, `barh` → `bar`, `barplot` → `bar`, `bars` → `bar`, `boxplot` → `box`, `column` → `bar`, `histogram` → `hist`, `histplot` → `hist`, `linechart` → `line`, `lineplot` → `line`, `points` → `scatter`, `scatterplot` → `scatter`, `timeseries` → `line`, `violinplot` → `violin`.

These `style` keys are also accepted at the top level: `title`, `subtitle`, `x_label`, `y_label`, `legend_title`, `palette`, `theme`, `figsize`, `grid`, `legend`, `stacked`, `orientation`, `annotate`. And these `output` keys: `dpi`, `path`, `transparent`, `format`.

## Rules the validator enforces

1. Every `field` must be a column that exists in the DataFrame. This is the most common failure; use the column list verbatim, including its capitalization.
2. Unknown keys are rejected — the contract is closed, not a free-form object.
3. A channel needs `field` unless its `aggregate` is `count`.
4. `mean`, `median`, `std`, `sum` only apply to numeric columns; `count` and `nunique` work on anything.
5. **On a chart marked `aggregates` above, set the measure's `aggregate`.** The data is one row per record, so a category or a date appears many times and there is no single value to draw. `sum` is the right default for amounts and counts of things, `mean` for rates, scores and ratios. `scatter` and `hist` are the exception: they draw rows, and must not aggregate.
6. A channel's `type` must be one the chart accepts for that role (see the per-type list above).
7. `time_unit` and `scale: log` require a temporal and a positive numeric column respectively.

Errors come back as objects with `code`, `path`, `message`, `hint` and
`did_you_mean`. When you receive them, fix the contract at `path` and
resend the whole contract — do not explain, do not apologize.

## A worked example

*"monthly revenue by region for the last two regions, biggest first"*

```json
{
  "viz_type": "line",
  "encoding": {
    "x": {
      "field": "date",
      "type": "temporal",
      "time_unit": "month"
    },
    "y": {
      "field": "revenue",
      "type": "quantitative",
      "aggregate": "sum"
    },
    "color": {
      "field": "region",
      "type": "nominal"
    }
  },
  "data": {
    "sort": {
      "by": "y",
      "order": "desc"
    },
    "limit": 2
  },
  "style": {
    "title": "Monthly revenue by region"
  }
}
```
