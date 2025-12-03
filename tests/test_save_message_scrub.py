"""``_save_message`` must drop the per-slot VNC password before persisting.

The wire ``browser_address`` frame carries the live RFB password so noVNC
can authenticate silently. The persisted copy must not — the frontend
never reads it from history (the parser ignores ``metadata.password``),
and stored credentials at rest would be reachable via
``GET /runs/<id>/messages``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from magentic_ui.backend.web.managers.connection import WebSocketManager


def _make_ws_manager() -> tuple[WebSocketManager, MagicMock]:
    """Build a WebSocketManager with stubbed I/O. Returns (manager, db_manager)."""
    mgr = WebSocketManager.__new__(WebSocketManager)
    fake_run = MagicMock()
    fake_run.session_id = 7
    fake_run.user_id = "u"
    mgr._get_run = AsyncMock(return_value=fake_run)
    db_manager = MagicMock()
    db_manager.upsert = MagicMock()
    mgr.db_manager = db_manager
    return mgr, db_manager


def _saved_config(db_manager: MagicMock) -> dict[str, Any]:
    """Return the ``config`` dict passed to the most recent ``db.upsert`` call."""
    assert db_manager.upsert.call_count == 1
    db_message = db_manager.upsert.call_args.args[0]
    return db_message.config


@pytest.mark.asyncio
async def test_save_message_strips_browser_address_password() -> None:
    mgr, db = _make_ws_manager()
    message = {
        "source": "web_surfer",
        "content": [],
        "metadata": {
            "type": "browser_address",
            "source": "web_surfer",
            "novnc_port": "6080",
            "playwright_port": "9222",
            "password": "secret-token",
        },
    }
    await mgr._save_message(1, message)
    saved = _saved_config(db)
    assert "password" not in saved["metadata"]
    # Other browser_address fields survive.
    assert saved["metadata"]["novnc_port"] == "6080"
    assert saved["metadata"]["playwright_port"] == "9222"
    # The input dict must not be mutated.
    assert message["metadata"]["password"] == "secret-token"


@pytest.mark.asyncio
async def test_save_message_browser_address_without_password_unchanged() -> None:
    mgr, db = _make_ws_manager()
    message = {
        "source": "web_surfer",
        "content": [],
        "metadata": {
            "type": "browser_address",
            "source": "web_surfer",
            "novnc_port": "6080",
            "playwright_port": "9222",
        },
    }
    await mgr._save_message(2, message)
    saved = _saved_config(db)
    assert "password" not in saved["metadata"]
    assert saved["metadata"]["novnc_port"] == "6080"


@pytest.mark.asyncio
async def test_save_message_other_types_pass_through() -> None:
    """Non-browser_address messages are persisted verbatim — even fields
    that happen to be named ``password`` on other message types stay
    untouched. The scrub is targeted, not blanket."""
    mgr, db = _make_ws_manager()
    message = {
        "source": "system",
        "content": [{"type": "text", "text": "ok"}],
        "metadata": {
            "type": "system",
            "source": "system",
            "status": "complete",
            "password": "this-is-not-a-vnc-password",
        },
    }
    await mgr._save_message(3, message)
    saved = _saved_config(db)
    assert saved["metadata"]["password"] == "this-is-not-a-vnc-password"
