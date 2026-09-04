"""The Vega-Lite dialect.

Vega-Lite is a decade old and everywhere in a model's training data, and this
contract was shaped after it, so accepting its spelling is nearly free. What
these tests pin down is the translation *and its boundary*: the parts with no
equivalent here must fail, with a hint, rather than be quietly ignored.
"""

import pandas as pd
import pytest

import jsonplot as jp
from jsonplot.binding.errors import Code
from jsonplot.spec import parse_spec
from jsonplot.spec.dialects import VL_UNSUPPORTED, normalize


@pytest.fixture(scope="module")
def frame():
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05", "2024-02-11", "2024-02-20", "2024-03-02"]),
        "region": ["North", "South", "North", "South"],
        "channel": ["Store", "Online", "Online", "Store"],
        "price": [10.0, 20.0, 30.0, 40.0],
        "revenue": [100.0, 200.0, 300.0, 400.0],
    })


def canonical(raw: dict):
    spec, errors = parse_spec(raw)
    assert not errors, errors
    return spec


# --------------------------------------------------------------------------
# What translates
# --------------------------------------------------------------------------


def test_a_vega_lite_contract_is_a_contract(frame):
    """Straight out of the Vega-Lite docs, near enough."""
    spec = canonical({
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": "bar",
        "width": 800,
        "height": 400,
        "encoding": {
            "x": {"field": "date", "type": "T", "timeUnit": "yearmonth"},
            "y": {"field": "revenue", "type": "Q", "aggregate": "average"},
            "color": {"field": "region", "type": "N"},
        },
    })
    assert spec.viz_type == "bar"
    assert spec.encoding.x.type == "temporal" and spec.encoding.x.time_unit == "month"
    assert spec.encoding.y.aggregate == "mean"
    assert spec.style.figsize == (8.0, 4.0)
    assert jp.validate(spec, frame) == []


@pytest.mark.parametrize("mark, viz_type", [
    ("point", "scatter"), ("circle", "scatter"), ("square", "scatter"),
    ("tick", "scatter"), ("trail", "line"), ("boxplot", "box"), ("bar", "bar"),
])
def test_marks(mark, viz_type):
    assert canonical({"mark": mark, "encoding": {"x": "a", "y": "b"}}).viz_type == viz_type


def test_a_mark_object_keeps_its_type():
    spec = canonical({"mark": {"type": "line", "point": True, "interpolate": "monotone"},
                      "encoding": {"x": "a", "y": "b"}})
    assert spec.viz_type == "line"


@pytest.mark.parametrize("name, role", [
    ("shape", "style"), ("strokeDash", "style"), ("row", "facet"), ("column", "facet"),
])
def test_channel_names(name, role):
    spec = canonical({"mark": "point", "encoding": {"x": "a", "y": "b",
                                                    name: {"field": "c"}}})
    assert getattr(spec.encoding, role).field == "c"


def test_two_vega_lite_channels_on_one_role_do_not_overwrite_each_other():
    """`row` and `column` are both `facet` here; the second is dropped, not merged."""
    spec = canonical({"mark": "bar", "encoding": {"x": "a", "y": "b",
                                                  "row": {"field": "region"},
                                                  "column": {"field": "channel"}}})
    assert spec.encoding.facet.field == "region"


def test_a_channel_sort_becomes_a_data_sort():
    assert canonical({"mark": "bar", "encoding": {
        "x": {"field": "region", "sort": "-y"}, "y": {"field": "revenue", "aggregate": "sum"},
    }}).data.sort.model_dump() == {"by": "y", "order": "desc"}

    assert canonical({"mark": "bar", "encoding": {
        "x": {"field": "region", "sort": "descending"}, "y": {"field": "revenue", "aggregate": "sum"},
    }}).data.sort.model_dump() == {"by": "x", "order": "desc"}

    assert canonical({"mark": "bar", "encoding": {
        "x": {"field": "region", "sort": {"field": "revenue", "order": "descending"}},
        "y": {"field": "revenue", "aggregate": "sum"},
    }}).data.sort.model_dump() == {"by": "revenue", "order": "desc"}


def test_an_explicit_sort_beats_the_channel_one():
    spec = canonical({"mark": "bar", "sort": "x", "encoding": {
        "x": {"field": "region", "sort": "-y"}, "y": {"field": "revenue", "aggregate": "sum"},
    }})
    assert spec.data.sort.by == "x"


@pytest.mark.parametrize("stack, expected", [("zero", True), ("normalize", True),
                                             (True, True), (None, False)])
def test_stack_becomes_style_stacked(stack, expected):
    spec = canonical({"mark": "bar", "encoding": {
        "x": "region", "y": {"field": "revenue", "aggregate": "sum", "stack": stack},
        "color": "channel",
    }})
    assert spec.style.stacked is expected


