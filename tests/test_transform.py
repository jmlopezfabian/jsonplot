"""Phase 03: the plot frame.

These tests draw nothing: they compare the plot frame against the equivalent
hand-written groupby. If the framework aggregates wrongly, it shows up here and
not in a pixel.
"""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from jsonplot import build_frame

CASES = [
    ("sum by category",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum"},
     lambda df: df.groupby("region", as_index=False)["revenue"].sum()),
    ("mean by category",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "price", "agg": "mean"},
     lambda df: df.groupby("region", as_index=False)["price"].mean()),
    ("median by category",
     {"viz_type": "bar", "x_axis": "channel", "y_axis": "price", "agg": "median"},
     lambda df: df.groupby("channel", as_index=False)["price"].median()),
    ("distinct values",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "channel", "agg": "nunique"},
     lambda df: df.groupby("region", as_index=False)["channel"].nunique()),
    ("two grouping keys",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum",
      "group_by": "channel"},
     lambda df: df.groupby(["region", "channel"], as_index=False)["revenue"].sum()),
    ("filter before aggregating",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum",
      "filters": [{"field": "channel", "op": "eq", "value": "Online"}]},
     lambda df: (df[df["channel"] == "Online"]
                 .groupby("region", as_index=False)["revenue"].sum())),
    ("max",
     {"viz_type": "bar", "x_axis": "region", "y_axis": "units", "agg": "max"},
     lambda df: df.groupby("region", as_index=False)["units"].max()),
]


@pytest.mark.parametrize("name,spec,manual", CASES, ids=[c[0] for c in CASES])
def test_aggregation_matches_the_groupby(df, name, spec, manual):
    got = build_frame(spec, df)
    expected = manual(df).sort_values(list(manual(df).columns[:-1])).reset_index(drop=True)
    got_cmp = got.copy()
    got_cmp.columns = list(expected.columns)
    assert_frame_equal(got_cmp.sort_values(list(expected.columns[:-1]))
                       .reset_index(drop=True), expected, check_dtype=False)


def test_count_without_a_field(df):
    pf = build_frame({"viz_type": "bar", "x_axis": "region",
                      "encoding": {"y": {"aggregate": "count"}}}, df)
    assert pf.set_index("x")["y"].to_dict() == df["region"].value_counts().to_dict()


def test_time_unit_groups_by_month(df):
    pf = build_frame({"viz_type": "line", "x_axis": "date", "y_axis": "revenue",
                      "agg": "sum", "time_unit": "month"}, df)
    expected = df.groupby(df["date"].dt.to_period("M"))["revenue"].sum()
    assert len(pf) == len(expected)
    assert pf["y"].sum() == pytest.approx(df["revenue"].sum())


def test_columns_are_named_after_the_channels(df):
    pf = build_frame({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                      "agg": "sum", "group_by": "channel", "facet_by": "channel"}, df)
    assert set(pf.columns) == {"x", "y", "color", "facet"}


def test_the_default_order_is_ascending_on_x(df):
    pf = build_frame({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                      "agg": "sum"}, df)
    assert list(pf["x"]) == sorted(pf["x"])


def test_descending_sort_plus_limit_gives_the_top_n(df):
    pf = build_frame({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                      "agg": "sum", "sort": "-y", "limit": 2}, df)
    every = build_frame({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                         "agg": "sum"}, df)
    assert len(pf) == 2
    assert list(pf["x"]) == list(every.nlargest(2, "y")["x"])


def test_the_limit_does_not_split_groups(df):
    pf = build_frame({"viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
                      "agg": "sum", "group_by": "channel", "sort": "-y",
                      "limit": 2}, df)
    assert pf["x"].nunique() == 2
    assert len(pf) == 4  # two categories × two channels, none half-drawn


def test_bin_discretizes_into_midpoints(df):
    pf = build_frame({"viz_type": "bar", "y_axis": "revenue", "agg": "count",
                      "encoding": {"x": {"field": "price", "bin": {"maxbins": 5}},
                                   "y": {"aggregate": "count"}}}, df)
    assert pf["x"].nunique() <= 6
    assert pd.api.types.is_numeric_dtype(pf["x"])
    assert pf["y"].sum() == len(df)


def test_rows_without_a_value_are_not_drawn():
    df = pd.DataFrame({"a": ["x", "y", None, "z"], "b": [1.0, None, 3.0, 4.0]})
    pf = build_frame({"viz_type": "scatter",
                      "encoding": {"x": {"field": "b"}, "y": {"field": "b"}}}, df)
    assert len(pf) == 3
