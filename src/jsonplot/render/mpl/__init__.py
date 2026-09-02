"""matplotlib renderers. Importing the module registers them."""

from . import bar, distribution, line, scatter  # noqa: F401

__all__ = ["bar", "distribution", "line", "scatter"]
