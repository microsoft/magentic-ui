"""Settings API.

Endpoints under ``/api/settings`` for runtime-tunable knobs that live in
``MagenticUIConfig`` and are persisted in the same ``Settings`` DB row
the onboarding flow writes to (``user_id = DEFAULT_USER_ID``). Changes
take effect on the next session — no backend restart required.

This module currently exposes only the per-agent ``max_rounds`` cap.
A follow-up PR will move the non-onboarding pieces of
``onboarding.py`` (model endpoints, ``agent_mode``) here as well.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...database import DatabaseManager  # noqa: F401

from ....magentic_ui_config import MagenticUIConfig
from ...web.deps import get_db
from .onboarding import _get_db_config, _save_db_config

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WebSurferAgentSettings(BaseModel):
    """Behavior settings for the FaraWebSurfer (CUA) agent."""

    max_rounds: int = Field(default=100, ge=1, le=1000)


class OrchestratorAgentSettings(BaseModel):
    """Behavior settings for the OmniAgent (orchestrator)."""

    max_rounds: int = Field(default=100, ge=1, le=1000)


class AgentSettings(BaseModel):
    """All agent behavior settings exposed to the frontend."""

    orchestrator: OrchestratorAgentSettings = Field(
        default_factory=OrchestratorAgentSettings
    )
    web_surfer: WebSurferAgentSettings = Field(default_factory=WebSurferAgentSettings)


class AgentSettingsPatch(BaseModel):
    """PUT body for ``/api/settings/agents`` that allows partial updates.

    Each sub-section is optional; omitted sections preserve the existing
    DB value instead of being reset to the schema default.
    """

    orchestrator: OrchestratorAgentSettings | None = None
    web_surfer: WebSurferAgentSettings | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_max_rounds(raw: Any, default: int) -> int:
    """Best-effort coerce a stored ``max_rounds`` value to ``int``.

    Falls back to ``default`` on missing / non-numeric / out-of-range
    values so a corrupt or hand-edited DB entry can't turn a GET on
    ``/api/settings/agents`` into an HTTP 500. Pydantic re-validates the
    final ``AgentSettings`` object below, so the only thing this needs
    to guarantee is "produces some int in [1, 1000]".
    """
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid max_rounds in DB (%r); using default", raw)
        return default
    if value < 1 or value > 1000:
        logger.warning("Out-of-range max_rounds in DB (%r); using default", raw)
        return default
    return value


def _read_agent_settings(config: dict[str, Any]) -> AgentSettings:
    """Project the harness section of a stored config into ``AgentSettings``.

    Falls back to ``MagenticUIConfig`` defaults for any missing or
    invalid field so the frontend always receives a fully-populated
    object — and so a GET never returns 500 on a corrupted DB entry.
    """
    harness_raw = config.get("harness_config") or {}
    if not isinstance(harness_raw, dict):
        harness_raw = {}
    web_raw = harness_raw.get("web_surfer") or {}
    if not isinstance(web_raw, dict):
        web_raw = {}
    orch_raw = harness_raw.get("orchestrator") or {}
    if not isinstance(orch_raw, dict):
        orch_raw = {}

    defaults = MagenticUIConfig().harness_config
    raw_settings = AgentSettings.model_construct(
        orchestrator=OrchestratorAgentSettings.model_construct(
            max_rounds=_coerce_max_rounds(
                orch_raw.get("max_rounds"), defaults.orchestrator.max_rounds
            ),
        ),
        web_surfer=WebSurferAgentSettings.model_construct(
            max_rounds=_coerce_max_rounds(
                web_raw.get("max_rounds"), defaults.web_surfer.max_rounds
            ),
        ),
    )
    # Final pydantic pass enforces the [1, 1000] bound; if a stored
    # value is out of range, swap in defaults rather than 500-ing.
    try:
        return AgentSettings.model_validate(raw_settings.model_dump())
    except Exception as e:
        logger.warning(
            "Stored agent settings failed validation (%s); using defaults", e
        )
        return AgentSettings()


def _apply_agent_settings(config: dict[str, Any], settings: AgentSettings) -> None:
    """Merge ``settings`` into ``config`` in place.

    Only writes the fields exposed through the UI — other ``harness_config``
    keys (e.g. ``approval_policy``, ``temperature``) come from the CLI/file
    and must not be clobbered by the partial JSON the frontend sends.
    """
    harness = config.setdefault("harness_config", {})
    if not isinstance(harness, dict):
        harness = {}
        config["harness_config"] = harness
    web = harness.setdefault("web_surfer", {})
    if not isinstance(web, dict):
        web = {}
        harness["web_surfer"] = web
    web["max_rounds"] = settings.web_surfer.max_rounds
    orch = harness.setdefault("orchestrator", {})
    if not isinstance(orch, dict):
        orch = {}
        harness["orchestrator"] = orch
    orch["max_rounds"] = settings.orchestrator.max_rounds


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/agents")
async def get_agent_settings(db=Depends(get_db)) -> Dict[str, Any]:
    """Return the active agent behavior settings."""
    _, config = _get_db_config(db)
    return {"status": True, "data": _read_agent_settings(config).model_dump()}


@router.put("/agents")
async def update_agent_settings(
    payload: AgentSettingsPatch, db=Depends(get_db)
) -> Dict[str, Any]:
    """Persist updated agent behavior settings.

    Sub-sections that are omitted from the payload preserve the current
    DB value; only fields explicitly sent are written. Returns the
    post-write view so the frontend can refresh its cache.
    """
    settings_row, config = _get_db_config(db)

    current = _read_agent_settings(config)
    merged = AgentSettings(
        orchestrator=payload.orchestrator or current.orchestrator,
        web_surfer=payload.web_surfer or current.web_surfer,
    )

    _apply_agent_settings(config, merged)
    _save_db_config(db, settings_row, config)
    return {"status": True, "data": merged.model_dump()}
