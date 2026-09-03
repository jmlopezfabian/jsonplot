"""The Streamlit adapter.

Two levels: the unit level for theme resolution and figure hygiene, and
`AppTest`, which runs a real script through Streamlit's own runner — the only
way to know that what the app emits is an image and not a traceback.
"""

from __future__ import annotations

import io
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

pytest.importorskip("streamlit", reason="the Streamlit adapter is an extra")

import streamlit.config as config  # noqa: E402
from PIL import Image  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import jsonplot.streamlit as jps  # noqa: E402
from jsonplot.binding.errors import Code, SpecErrorGroup  # noqa: E402
from jsonplot.spec.models import Spec, Style  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

BAR = {"viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum"}
BROKEN = {"viz_type": "bar", "x_axis": "regionn", "y_axis": "revenue", "agg": "sum"}


# --------------------------------------------------------------------------
# png
# --------------------------------------------------------------------------


def test_png_returns_png_bytes(df):
    data = jps.png(BAR, df)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_leaves_no_open_figure(df):
    """A rerun draws again; anything left open is leaked for the app's life."""
    plt.close("all")
    for _ in range(3):
        jps.png(BAR, df)
    assert plt.get_fignums() == []


def test_png_leaves_no_open_figure_on_failure(df):
    plt.close("all")
    with pytest.raises(SpecErrorGroup):
        jps.png(BROKEN, df)
    assert plt.get_fignums() == []


def test_png_accepts_a_json_string(df):
    assert jps.png('{"viz_type": "bar", "x_axis": "region", '
                   '"y_axis": "revenue", "agg": "sum"}', df)[:4] == b"\x89PNG"


def test_png_honors_the_contract_dpi(df):
    small = jps.png({**BAR, "dpi": 50}, df)
    large = jps.png({**BAR, "dpi": 200}, df)
    assert len(large) > len(small)


@pytest.mark.parametrize("spec", [
    {**BAR, "backend": "seaborn"},                            # the other backend
    {"viz_type": "hist", "x_axis": "units", "facet_by": "region"},   # facets
    {"viz_type": "line", "x_axis": "date", "y_axis": "revenue",
     "agg": "sum", "time_unit": "month", "group_by": "channel"},
], ids=["seaborn", "facets", "temporal"])
def test_png_draws_the_whole_matrix(spec, df):
    """The adapter is a host, not a backend: everything the library draws has
    to come out of it unchanged."""
    assert jps.png(spec, df)[:4] == b"\x89PNG"


def test_png_raises_the_error_group(df):
    with pytest.raises(SpecErrorGroup) as exc:
        jps.png(BROKEN, df)
    assert [e.code for e in exc.value.errors] == [Code.COLUMN_NOT_FOUND]


# --------------------------------------------------------------------------
# theme resolution
# --------------------------------------------------------------------------


def test_active_theme_defaults_to_clean(monkeypatch):
    monkeypatch.setattr(jps, "_context_theme", lambda: None)
    monkeypatch.setattr(jps, "_option", lambda name: None)
    assert jps.active_theme() == "clean"


def test_active_theme_follows_the_viewer(monkeypatch):
    monkeypatch.setattr(jps, "_context_theme", lambda: "dark")
    assert jps.active_theme() == "dark"


def test_active_theme_falls_back_to_the_configured_base(monkeypatch):
    monkeypatch.setattr(jps, "_context_theme", lambda: None)
    monkeypatch.setattr(jps, "_option", lambda name: "dark")
    assert jps.active_theme() == "dark"


def test_theme_is_injected_when_the_contract_is_silent():
    assert jps._with_theme(BAR, "dark")["style"] == {"theme": "dark"}


def test_theme_is_injected_next_to_other_style_keys():
    spec = {**BAR, "style": {"palette": "warm"}}
    assert jps._with_theme(spec, "dark")["style"] == {"palette": "warm", "theme": "dark"}


@pytest.mark.parametrize("spec", [
    {**BAR, "theme": "clean"},                    # flat dialect
    {**BAR, "style": {"theme": "clean"}},         # canonical
])
def test_the_contract_wins_over_the_app(spec):
    """The app's appearance is a default; an explicit theme is a decision."""
    assert jps._with_theme(spec, "dark") == spec


def test_theme_is_injected_into_a_spec_object():
    spec = Spec.model_validate({"viz_type": "bar", "encoding": {"x": "region"}})
    assert jps._with_theme(spec, "dark").style.theme == "dark"


def test_a_spec_object_keeps_its_own_theme():
    spec = Spec(viz_type="bar", encoding={"x": "region"}, style=Style(theme="clean"))
    assert jps._with_theme(spec, "dark").style.theme == "clean"


