"""jsonplot — a JSON contract and a DataFrame go in, a figure comes out."""

from .api import (
    build_frame, describe_dataframe, inspect, plot, resolve, supported, validate,
)
from .binding.errors import Code, SpecError, SpecErrorGroup
from .spec.briefing import contract
from .spec.models import Spec
from .spec.schema import capability_summary, json_schema, tool_definition

__version__ = "0.1.0"

__all__ = [
    "Code", "Spec", "SpecError", "SpecErrorGroup", "build_frame",
    "capability_summary", "contract", "describe_dataframe", "inspect",
    "json_schema",
    "plot", "resolve", "supported", "tool_definition", "validate",
]
