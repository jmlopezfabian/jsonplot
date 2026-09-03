"""jsonplot inside a Streamlit app.

Streamlit reruns the whole script on every interaction, and that is what makes
matplotlib awkward there: figures pile up in pyplot's registry, the app's
appearance can change underneath the chart, and a contract the data does not
support takes the page down with a traceback. This module is the adapter for
those three things and nothing else — the contract, the pipeline and the errors
are the same ones the rest of the library uses.

    import jsonplot.streamlit as jps

    jps.st_plot({"viz_type": "bar", "x_axis": "region",
                 "y_axis": "revenue", "agg": "sum"}, df)

A figure is never left open, the theme follows the app unless the contract
picked one, and an invalid contract is displayed as a structured error instead
of being raised.
"""

from __future__ import annotations

import json
from typing import Any, Literal

import matplotlib.pyplot as plt
import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - depends on the install
    raise ModuleNotFoundError(
        "jsonplot.streamlit needs Streamlit: pip install 'jsonplot[streamlit]'"
    ) from exc

from .api import resolve
from .binding.errors import SpecError, SpecErrorGroup
from .render.driver import export, render
from .spec.models import Output, Spec
from .transform.pipeline import build_plot_frame

__all__ = ["st_plot", "png", "active_theme", "show_errors"]

#: `width="stretch"` on `st.image` landed in 1.46; before that it was
#: `use_container_width`.
_WIDTH_KEYWORD = tuple(int(p) for p in st.__version__.split(".")[:2]) >= (1, 46)

Width = Literal["stretch", "content"] | int
ErrorMode = Literal["show", "raise", "silent"]


def st_plot(
    spec: Any,
    df: pd.DataFrame,
    *,
    theme: str = "auto",
    width: Width = "stretch",
    transparent: bool = True,
    caption: str | None = None,
    errors: ErrorMode = "show",
    target: Any | None = None,
) -> list[SpecError]:
    """Draw the contract in the app. Returns `[]`, or the errors if it could not.

    Failure is a returned value rather than an exception because in Streamlit
    the alternative is a dead page: an agent-written contract that misses the
    data should leave the rest of the app standing. `errors="raise"` restores
    the library's behaviour, `errors="silent"` draws nothing and stays quiet.

    `target` is any Streamlit container (a column, a tab, an expander), so the
    chart can be placed where the layout wants it.
    """
    target = st if target is None else target
    try:
        data = png(spec, df, theme=theme, transparent=transparent)
    except SpecErrorGroup as group:
        if errors == "raise":
            raise
        if errors == "show":
            show_errors(group.errors, target=target)
        return group.errors

    _image(target, data, caption, width)
    return []


def png(spec: Any, df: pd.DataFrame, *, theme: str = "auto",
        transparent: bool = True) -> bytes:
    """The chart as PNG bytes, for `st.image`, `st.download_button` or a cache.

    Bytes rather than a `Figure`: they are what Streamlit sends anyway, they
    can be memoized with `st.cache_data`, and nothing stays open afterwards.

    Raises `SpecErrorGroup`, like `jsonplot.plot`.
    """
    bound = resolve(_with_theme(spec, active_theme() if theme == "auto" else theme), df)
    fig = render(bound, build_plot_frame(bound))
    try:
        return export(fig, Output(format="png", dpi=bound.spec.output.dpi,
                                  transparent=transparent))
    finally:
        # a rerun would otherwise leave every figure it ever drew in memory
        plt.close(fig)


def active_theme(default: str = "clean") -> str:
    """The jsonplot theme that matches how the app currently looks.

    Reads the viewer's resolved appearance first (`st.context.theme`), then the
    configured base, so a chart in a dark app is not a white rectangle.
    """
    for base in (_context_theme(), _option("theme.base")):
        if base:
            return "dark" if str(base).lower() == "dark" else default
    return default


def show_errors(errors: list[SpecError], *, target: Any | None = None) -> None:
    """Display contract errors as an app element instead of a traceback.

    Keeps `code`, `path`, `hint` and `did_you_mean` visible: the same fields
    that go back into the prompt when an agent wrote the contract.
    """
    if not errors:
        return
    target = st if target is None else target

    lines = [f"**Contract cannot be drawn** — {len(errors)} error(s):"]
    for e in errors:
        line = f"- `{e.code}` at `{e.path}` — {e.message}"
        if e.did_you_mean:
            line += "  \n  did you mean " + " or ".join(f"`{c}`" for c in e.did_you_mean) + "?"
        if e.hint:
            line += f"  \n  _{e.hint}_"
        lines.append(line)
    target.error("\n".join(lines))

    if hasattr(target, "expander"):
        with target.expander("Errors as JSON"):
            st.code(json.dumps([e.to_dict() for e in errors], indent=2, ensure_ascii=False),
                    language="json")


# --------------------------------------------------------------------------


def _with_theme(spec: Any, theme: str) -> Any:
    """Set the theme on the contract, unless the contract already chose one.

    The app's appearance is a default, never an override: a contract asking for
    `dark` means it, wherever it is drawn.
    """
    if isinstance(spec, Spec):
        if "theme" in spec.style.model_fields_set:
            return spec
        return spec.model_copy(update={
            "style": spec.style.model_copy(update={"theme": theme}),
        })

    if isinstance(spec, (str, bytes)):
        try:
            spec = json.loads(spec)
        except (ValueError, TypeError):
            return spec  # let parse_spec report the malformed JSON
    if not isinstance(spec, dict):
        return spec

    style = spec.get("style")
    if "theme" in spec or (isinstance(style, dict) and "theme" in style):
        return spec
    merged = dict(style) if isinstance(style, dict) else {}
    merged["theme"] = theme
    return {**spec, "style": merged}


def _image(target: Any, data: bytes, caption: str | None, width: Width) -> None:
    if _WIDTH_KEYWORD:
        target.image(data, caption=caption, width=width)
    else:
        target.image(data, caption=caption, use_container_width=width == "stretch")


def _context_theme() -> str | None:
    """The viewer's appearance.

    Only readable during a script run; asked for outside one it warns instead
    of raising, so the run context is checked first — importing this module in
    a test or a notebook has to stay silent.
    """
    if not _in_app():
        return None
    try:
        return getattr(st.context.theme, "type", None)
    except Exception:
        return None


def _in_app() -> bool:
    """True while a Streamlit script is running."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:  # pragma: no cover - moved in some versions
        return False
    return get_script_run_ctx(suppress_warning=True) is not None


def _option(name: str) -> str | None:
    try:
        return st.get_option(name)
    except Exception:
        return None
