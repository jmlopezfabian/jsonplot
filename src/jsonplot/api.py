"""The public surface.

`plot` is the short path; `validate` and `inspect` are the path an agent takes
before drawing, because neither of them executes anything graphical.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .binding.binder import BoundSpec, bind
from .binding.dtypes import describe_column
from .binding.errors import SpecError, SpecErrorGroup
from .render.driver import export, render
from .render.registry import available
from .spec.models import Output, Spec
from .spec.parse import parse_spec
from .transform.pipeline import build_plot_frame

__all__ = [
    "plot", "validate", "build_frame", "describe_dataframe", "inspect",
    "supported", "resolve",
]


def plot(spec: Any, df: pd.DataFrame, output: str | None = None):
    """Contract + DataFrame -> figure.

    Returns a `matplotlib.figure.Figure` unless the contract (or the `output`
    argument) asks for another format. Raises `SpecErrorGroup` when the
    contract cannot be executed; its errors are JSON-serializable.
    """
    bound = resolve(spec, df)
    pf = build_plot_frame(bound)
    fig = render(bound, pf)
    out = bound.spec.output if output is None else Output(format=output,
                                                          dpi=bound.spec.output.dpi)
    return export(fig, out)


def validate(spec: Any, df: pd.DataFrame | None = None) -> list[SpecError]:
    """Check the contract without drawing anything.

    Without `df` it only checks the shape; with `df` it also checks against the
    data. Returns the full list of errors rather than the first one: an agent
    repairs better when it sees them all.
    """
    parsed, errors = parse_spec(spec)
    if errors or parsed is None:
        return errors
    if df is None:
        return []
    _, bind_errors = bind(parsed, df)
    return bind_errors


def build_frame(spec: Any, df: pd.DataFrame) -> pd.DataFrame:
    """The plot frame: the exact data that will be drawn.

    It is the core's boundary, so it is also the place to check that a contract
    does what you think it does, without looking at a single pixel.
    """
    return build_plot_frame(resolve(spec, df))


def resolve(spec: Any, df: pd.DataFrame) -> BoundSpec:
    """Normalize, validate and bind. Raises `SpecErrorGroup` on failure."""
    parsed, errors = parse_spec(spec)
    if errors or parsed is None:
        raise SpecErrorGroup(errors)
    bound, errors = bind(parsed, df)
    if errors or bound is None:
        raise SpecErrorGroup(errors)
    return bound


def describe_dataframe(df: pd.DataFrame, examples: int = 3) -> dict:
    """A DataFrame summary sized to fit in a prompt.

    Handing this to the agent before it writes the contract eliminates most
    COLUMN_NOT_FOUND errors at the root.
    """
    return {
        "n_rows": int(len(df)),
        "columns": {str(c): describe_column(df[c], examples) for c in df.columns},
    }


def inspect(spec: Any, df: pd.DataFrame) -> dict:
    """A full report on a contract: what was understood and what would be drawn.

    Meant for debugging and for an agent to correct itself: it returns the
    normalized spec, the errors, and a sample of the plot frame.
    """
    parsed, errors = parse_spec(spec)
    report: dict = {
        "valid": False,
        "canonical": parsed.model_dump(exclude_none=True) if parsed else None,
        "errors": [e.to_dict() for e in errors],
    }
    if parsed is None:
        return report

    bound, bind_errors = bind(parsed, df)
    report["errors"] += [e.to_dict() for e in bind_errors]
    if bound is None:
        return report

    pf = build_plot_frame(bound)
    report.update(
        valid=True,
        needs_aggregation=bound.needs_aggregation,
        channels={r: {"field": c.field, "type": c.type, "aggregate": c.aggregate,
                      "n_unique": c.n_unique} for r, c in bound.channels.items()},
        plot_frame={"n_rows": int(len(pf)), "columns": list(pf.columns),
                    "head": pf.head(5).to_dict("records")},
    )
    return report


def supported() -> dict[str, list[str]]:
    """{viz_type: [backends]} — what this installation can draw."""
    return available()
