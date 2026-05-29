"""JSON state persistence for OmniAgent multi-turn resume."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

# Skip writes above this size. A long session can produce a large message
# list; rather than truncating semantically, we drop the persist step and
# let the in-memory agent keep working for the current process.
DEFAULT_MAX_STATE_BYTES = 50_000_000


def read_state(state_path: Path) -> dict[str, Any]:
    """Return the parsed state dict at ``state_path``, or ``{}`` on any failure."""
    if not state_path.exists():
        return {}
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read omni state at %s: %s", state_path, exc)
        return {}
    if not raw:
        return {}
    try:
        loaded: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Corrupted omni state at %s: %s", state_path, exc)
        return {}
    if not isinstance(loaded, dict):
        logger.warning(
            "Omni state at %s is not a JSON object (got %s); ignoring",
            state_path,
            type(loaded).__name__,
        )
        return {}
    return cast(dict[str, Any], loaded)


def write_state(
    state_path: Path,
    payload: dict[str, Any],
    max_bytes: int = DEFAULT_MAX_STATE_BYTES,
) -> None:
    """Atomically write ``payload`` as JSON to ``state_path``; skip if oversized."""
    try:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        logger.warning("Cannot serialize omni state for %s: %s", state_path, exc)
        return
    if len(encoded) > max_bytes:
        logger.warning(
            "Omni state for %s is %d bytes (> %d cap); skipping persist",
            state_path,
            len(encoded),
            max_bytes,
        )
        return
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create omni state dir %s: %s", state_path.parent, exc)
        return
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".omni_state.", suffix=".tmp", dir=str(state_path.parent)
    )
    # Close the raw fd immediately; we write via the path so any open
    # or write failure below can never leak the fd.
    os.close(tmp_fd)
    try:
        Path(tmp_name).write_bytes(encoded)
        if state_path.exists():
            state_path.rename(state_path.with_suffix(".bak"))
        state_path.replace(Path(tmp_name))
    except OSError as exc:
        logger.warning("Cannot write omni state to %s: %s", state_path, exc)
        try:
            os.unlink(tmp_name)
        except OSError:
            pass