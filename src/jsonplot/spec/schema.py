"""JSON Schema export for the contract.

Generated from the models, never written by hand: maintained twice, the two
copies would drift apart immediately.
"""

from __future__ import annotations

import json

from .capabilities import CAPABILITIES
from .models import Spec

TOOL_NAME = "render_chart"


def json_schema() -> dict:
    """The JSON Schema of the canonical spec."""
    return Spec.model_json_schema(mode="validation")


def tool_definition(name: str = TOOL_NAME) -> dict:
    """A tool definition ready for tool-calling."""
    return {
        "name": name,
        "description": (
            "Render a visualization from an already-loaded DataFrame. "
            "Declare which column goes in which visual channel; do not write code. "
            + capability_summary()
        ),
        "input_schema": json_schema(),
    }


def capability_summary() -> str:
    """One line per chart type, for the agent's prompt."""
    lines = []
    for name, cap in CAPABILITIES.items():
        lines.append(
            f"{name}: required {list(cap.required)}, "
            f"optional {list(cap.optional)} — {cap.description}"
        )
    return "Available types — " + " | ".join(lines)


def dump(path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(json_schema(), fh, indent=2, ensure_ascii=False)
