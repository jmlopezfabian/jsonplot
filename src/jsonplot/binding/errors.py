"""Structured errors.

A contract is often written by a model that has never seen the data, so a
validation failure is the normal case, not the exception. Every error carries
where it is (`path`), what to do about it (`hint`), and — when it can be
guessed — what was meant (`did_you_mean`), so it can go straight back into a
prompt without being translated.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass, field


class Code:
    """Error codes. Stable: they are part of the public API."""

    # contract shape
    INVALID_JSON = "INVALID_JSON"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_VALUE = "INVALID_VALUE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"

    # contract against data
    COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    AGGREGATE_REQUIRED = "AGGREGATE_REQUIRED"
    AGGREGATE_INVALID = "AGGREGATE_INVALID"
    CARDINALITY_TOO_HIGH = "CARDINALITY_TOO_HIGH"
    CHANNEL_NOT_SUPPORTED = "CHANNEL_NOT_SUPPORTED"
    MISSING_CHANNEL = "MISSING_CHANNEL"
    EMPTY_RESULT = "EMPTY_RESULT"

    # render
    RENDERER_NOT_FOUND = "RENDERER_NOT_FOUND"


@dataclass
class SpecError:
    code: str
    path: str
    message: str
    hint: str | None = None
    did_you_mean: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d["did_you_mean"]:
            d.pop("did_you_mean")
        if d["hint"] is None:
            d.pop("hint")
        return d

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.path}: {self.message}"]
        if self.did_you_mean:
            parts.append("did you mean " + " or ".join(repr(c) for c in self.did_you_mean) + "?")
        if self.hint:
            parts.append(self.hint)
        return " ".join(parts)


class SpecErrorGroup(Exception):
    """Raised when `plot()` gets a contract it cannot execute.

    Collects every error instead of stopping at the first: an agent repairs
    better with the full list.
    """

    def __init__(self, errors: list[SpecError]):
        self.errors = errors
        super().__init__("\n".join(f"  · {e}" for e in errors))

    def to_json(self, **kw) -> str:
        return json.dumps([e.to_dict() for e in self.errors], ensure_ascii=False, **kw)

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self.errors]


def close_matches(name: str, candidates, n: int = 3) -> list[str]:
    """The real columns closest to the one the contract asked for.

    Compares case- and punctuation-insensitively so that 'Date' finds 'date'
    and 'sale_date' finds 'sale date'.
    """
    pool = list(candidates)
    norm = {c: _norm(c) for c in pool}
    target = _norm(name)
    exact = [c for c in pool if norm[c] == target]
    if exact:
        return exact[:n]
    hits = difflib.get_close_matches(target, list(norm.values()), n=n, cutoff=0.6)
    seen, out = set(), []
    for h in hits:
        for c in pool:
            if norm[c] == h and c not in seen:
                seen.add(c)
                out.append(c)
    return out[:n]


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())
