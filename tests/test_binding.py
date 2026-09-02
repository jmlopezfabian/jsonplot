"""Phases 02–04: the contract against the data."""

import pandas as pd

from jsonplot import validate
from jsonplot.binding.errors import Code


def codes(spec, df):
    return {e.code for e in validate(spec, df)}


def error(spec, df, code):
    return next(e for e in validate(spec, df) if e.code == code)


def test_a_missing_column_suggests_the_real_one(df):
    err = error({"viz_type": "bar", "x_axis": "regionn", "y_axis": "revenue",
                 "agg": "sum"}, df, Code.COLUMN_NOT_FOUND)
    assert err.path == "encoding.x.field"
    assert "region" in err.did_you_mean


def test_incompatible_type(df):
    err = error({"viz_type": "bar", "encoding": {
        "x": {"field": "region"},
        "y": {"field": "channel", "type": "quantitative"}}}, df, Code.TYPE_MISMATCH)
    assert "quantitative" in err.message


def test_aggregate_required_when_rows_repeat(df):
    err = error({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue"},
                df, Code.AGGREGATE_REQUIRED)
    assert err.path == "encoding.y.aggregate"
    assert "sum" in err.hint


def test_invalid_aggregate_over_text(df):
    err = error({"viz_type": "scatter", "x_axis": "price", "y_axis": "revenue",
                 "encoding": {"color": {"field": "region", "aggregate": "mean"}}},
                df, Code.AGGREGATE_INVALID)
    assert "count" in err.hint


def test_too_many_color_categories():
    # hues are assigned in fixed order and never recycled: the palette is the cap
    many = pd.DataFrame({"cat": [f"c{i}" for i in range(30)] * 4,
                         "series": [f"s{i}" for i in range(30)] * 4,
                         "v": range(120)})
    err = error({"viz_type": "bar", "x_axis": "cat", "y_axis": "v",
                 "agg": "sum", "group_by": "series"}, many,
                Code.CARDINALITY_TOO_HIGH)
    assert "facet" in err.hint


def test_a_quantitative_color_on_bars_is_a_type_error(df):
    err = error({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                 "agg": "sum", "group_by": "price"}, df, Code.TYPE_MISMATCH)
    assert "nominal" in err.hint


def test_a_quantitative_color_does_not_count_as_series(df):
    spec = {"viz_type": "scatter", "x_axis": "price", "y_axis": "revenue",
            "encoding": {"color": {"field": "satisfaction"}}}
    assert validate(spec, df) == []


def test_unsupported_channel(df):
    err = error({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                 "agg": "sum", "size_by": "price"}, df, Code.CHANNEL_NOT_SUPPORTED)
    assert "color" in err.hint


def test_missing_required_channel(df):
    err = error({"viz_type": "bar", "x_axis": "region"}, df, Code.MISSING_CHANNEL)
    assert err.path == "encoding.y"


def test_filters_that_leave_no_rows(df):
    err = error({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                 "agg": "sum",
                 "filters": [{"field": "region", "op": "eq", "value": "Atlantis"}]},
                df, Code.EMPTY_RESULT)
    assert "region" in err.hint


def test_every_error_is_collected(df):
    spec = {"viz_type": "bar", "x_axis": "regionn", "y_axis": "revenuu",
            "agg": "sum"}
    assert codes(spec, df) == {Code.COLUMN_NOT_FOUND}
    assert len(validate(spec, df)) == 2


def test_scatter_does_not_require_aggregation(df):
    assert validate({"viz_type": "scatter", "x_axis": "price",
                     "y_axis": "revenue"}, df) == []


def test_time_unit_on_a_non_temporal_column(df):
    err = error({"viz_type": "line", "x_axis": "region", "y_axis": "revenue",
                 "agg": "sum", "time_unit": "month"}, df, Code.TYPE_MISMATCH)
    assert "to_datetime" in err.hint


def test_without_a_dataframe_only_the_shape_is_checked():
    assert validate({"viz_type": "bar", "x_axis": "missing",
                     "y_axis": "also_missing"}) == []


def test_errors_are_serializable(df):
    errs = validate({"viz_type": "bar", "x_axis": "nope", "y_axis": "revenue",
                     "agg": "sum"}, df)
    d = errs[0].to_dict()
    assert set(d) >= {"code", "path", "message"}
    # empty keys do not travel: the JSON the model sees carries no noise
    assert "did_you_mean" not in d
    with_suggestion = validate({"viz_type": "bar", "x_axis": "regio",
                                "y_axis": "revenue", "agg": "sum"}, df)[0].to_dict()
    assert with_suggestion["did_you_mean"][0] == "region"