def test_scale_axis_and_legend_objects():
    spec = canonical({"mark": "point", "encoding": {
        "x": {"field": "price", "scale": {"type": "log"}, "axis": {"title": "Unit price"}},
        "y": {"field": "revenue"},
        "color": {"field": "region", "legend": {"title": "Region"}},
    }})
    assert spec.encoding.x.scale == "log"
    assert spec.encoding.x.title == "Unit price"
    assert spec.encoding.color.title == "Region"


def test_a_scale_this_framework_does_not_have_is_reported_not_swallowed():
    """Only `{"type": ...}` translates; a real scale config must not vanish."""
    _, errors = parse_spec({"mark": "point", "encoding": {
        "x": {"field": "a", "scale": {"type": "log", "domain": [1, 100]}}, "y": "b"}})
    assert errors and errors[0].path.startswith("encoding.x.scale")


def test_the_canonical_spelling_still_wins():
    spec = canonical({"mark": "bar", "encoding": {
        "x": {"field": "date", "timeUnit": "yearmonth", "time_unit": "year"},
        "y": {"field": "revenue", "aggregate": "sum"}}})
    assert spec.encoding.x.time_unit == "year"


def test_a_vega_lite_contract_draws(frame):
    figure = jp.plot({
        "mark": "bar",
        "encoding": {
            "x": {"field": "region", "type": "N", "sort": "-y"},
            "y": {"field": "revenue", "type": "Q", "aggregate": "sum", "stack": "zero"},
            "color": {"field": "channel", "type": "N"},
        },
    }, frame)
    assert figure.axes


# --------------------------------------------------------------------------
# What does not, and says so
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(VL_UNSUPPORTED))
def test_the_unsupported_keys_fail_with_a_hint(key, frame):
    errors = jp.validate({"mark": "bar", key: {}, "encoding": {"x": "region",
                          "y": {"field": "revenue", "aggregate": "sum"}}}, frame)
    hit = [e for e in errors if e.path == key]
    assert hit, errors
    assert hit[0].code == Code.UNKNOWN_FIELD
    assert "Vega-Lite" in (hit[0].hint or "")
    assert VL_UNSUPPORTED[key] in hit[0].hint


def test_a_data_source_is_a_category_error_with_its_own_message(frame):
    errors = jp.validate({"mark": "bar", "data": {"url": "sales.csv"},
                          "encoding": {"x": "region",
                                       "y": {"field": "revenue", "aggregate": "sum"}}}, frame)
    assert errors[0].code == Code.UNKNOWN_FIELD
    assert errors[0].path == "data.url"
    assert "argument to plot()" in errors[0].hint


def test_an_unsupported_mark_lists_what_there_is():
    _, errors = parse_spec({"mark": "arc", "encoding": {"x": "a", "y": "b"}})
    assert errors[0].code == Code.INVALID_VALUE and errors[0].path == "viz_type"
    assert "bar" in errors[0].hint


def test_nothing_is_dropped_except_the_schema_pointer():
    """`$schema` is metadata about a spec language this is not; everything else
    that cannot be translated has to survive into the errors."""
    out = normalize({"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                     "mark": "bar", "transform": [{"filter": "datum.revenue > 1"}]})
    assert "$schema" not in out
    assert out["transform"] == [{"filter": "datum.revenue > 1"}]


def test_a_vega_lite_horizontal_bar_chart(frame):
    """Vega-Lite swaps the channels to turn a bar chart on its side."""
    spec = canonical({"mark": "bar", "encoding": {
        "x": {"field": "revenue", "type": "quantitative", "aggregate": "sum"},
        "y": {"field": "region", "type": "nominal"},
    }})
    assert spec.encoding.x.field == "region"
    assert spec.encoding.y.field == "revenue" and spec.encoding.y.aggregate == "sum"
    assert spec.style.orientation == "horizontal"
    assert jp.validate(spec, frame) == []


def test_the_swap_needs_the_contract_to_say_so():
    """Without declared types or an aggregate there is nothing to go on, and
    guessing from the data is the binder's job, not the dialect's."""
    spec = canonical({"mark": "bar", "encoding": {"x": {"field": "revenue"},
                                                  "y": {"field": "region"}}})
    assert spec.encoding.x.field == "revenue"
    assert spec.style.orientation == "vertical"


def test_the_swap_leaves_an_explicit_orientation_alone():
    spec = canonical({"mark": "bar", "orientation": "vertical", "encoding": {
        "x": {"field": "revenue", "type": "quantitative", "aggregate": "sum"},
        "y": {"field": "region", "type": "nominal"}}})
    assert spec.style.orientation == "vertical"


def test_a_normal_bar_chart_is_not_swapped():
    spec = canonical({"mark": "bar", "encoding": {
        "x": {"field": "region", "type": "nominal"},
        "y": {"field": "revenue", "type": "quantitative", "aggregate": "sum"}}})
    assert spec.encoding.x.field == "region"
    assert spec.style.orientation == "vertical"
