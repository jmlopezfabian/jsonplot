"""seaborn backend. Optional: when seaborn is not installed nothing registers,
and a contract asking for it gets a RENDERER_NOT_FOUND listing the backends
that are available."""

try:
    from . import renderers  # noqa: F401
    AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the installation
    AVAILABLE = False

__all__ = ["AVAILABLE"]
