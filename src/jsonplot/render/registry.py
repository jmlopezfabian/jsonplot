"""Renderer registry.

Adding a chart type means writing a class and decorating it. An external
package can do that without touching the core.
"""

from __future__ import annotations

from ..binding.errors import Code, SpecError
from .base import Renderer

_REGISTRY: dict[tuple[str, str], Renderer] = {}


def register(viz_type: str, backend: str):
    def decorator(cls: type[Renderer]) -> type[Renderer]:
        cls.viz_type = viz_type
        cls.backend = backend
        _REGISTRY[(viz_type, backend)] = cls()
        return cls
    return decorator


def get_renderer(viz_type: str, backend: str) -> tuple[Renderer | None, SpecError | None]:
    hit = _REGISTRY.get((viz_type, backend))
    if hit is not None:
        return hit, None
    others = sorted(b for (v, b) in _REGISTRY if v == viz_type)
    return None, SpecError(
        Code.RENDERER_NOT_FOUND, "viz_type",
        f"the '{backend}' backend does not draw '{viz_type}'",
        hint=(f"backends available for '{viz_type}': {', '.join(others)}" if others
              else f"available types: {', '.join(sorted({v for v, _ in _REGISTRY}))}"),
    )


def available() -> dict[str, list[str]]:
    """{viz_type: [backends]} — what this installation can draw."""
    out: dict[str, list[str]] = {}
    for viz, backend in sorted(_REGISTRY):
        out.setdefault(viz, []).append(backend)
    return out
