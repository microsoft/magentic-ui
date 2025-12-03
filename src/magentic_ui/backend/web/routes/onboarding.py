# api/routes/onboarding.py
"""Onboarding API — model endpoint configuration and verification."""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

if TYPE_CHECKING:
    from ...database import DatabaseManager

from ....magentic_ui_config import (
    AgentMode,
    MagenticUIConfig,
    ROLE_DEFAULTS,
    is_onboarding_complete,
    required_roles_for_mode,
)
from ...datamodel import Settings
from ...web.deps import get_db
from ...web.config import settings as app_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Sentinel value returned instead of real API keys in GET responses.
# When the frontend sends this back, the backend keeps the existing DB value.
API_KEY_MASKED = "__MASKED__"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ModelEndpointInput(BaseModel):
    """User-provided fields only — backend fills the rest from role defaults."""

    base_url: str
    model: str
    api_key: str = ""

    @field_validator("base_url", "model")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty or whitespace")
        return v


class ModelVerifyRequest(BaseModel):
    """Payload for POST /api/onboarding/verify.

    The ``orchestrator`` and ``web_surfer`` fields are optional — the caller
    only needs to send the role(s) required by ``agent_mode``.
    """

    orchestrator: Optional[ModelEndpointInput] = None
    web_surfer: Optional[ModelEndpointInput] = None
    agent_mode: AgentMode = AgentMode.ALL


class AgentModeRequest(BaseModel):
    """Payload for POST /api/onboarding/agent-mode."""

    agent_mode: AgentMode


class ModelEndpointVerification(BaseModel):
    success: bool
    error: Optional[str] = None


class ModelVerifyResponse(BaseModel):
    orchestrator: Optional[ModelEndpointVerification] = None
    web_surfer: Optional[ModelEndpointVerification] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db_config(db: "DatabaseManager") -> tuple[Settings, dict[str, Any]]:
    """Return (Settings row, config dict as MagenticUIConfig shape)."""
    response = db.get(Settings, filters={"user_id": app_settings.DEFAULT_USER_ID})
    if not response.status:
        raise HTTPException(status_code=500, detail="Failed to read settings from DB")
    if response.data:
        settings_row = response.data[0]
        raw = settings_row.config if isinstance(settings_row.config, dict) else {}
        # If empty, fill with defaults
        if not raw:
            raw = MagenticUIConfig().model_dump()
        return settings_row, raw

    # Create default
    default_config = MagenticUIConfig().model_dump()
    default = Settings(  # pyright: ignore[reportCallIssue]
        user_id=app_settings.DEFAULT_USER_ID,
        config=default_config,
    )
    upsert = db.upsert(default)
    if not upsert.status:
        raise HTTPException(status_code=500, detail="Failed to create settings")
    refetch = db.get(Settings, filters={"user_id": app_settings.DEFAULT_USER_ID})
    if refetch.status and refetch.data:
        return refetch.data[0], default_config
    raise HTTPException(
        status_code=500, detail="Failed to load settings after creation."
    )


def _save_db_config(
    db: "DatabaseManager", settings_row: Settings, config: dict[str, Any]
) -> None:
    """Persist config dict back into the Settings row."""
    settings_row.config = config
    resp = db.upsert(settings_row)
    if not resp.status:
        raise HTTPException(status_code=500, detail="Failed to save settings")


def _build_client_dict(user_input: ModelEndpointInput, role: str) -> dict[str, Any]:
    """Build a model client config dict from user input + role defaults."""
    defaults = ROLE_DEFAULTS[role]
    return {
        "provider": defaults["provider"],
        "config": {
            "model": user_input.model.strip(),
            "api_key": user_input.api_key.strip(),
            "base_url": user_input.base_url.strip(),
            "max_retries": defaults["max_retries"],
            "model_info": copy.deepcopy(defaults["model_info"]),
        },
    }


