"""Phase 07: the contract, written out — and kept in step with the code.

These tests are the mechanism, not decoration. The briefing is only worth
putting in a prompt if it cannot fall behind the framework, so what is checked
here is mostly that: add a chart type, an aggregation, a palette or an alias
without documenting it, and one of these fails.
"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import jsonplot as jp
from jsonplot import agent
from jsonplot.spec import briefing
from jsonplot.spec.briefing import SECTION_NAMES
from jsonplot.spec.capabilities import CAPABILITIES, Capability

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs" / "CONTRACT.md"


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def test_the_briefing_covers_every_value_the_contract_accepts():
    """The candado: no vocabulary member may go undocumented.

    `coverage()` walks the Literals in the models plus the palettes, themes and
    dialect keys, and reports what the text never mentions. A new member with
    no prose lands here, not in front of a model.
    """
    assert briefing.coverage() == {}


def test_the_vocabulary_is_read_off_the_models():
    vocab = briefing.vocabulary()
    assert "sum" in vocab["Channel.aggregate"]
    assert "between" in vocab["Filter.op"]
    assert set(vocab["Spec.viz_type"]) == set(CAPABILITIES)
    assert "default" in vocab["palette"] and "dark" in vocab["theme"]


def test_every_section_is_reachable_and_ordered():
    assert list(briefing.sections()) == list(SECTION_NAMES)
    only = briefing.sections(("rules", "types"))
    assert list(only) == ["types", "rules"]           # declaration order wins
    with pytest.raises(ValueError, match="unknown section"):
        briefing.sections(("nope",))


def test_the_json_form_is_serializable_and_complete():
    doc = jp.contract(format="json")
    json.dumps(doc)
    assert doc["schema"] == jp.json_schema()
    assert doc["capabilities"]["bar"]["required"] == ["x", "y"]
    assert doc["capabilities"]["bar"]["backends"]        # installed here
    assert doc["flat_dialect"]["channel_keys"]["x_axis"] == ["encoding", "x", "field"]
    assert doc["data"] is None


def test_the_data_block_names_the_real_columns(df):
    text = jp.contract(df)
    for col in df.columns:
        assert col in text
    assert jp.contract(df, format="json")["data"]["n_rows"] == len(df)


def test_an_unknown_format_is_refused():
    with pytest.raises(ValueError, match="unknown format"):
        jp.contract(format="yaml")


# --------------------------------------------------------------------------
# Dynamic: what the framework grows, the briefing grows
# --------------------------------------------------------------------------


def test_a_new_chart_type_appears_without_editing_the_text(monkeypatch):
    cap = Capability(
        required=("x", "y"), optional=("color",),
        accepts={"x": ("nominal",)}, aggregates=True, measure="y",
        description="A made-up type, for this test only.",
    )
    monkeypatch.setitem(CAPABILITIES, "sunburst", cap)
    text = jp.contract()
    assert "`sunburst`" in text
    assert "A made-up type, for this test only." in text
    assert "**not installed**" in text          # no renderer registered for it


def test_a_new_palette_and_a_new_alias_appear_too(monkeypatch):
    from jsonplot.spec import dialects
    from jsonplot.theme import PALETTES, palettes

    monkeypatch.setitem(PALETTES, "neon", palettes.DEFAULT)
    monkeypatch.setitem(dialects._CHANNEL_KEYS, "split_by",
                        ("encoding", "facet", "field"))
    text = jp.contract()
    assert "`neon`" in text
    assert "`split_by`" in text


def test_a_backend_that_is_not_installed_is_not_advertised(monkeypatch):
    monkeypatch.setattr(briefing, "available",
                        lambda: {"bar": ["matplotlib"], "line": ["matplotlib"]})
    text = jp.contract()
    assert "Backends installed here: `matplotlib`." in text
    types = briefing.sections(("types",))["types"]
    assert "| `seaborn`" not in types and "`matplotlib`, `seaborn`" not in types
    assert "**not installed**" in types          # box, violin, ...


def test_a_capability_change_reaches_the_channel_table(monkeypatch):
    narrowed = replace(CAPABILITIES["scatter"], optional=("color",))
    monkeypatch.setitem(CAPABILITIES, "scatter", narrowed)
    types_section = briefing.sections(("types",))["types"]
    line = next(ln for ln in types_section.splitlines() if ln.startswith("| `scatter`"))
    assert "`size`" not in line


# --------------------------------------------------------------------------
# Where it is consumed
# --------------------------------------------------------------------------


def test_the_tool_definition_carries_the_briefing():
    tool = jp.tool_definition()
    assert tool["input_schema"] == jp.json_schema()
    for cue in ("| `bar` |", "Rules the validator enforces", "`quantitative`"):
        assert cue in tool["description"]
    short = jp.tool_definition(sections=())["description"]
    assert "bar" in short and len(short) < len(tool["description"])


def test_agent_context_is_the_briefing_plus_the_data(df):
    text = agent.context(df)
    assert "## The data" in text and "## Chart types" in text
    trimmed = agent.context(df, sections=("types", "rules"))
    assert "## Chart types" in trimmed
    assert "## The flat dialect" not in trimmed
    assert len(trimmed) < len(text)


def test_columns_alone_stays_small(df):
    text = agent.columns(df)
    assert "region" in text
    assert "viz_type" not in text        # this block is only about the data


# --------------------------------------------------------------------------
# The committed snapshot
# --------------------------------------------------------------------------


def _cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "jsonplot.cli", *args],
                          capture_output=True, text=True, cwd=ROOT)


@pytest.mark.skipif(
    "seaborn" not in {b for bs in jp.supported().values() for b in bs},
    reason="the snapshot is generated with every optional backend installed",
)
def test_the_committed_snapshot_is_up_to_date():
    """`docs/CONTRACT.md` is generated; this fails when it drifts."""
    done = _cli("contract", "-o", str(SNAPSHOT), "--check")
    assert done.returncode == 0, done.stderr + "\n" + done.stdout


def test_the_check_flag_reports_a_stale_file(tmp_path):
    stale = tmp_path / "CONTRACT.md"
    assert _cli("contract", "-o", str(stale), "--check").returncode == 1  # missing
    stale.write_text("out of date", encoding="utf-8")
    done = _cli("contract", "-o", str(stale), "--check")
    assert done.returncode == 1 and "out of date" in done.stderr
    assert _cli("contract", "-o", str(stale)).returncode == 0
    assert _cli("contract", "-o", str(stale), "--check").returncode == 0


def test_the_cli_serves_sections_and_json():
    assert "## Chart types" in _cli("contract", "--section", "types").stdout
    assert json.loads(_cli("contract", "--json").stdout)["version"] == "1.0"
    bad = _cli("contract", "--section", "nope")
    assert bad.returncode == 2 and "unknown section" in bad.stderr