def test_malformed_json_is_left_for_the_parser(df):
    with pytest.raises(SpecErrorGroup) as exc:
        jps.png("{not json", df)
    assert exc.value.errors[0].code == Code.INVALID_JSON


def test_the_theme_changes_the_output(df):
    assert jps.png(BAR, df, theme="dark") != jps.png(BAR, df, theme="clean")


def _corner(data: bytes) -> tuple[int, int, int, int]:
    """The top-left pixel: outside the axes, so it is the figure's surface."""
    with Image.open(io.BytesIO(data)) as img:
        return img.convert("RGBA").getpixel((0, 0))


def test_the_dark_theme_paints_a_dark_surface(df):
    r, g, b, _ = _corner(jps.png({**BAR, "theme": "dark"}, df, transparent=False))
    assert max(r, g, b) < 60


def test_the_clean_theme_paints_a_light_surface(df):
    r, g, b, _ = _corner(jps.png({**BAR, "theme": "clean"}, df, transparent=False))
    assert min(r, g, b) > 200


def test_the_surface_is_transparent_by_default(df):
    """So the chart sits on the app's background instead of a pale rectangle."""
    assert _corner(jps.png(BAR, df))[3] == 0
    assert _corner(jps.png(BAR, df, transparent=False))[3] == 255


# --------------------------------------------------------------------------
# inside a real app
# --------------------------------------------------------------------------


def _app(body: str) -> AppTest:
    script = (
        f"import sys; sys.path.insert(0, {str(EXAMPLES)!r})\n"
        "import streamlit as st\n"
        "import jsonplot.streamlit as jps\n"
        "from sample_data import sales\n"
        "df = sales(200)\n"
        f"{body}\n"
    )
    return AppTest.from_string(script, default_timeout=60).run()


def test_a_valid_contract_emits_an_image():
    at = _app(f"errors = jps.st_plot({BAR}, df)\n"
              "st.text('drawn' if not errors else 'failed')")
    assert not at.exception
    assert len(at.image) == 1
    assert at.text[0].value == "drawn"


def test_a_broken_contract_shows_an_error_instead_of_crashing():
    at = _app(f"errors = jps.st_plot({BROKEN}, df)\n"
              "st.text(errors[0].code)")
    assert not at.exception          # the page survives
    assert not at.image              # and draws nothing
    assert len(at.error) == 1
    assert "COLUMN_NOT_FOUND" in at.error[0].value
    assert "did you mean `region`" in at.error[0].value
    assert at.text[0].value == "COLUMN_NOT_FOUND"


def test_errors_can_be_raised_instead():
    at = _app(f"jps.st_plot({BROKEN}, df, errors='raise')")
    assert at.exception


def test_errors_can_be_silenced():
    at = _app(f"jps.st_plot({BROKEN}, df, errors='silent')")
    assert not at.exception
    assert not at.error
    assert not at.image


def test_a_caption_reaches_the_app():
    at = _app(f"jps.st_plot({BAR}, df, caption='Revenue')")
    assert at.image[0].proto.imgs[0].caption == "Revenue"


def test_the_chart_can_be_drawn_in_a_container():
    at = _app("left, right = st.columns(2)\n"
              f"jps.st_plot({BAR}, df, target=right)")
    assert not at.exception
    assert len(at.image) == 1


def test_the_app_theme_is_picked_up_automatically():
    """`theme='auto'` in a dark app must not draw a white rectangle."""
    at = _app("import streamlit.config as cfg\n"
              "cfg.set_option('theme.base', 'dark')\n"
              "st.text(jps.active_theme())\n"
              f"auto, explicit = jps.png({BAR}, df), jps.png({{**{BAR}, 'theme': 'dark'}}, df)\n"
              "st.text('same' if auto == explicit else 'different')")
    try:
        assert at.text[0].value == "dark"
        assert at.text[1].value == "same"
    finally:
        config.set_option("theme.base", None)


def test_a_rerun_does_not_accumulate_figures():
    at = _app("import matplotlib.pyplot as plt\n"
              f"jps.st_plot({BAR}, df)\n"
              "st.text(str(len(plt.get_fignums())))")
    for _ in range(3):
        at.run()
    assert at.text[0].value == "0"


def test_the_example_app_runs():
    at = AppTest.from_file(str(EXAMPLES / "streamlit_app.py"), default_timeout=90).run()
    assert not at.exception
    assert len(at.image) == 1


def test_the_example_app_reports_a_failing_contract():
    at = AppTest.from_file(str(EXAMPLES / "streamlit_app.py"), default_timeout=90).run()
    at.selectbox[0].select("A contract that fails").run()
    assert not at.exception
    assert not at.image
    assert len(at.error) == 1