def _mask_client_dict(d: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a copy of the client dict with api_key masked."""
    if not d:
        return None
    result = copy.deepcopy(d)
    cfg = result.get("config", {})
    if cfg.get("api_key"):
        cfg["api_key"] = API_KEY_MASKED
    return result


def _resolve_masked_key(
    user_input: ModelEndpointInput,
    saved_dict: dict[str, Any] | None,
) -> None:
    """Replace __MASKED__ sentinel with the real key from DB (in-place)."""
    if user_input.api_key.strip() == API_KEY_MASKED and saved_dict:
        saved_key = saved_dict.get("config", {}).get("api_key", "")
        if saved_key:
            user_input.api_key = saved_key


async def _verify_single_endpoint(
    client_dict: dict[str, Any],
) -> ModelEndpointVerification:
    """Probe an OpenAI-compatible endpoint (reachability + best-effort model check)."""
    cfg = client_dict.get("config", {})
    base_url = cfg.get("base_url", "").rstrip("/")
    model_name = cfg.get("model", "")
    api_key = cfg.get("api_key", "")

    if not base_url.startswith(("http://", "https://")):
        return ModelEndpointVerification(
            success=False, error="base_url must use http:// or https:// scheme"
        )

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
            if resp.status_code != 200:
                return ModelEndpointVerification(
                    success=False,
                    error=f"Endpoint returned HTTP {resp.status_code}",
                )

            try:
                data = resp.json()
                models = data.get("data", [])
                model_ids = [str(m.get("id", "")) for m in models if m.get("id")]
                if model_name and model_ids and model_name not in model_ids:
                    return ModelEndpointVerification(
                        success=False,
                        error=f"Model '{model_name}' not found. Available: {', '.join(model_ids[:5])}",
                    )
            except Exception:
                pass

            return ModelEndpointVerification(success=True)
    except httpx.ConnectError:
        return ModelEndpointVerification(
            success=False, error="Connection refused — is the server running?"
        )
    except httpx.TimeoutException:
        return ModelEndpointVerification(
            success=False, error="Connection timed out (10s)"
        )
    except Exception:
        logger.exception("Unexpected error verifying endpoint")
        return ModelEndpointVerification(
            success=False, error="Verification failed due to an unexpected error"
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _get_model_configs(config: dict[str, Any]) -> dict[str, Any]:
    """Safely extract model_client_configs dict from config."""
    val = config.get("model_client_configs", {})
    return val if isinstance(val, dict) else {}


# Re-export shared helpers under their old private names so existing call sites
# (and tests) keep working. Logic lives in ``magentic_ui_config``.
_required_roles = required_roles_for_mode
_is_onboarding_complete = is_onboarding_complete


@router.get("/status")
async def get_onboarding_status(db=Depends(get_db)) -> Dict[str, Any]:
    """Return whether onboarding has been completed."""
    response = db.get(Settings, filters={"user_id": app_settings.DEFAULT_USER_ID})
    completed = False
    if response.status and response.data:
        completed = response.data[0].onboarding_completed
    return {
        "status": True,
        "data": {"onboarding_completed": completed},
    }


@router.get("/endpoints")
async def get_onboarding_endpoints(db=Depends(get_db)) -> Dict[str, Any]:
    """Return saved model endpoints (masked) and the active agent_mode.

    Used by the settings page and the onboarding flow.
    """
    _, config = _get_db_config(db)
    model_configs = _get_model_configs(config)
    raw_mode = config.get("agent_mode") or AgentMode.ALL.value
    try:
        agent_mode = AgentMode(raw_mode).value
    except ValueError:
        agent_mode = AgentMode.ALL.value

    return {
        "status": True,
        "data": {
            "orchestrator": _mask_client_dict(model_configs.get("orchestrator")),
            "web_surfer": _mask_client_dict(model_configs.get("web_surfer")),
            "agent_mode": agent_mode,
        },
    }


@router.post("/verify")
async def verify_endpoints(
    req: ModelVerifyRequest, db=Depends(get_db)
) -> Dict[str, Any]:
    """Verify the model endpoint(s) required by ``agent_mode`` and save them.

    The caller may omit the role(s) not required by ``agent_mode``. On
    success, the active ``agent_mode`` is also persisted; the inactive
    role's saved config (if any) is left untouched.
    """
    settings_row, config = _get_db_config(db)
    model_configs = _get_model_configs(config)
    required = _required_roles(req.agent_mode)

    # Caller must provide every required role.
    missing_input = [
        role
        for role in required
        if (role == "orchestrator" and req.orchestrator is None)
        or (role == "web_surfer" and req.web_surfer is None)
    ]
    if missing_input:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required endpoint(s) for {req.agent_mode.value}: {', '.join(sorted(missing_input))}",
        )

    orch_dict: dict[str, Any] | None = None
    ws_dict: dict[str, Any] | None = None
    orch_result: ModelEndpointVerification | None = None
    ws_result: ModelEndpointVerification | None = None

    tasks: list[Any] = []
    if "orchestrator" in required and req.orchestrator is not None:
        _resolve_masked_key(req.orchestrator, model_configs.get("orchestrator"))
        orch_dict = _build_client_dict(req.orchestrator, "orchestrator")
        tasks.append(("orchestrator", _verify_single_endpoint(orch_dict)))
    if "web_surfer" in required and req.web_surfer is not None:
        _resolve_masked_key(req.web_surfer, model_configs.get("web_surfer"))
        ws_dict = _build_client_dict(req.web_surfer, "web_surfer")
        tasks.append(("web_surfer", _verify_single_endpoint(ws_dict)))

    results = await asyncio.gather(*(coro for _, coro in tasks))
    for (role, _), result in zip(tasks, results):
        if role == "orchestrator":
            orch_result = result
        else:
            ws_result = result

    # Save to DB only when every required role verified successfully.
    all_ok = True
    if "orchestrator" in required:
        all_ok = all_ok and bool(orch_result and orch_result.success)
    if "web_surfer" in required:
        all_ok = all_ok and bool(ws_result and ws_result.success)

    if all_ok:
        if orch_dict is not None:
            model_configs["orchestrator"] = orch_dict
        if ws_dict is not None:
            model_configs["web_surfer"] = ws_dict
        config["model_client_configs"] = model_configs
        config["agent_mode"] = req.agent_mode.value
        # Recompute onboarding_completed based on the new config.
        settings_row.onboarding_completed = _is_onboarding_complete(config)
        _save_db_config(db, settings_row, config)

    return {
        "status": True,
        "data": ModelVerifyResponse(
            orchestrator=orch_result,
            web_surfer=ws_result,
        ).model_dump(),
    }


@router.post("/agent-mode")
async def set_agent_mode(req: AgentModeRequest, db=Depends(get_db)) -> Dict[str, Any]:
    """Update ``agent_mode`` only — no model verification.

    Returns HTTP 400 (with a human-readable message) when the new mode
    requires a model_client_config that is not yet saved in DB. The
    frontend's smart-save logic guards against this in normal flow, so a
    400 here typically indicates a stale UI / concurrent edit.
    """
    settings_row, config = _get_db_config(db)
    model_configs = _get_model_configs(config)
    required = _required_roles(req.agent_mode)

    missing = sorted(role for role in required if not model_configs.get(role))
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot switch to {req.agent_mode.value}: "
                f"missing saved config for {', '.join(missing)}"
            ),
        )

    config["agent_mode"] = req.agent_mode.value
    settings_row.onboarding_completed = _is_onboarding_complete(config)
    _save_db_config(db, settings_row, config)

    return {
        "status": True,
        "data": {"agent_mode": req.agent_mode.value},
    }


@router.post("/complete")
async def complete_onboarding(db=Depends(get_db)) -> Dict[str, Any]:
    """Mark onboarding as completed. Requires the model(s) for the active
    ``agent_mode`` to be configured.
    """
    settings_row, config = _get_db_config(db)
    model_configs = _get_model_configs(config)
    raw_mode = config.get("agent_mode") or AgentMode.ALL.value
    try:
        agent_mode = AgentMode(raw_mode)
    except ValueError:
        agent_mode = AgentMode.ALL

    missing = sorted(
        role for role in _required_roles(agent_mode) if not model_configs.get(role)
    )
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing endpoint(s) for {agent_mode.value}: {', '.join(missing)}",
        )

    settings_row.onboarding_completed = True
    _save_db_config(db, settings_row, config)

    return {"status": True, "message": "Onboarding completed"}


@router.post("/reset")
async def reset_onboarding(db=Depends(get_db)) -> Dict[str, Any]:
    """Reset onboarding config — clears model endpoints, preserves sandbox/agent_mode."""
    reset_onboarding_config(db)
    return {"status": True, "message": "Onboarding config reset"}


# ---------------------------------------------------------------------------
# Helpers (non-route, also used by CLI --reset-config)
# ---------------------------------------------------------------------------


def reset_onboarding_config(db: "DatabaseManager") -> None:
    """Clear model endpoints and onboarding flag. Preserves sandbox and agent_mode."""
    response = db.get(Settings, filters={"user_id": app_settings.DEFAULT_USER_ID})
    if response.status and response.data:
        settings_row = response.data[0]
        raw = settings_row.config if isinstance(settings_row.config, dict) else {}
        if not raw:
            raw = MagenticUIConfig().model_dump()
        # Clear only model configs
        model_configs = raw.setdefault("model_client_configs", {})
        model_configs["orchestrator"] = None
        model_configs["web_surfer"] = None
        settings_row.onboarding_completed = False
        settings_row.config = raw
        result = db.upsert(settings_row)
        if not result.status:
            logger.error("Failed to reset onboarding config: %s", result.message)
            return
        logger.info("Onboarding config reset")
