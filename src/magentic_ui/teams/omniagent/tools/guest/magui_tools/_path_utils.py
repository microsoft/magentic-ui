"""Path-validation helpers shared by guest tools.

Refuses paths under ``__pycache__`` and ``site-packages`` to keep
search/find results free of venv internals.
"""

from __future__ import annotations

from pathlib import Path

_RESTRICTED_PARTS = frozenset({"__pycache__"})
_RESTRICTED_SUBSTRINGS = ("site-packages",)


def is_restricted(path: Path) -> bool:
    """Return True if ``path`` traverses a harness-internal location."""
    parts = path.parts
    if any(p in _RESTRICTED_PARTS for p in parts):
        return True
    if any(s in p for p in parts for s in _RESTRICTED_SUBSTRINGS):
        return True
    return False
