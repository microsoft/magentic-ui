"""Tests for the /api/settings/agents route.

Covers helper-level behavior plus the route-level partial-PUT contract
that the frontend Settings UI depends on:

- GET returns the projection of the stored harness_config, never 500ing
  on missing / malformed values.
- PUT with both sub-sections persists both.
- PUT with only one sub-section preserves the other (the regression
  Copilot flagged: previously ``AgentSettings.model_validate`` would
  fill the omitted side with schema defaults).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from magentic_ui.backend.web.deps import get_db
from magentic_ui.backend.web.routes import settings as settings_routes
from magentic_ui.backend.web.routes.settings import (
    AgentSettings,
    OrchestratorAgentSettings,
    WebSurferAgentSettings,
    _apply_agent_settings,
    _coerce_max_rounds,
    _read_agent_settings,
)
from magentic_ui.backend.datamodel import Settings


# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


class TestCoerceMaxRounds:
    def test_returns_default_on_missing(self) -> None:
        assert _coerce_max_rounds(None, default=42) == 42

    def test_returns_int_on_int(self) -> None:
        assert _coerce_max_rounds(50, default=42) == 50

    def test_coerces_numeric_string(self) -> None:
        assert _coerce_max_rounds("75", default=42) == 75

    def test_returns_default_on_non_numeric_string(self) -> None:
        assert _coerce_max_rounds("not-an-int", default=42) == 42

    def test_returns_default_on_below_range(self) -> None:
        assert _coerce_max_rounds(0, default=42) == 42

    def test_returns_default_on_above_range(self) -> None:
        assert _coerce_max_rounds(1001, default=42) == 42


class TestReadAgentSettings:
    def test_empty_config_returns_defaults(self) -> None:
        result = _read_agent_settings({})
        assert result.orchestrator.max_rounds == 100
        assert result.web_surfer.max_rounds == 100

    def test_reads_existing_values(self) -> None:
        result = _read_agent_settings(
            {
                "harness_config": {
                    "orchestrator": {"max_rounds": 25},
                    "web_surfer": {"max_rounds": 250},
                }
            }
        )
        assert result.orchestrator.max_rounds == 25
        assert result.web_surfer.max_rounds == 250

    def test_partial_section_falls_back_to_defaults(self) -> None:
        result = _read_agent_settings(
            {"harness_config": {"orchestrator": {"max_rounds": 25}}}
        )
        assert result.orchestrator.max_rounds == 25
        assert result.web_surfer.max_rounds == 100

    def test_corrupt_section_uses_defaults_no_500(self) -> None:
        result = _read_agent_settings(
            {"harness_config": {"orchestrator": "not-a-dict"}}
        )
        assert result.orchestrator.max_rounds == 100


class TestApplyAgentSettings:
    def test_writes_both_sections(self) -> None:
        config: dict[str, Any] = {}
        _apply_agent_settings(
            config,
            AgentSettings(
                orchestrator=OrchestratorAgentSettings(max_rounds=25),
                web_surfer=WebSurferAgentSettings(max_rounds=250),
            ),
        )
        assert config["harness_config"]["orchestrator"]["max_rounds"] == 25
        assert config["harness_config"]["web_surfer"]["max_rounds"] == 250

    def test_preserves_unrelated_harness_keys(self) -> None:
        config: dict[str, Any] = {
            "harness_config": {
                "orchestrator": {
                    "max_rounds": 5,
                    "approval_policy": "auto-approve",
                    "temperature": 0.2,
                },
            },
        }
        _apply_agent_settings(
            config,
            AgentSettings(
                orchestrator=OrchestratorAgentSettings(max_rounds=99),
                web_surfer=WebSurferAgentSettings(max_rounds=200),
            ),
        )
        assert config["harness_config"]["orchestrator"]["max_rounds"] == 99
        assert config["harness_config"]["orchestrator"]["approval_policy"] == (
            "auto-approve"
        )
        assert config["harness_config"]["orchestrator"]["temperature"] == 0.2


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------


def _make_test_app(initial_config: dict[str, Any]) -> tuple[TestClient, dict[str, Any]]:
    """Wire the settings router with a mocked DB.

    Returns the client plus a mutable ``state`` dict whose ``config`` key
    reflects what _save_db_config persists. The fixture intentionally
    mutates this dict in place so the test can assert on the post-PUT
    DB shape.
    """
    state: dict[str, Any] = {"config": dict(initial_config)}

    db = MagicMock()
    settings_row = Settings(  # pyright: ignore[reportCallIssue]
        user_id="default", config=state["config"]
    )

    def get_response() -> MagicMock:
        # Each get() returns the row pointing at the current state.
        settings_row.config = state["config"]
        resp = MagicMock()
        resp.status = True
        resp.data = [settings_row]
        return resp

    def upsert_response(row: Settings, **_: Any) -> MagicMock:
        # Capture writes the route makes via _save_db_config.
        state["config"] = dict(row.config) if isinstance(row.config, dict) else {}
        resp = MagicMock()
        resp.status = True
        return resp

    db.get = MagicMock(side_effect=lambda *_a, **_k: get_response())
    db.upsert = MagicMock(side_effect=upsert_response)

    app = FastAPI()
    app.include_router(settings_routes.router, prefix="/api/settings")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), state


class TestRoutes:
    def test_get_returns_defaults_when_db_empty(self) -> None:
        client, _ = _make_test_app({})
        resp = client.get("/api/settings/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] is True
        assert data["data"]["orchestrator"]["max_rounds"] == 100
        assert data["data"]["web_surfer"]["max_rounds"] == 100

    def test_put_with_both_sections_persists(self) -> None:
        client, state = _make_test_app({})
        resp = client.put(
            "/api/settings/agents",
            json={
                "orchestrator": {"max_rounds": 50},
                "web_surfer": {"max_rounds": 200},
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["orchestrator"]["max_rounds"] == 50
        assert data["web_surfer"]["max_rounds"] == 200
        assert state["config"]["harness_config"]["orchestrator"]["max_rounds"] == 50
        assert state["config"]["harness_config"]["web_surfer"]["max_rounds"] == 200

    def test_put_with_only_orchestrator_preserves_web_surfer(self) -> None:
        # Pre-existing DB state with both sub-sections.
        client, state = _make_test_app(
            {
                "harness_config": {
                    "orchestrator": {"max_rounds": 25},
                    "web_surfer": {"max_rounds": 300},
                }
            }
        )
        # Partial PUT: only orchestrator. The previously regressing path
        # would have reset web_surfer.max_rounds to 100 (schema default).
        resp = client.put(
            "/api/settings/agents",
            json={"orchestrator": {"max_rounds": 50}},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["orchestrator"]["max_rounds"] == 50
        assert data["web_surfer"]["max_rounds"] == 300
        # And the persisted DB shape mirrors the response.
        persisted = state["config"]["harness_config"]
        assert persisted["orchestrator"]["max_rounds"] == 50
        assert persisted["web_surfer"]["max_rounds"] == 300

    def test_put_with_only_web_surfer_preserves_orchestrator(self) -> None:
        client, state = _make_test_app(
            {
                "harness_config": {
                    "orchestrator": {"max_rounds": 25},
                    "web_surfer": {"max_rounds": 300},
                }
            }
        )
        resp = client.put(
            "/api/settings/agents",
            json={"web_surfer": {"max_rounds": 200}},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["orchestrator"]["max_rounds"] == 25
        assert data["web_surfer"]["max_rounds"] == 200

    def test_put_preserves_unrelated_harness_keys(self) -> None:
        client, state = _make_test_app(
            {
                "harness_config": {
                    "orchestrator": {
                        "max_rounds": 25,
                        "approval_policy": "auto-approve",
                        "temperature": 0.4,
                    },
                }
            }
        )
        resp = client.put(
            "/api/settings/agents",
            json={"orchestrator": {"max_rounds": 99}},
        )
        assert resp.status_code == 200
        orch = state["config"]["harness_config"]["orchestrator"]
        assert orch["max_rounds"] == 99
        assert orch["approval_policy"] == "auto-approve"
        assert orch["temperature"] == 0.4

    @pytest.mark.parametrize(
        "payload",
        [{"orchestrator": {"max_rounds": 0}}, {"web_surfer": {"max_rounds": 1001}}],
    )
    def test_put_rejects_out_of_range(self, payload: dict[str, Any]) -> None:
        client, _ = _make_test_app({})
        resp = client.put("/api/settings/agents", json=payload)
        assert resp.status_code == 422
