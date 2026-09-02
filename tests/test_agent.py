"""Phase 06: the surface an agent consumes."""

import json

import jsonplot as jp
from jsonplot import agent
from jsonplot.binding.errors import Code


def test_the_schema_comes_from_the_models():
    schema = jp.json_schema()
    assert schema["properties"]["viz_type"]  # derived, not hand-written
    assert "encoding" in schema["required"]
    json.dumps(schema)  # must be serializable as-is


def test_the_tool_definition_lists_the_types():
    tool = jp.tool_definition()
    assert tool["input_schema"] == jp.json_schema()
    assert "bar" in tool["description"]


def test_describe_dataframe_fits_in_a_prompt(df):
    desc = jp.describe_dataframe(df)
    assert desc["n_rows"] == len(df)
    assert desc["columns"]["region"]["inferred_type"] == "nominal"
    assert desc["columns"]["date"]["inferred_type"] == "temporal"
    assert "min" in desc["columns"]["price"]
    json.dumps(desc)


def test_the_context_names_the_real_columns(df):
    text = agent.context(df)
    for col in df.columns:
        assert col in text


def test_inspect_explains_what_was_understood(df):
    report = jp.inspect({"viz_type": "bar", "x_axis": "region",
                         "y_axis": "revenue", "agg": "sum"}, df)
    assert report["valid"]
    assert report["canonical"]["encoding"]["y"]["aggregate"] == "sum"
    assert report["channels"]["x"]["n_unique"] == df["region"].nunique()
    assert report["plot_frame"]["columns"] == ["x", "y"]


def test_inspect_on_a_broken_contract(df):
    report = jp.inspect({"viz_type": "bar", "x_axis": "nope",
                         "y_axis": "revenue"}, df)
    assert not report["valid"]
    assert report["errors"][0]["code"] == Code.COLUMN_NOT_FOUND


def test_the_repair_loop_fixes_a_column(df):
    """The loop lives outside the framework; this checks it is made possible."""
    calls = []

    def fix(spec, errors):
        calls.append(errors)
        suggestion = errors[0]["did_you_mean"][0]
        return {**spec, "x_axis": suggestion}

    res = agent.repair({"viz_type": "bar", "x_axis": "regionn",
                        "y_axis": "revenue", "agg": "sum"}, df, fix)
    assert res.ok
    assert res.attempts == 2
    assert calls[0][0]["code"] == Code.COLUMN_NOT_FOUND


def test_the_repair_loop_gives_up_and_says_so(df):
    res = agent.repair({"viz_type": "bar", "x_axis": "nope", "y_axis": "revenue",
                        "agg": "sum"}, df, lambda spec, errors: spec,
                       max_attempts=2)
    assert not res.ok
    assert len(res.history) == 3
    assert "could not produce a figure" in res.report()


def test_errors_travel_as_json(df):
    errors = jp.validate({"viz_type": "bar", "x_axis": "regio",
                          "y_axis": "revenue", "agg": "sum"}, df)
    loaded = json.loads(agent.errors_as_json(errors))
    assert loaded[0]["code"] == Code.COLUMN_NOT_FOUND
    assert loaded[0]["did_you_mean"][0] == "region"
