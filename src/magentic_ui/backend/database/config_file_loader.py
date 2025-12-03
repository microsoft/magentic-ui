# database/config_file_loader.py
"""Merge YAML config into the Settings DB row.

Supports partial YAML — only fields explicitly set in the YAML override
existing DB values. Missing fields are preserved from the DB (or filled
with MagenticUIConfig defaults for new installs).
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

from ...magentic_ui_config import MagenticUIConfig, is_onboarding_complete
from .db_manager import DatabaseManager
from ..datamodel import Settings

logger = logging.getLogger(__name__)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (returns a new dict).

    - Dict values are merged recursively.
    - Non-dict values in *override* replace *base*.
    - Keys only in *base* are preserved.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)  # pyright: ignore[reportUnknownArgumentType]
        else:
            result[key] = copy.deepcopy(value)
    return result


def _merge_yaml_into_db(
    db: DatabaseManager,
    *,
    raw_yaml: dict[str, Any],
    user_id: str,
) -> bool:
    """Merge an already-loaded YAML dict into the Settings DB row.

    Internal helper — exposed for unit tests. Public callers should use
    :func:`load_config_file` which reads the YAML file itself.
    """
    if not raw_yaml:
        logger.info("YAML config is empty — DB unchanged")
        return False

    # ── Read existing DB config (or create default) ─────────────────────
    response = db.get(Settings, filters={"user_id": user_id})
    if not response.status:
        logger.error("Failed to read settings from DB: %s", response.message)
        return False
    if response.data:
        settings_row = response.data[0]
        raw = settings_row.config  # pyright: ignore[reportUnknownMemberType]
        existing: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    else:
        settings_row = Settings(  # pyright: ignore[reportCallIssue]
            user_id=user_id,
            config={},
        )
        existing = {}

    # If DB is empty, start from defaults
    if not existing:
        existing = MagenticUIConfig().model_dump()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]

    # ── Merge YAML overrides into existing ──────────────────────────────
    merged = _deep_merge(existing, raw_yaml)  # pyright: ignore[reportUnknownArgumentType]

    # ── Determine onboarding_completed (honors agent_mode) ──────────────
    settings_row.onboarding_completed = is_onboarding_complete(merged)

    # ── Save ────────────────────────────────────────────────────────────
    settings_row.config = merged
    result = db.upsert(settings_row)
    if not result.status:
        logger.error("Failed to merge YAML config into DB: %s", result.message)
        return False

    logger.info(
        "Merged YAML config into DB (overrides: %s)",
        ", ".join(raw_yaml.keys()),
    )
    return True


def load_config_file(
    db: DatabaseManager,
    *,
    config_path: Path,
    user_id: str,
) -> bool:
    """Load a YAML config file and merge it into the Settings DB row.

    Supports partial YAML files. For example, a YAML with only ``agent_mode``
    will update that field without touching model configs or sandbox settings.

    Uses the raw YAML dict (not pydantic-parsed config) so only fields the
    user explicitly set override the DB — avoiding the ``exclude_defaults``
    problem where a value equal to the pydantic default would be silently
    skipped.

    Returns True if the DB was updated, False on empty/missing config or
    on DB error.
    """
    path = config_path.expanduser().resolve()
    with open(path) as f:
        raw_yaml: dict[str, Any] = yaml.safe_load(f) or {}
    return _merge_yaml_into_db(db, raw_yaml=raw_yaml, user_id=user_id)
