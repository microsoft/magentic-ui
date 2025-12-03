"""``_scrub_for_log`` must recursively redact sensitive keys before logging.

The backend logger formats outgoing WebSocket frames as dicts; some carry
per-slot RFB passwords (``browser_address`` messages) or other secrets.
``_scrub_for_log`` walks the structure and replaces values of known-sensitive
keys with ``***REDACTED***`` regardless of nesting depth.
"""

from __future__ import annotations

from typing import Any

from magentic_ui.backend.web.managers.connection import _scrub_for_log


def test_top_level_password_redacted() -> None:
    result = _scrub_for_log({"password": "secret-token"})
    assert result == {"password": "***REDACTED***"}


def test_nested_password_redacted() -> None:
    msg = {"type": "message", "data": {"metadata": {"password": "secret-token"}}}
    result = _scrub_for_log(msg)
    assert result == {
        "type": "message",
        "data": {"metadata": {"password": "***REDACTED***"}},
    }


def test_deeply_nested_password_redacted() -> None:
    msg = {"a": {"b": {"c": {"d": {"password": "secret-token"}}}}}
    result = _scrub_for_log(msg)
    assert result == {"a": {"b": {"c": {"d": {"password": "***REDACTED***"}}}}}


def test_password_inside_list_of_dicts_redacted() -> None:
    msg = {
        "items": [
            {"password": "a"},
            {"password": "b"},
            {"other": "c"},
        ]
    }
    result = _scrub_for_log(msg)
    assert result == {
        "items": [
            {"password": "***REDACTED***"},
            {"password": "***REDACTED***"},
            {"other": "c"},
        ]
    }


def test_all_sensitive_keys_redacted() -> None:
    msg = {
        "password": "p",
        "token": "t",
        "api_key": "k",
        "secret": "s",
        "normal": "n",
    }
    result = _scrub_for_log(msg)
    assert result == {
        "password": "***REDACTED***",
        "token": "***REDACTED***",
        "api_key": "***REDACTED***",
        "secret": "***REDACTED***",
        "normal": "n",
    }


def test_case_insensitive_match() -> None:
    msg = {"PASSWORD": "x", "Token": "y", "API_KEY": "z"}
    result = _scrub_for_log(msg)
    assert result == {
        "PASSWORD": "***REDACTED***",
        "Token": "***REDACTED***",
        "API_KEY": "***REDACTED***",
    }


def test_non_sensitive_keys_unchanged() -> None:
    msg = {"username": "u", "port": 9999, "url": "http://x"}
    result = _scrub_for_log(msg)
    assert result == msg


def test_primitives_pass_through_unchanged() -> None:
    assert _scrub_for_log("hello") == "hello"
    assert _scrub_for_log(42) == 42
    assert _scrub_for_log(True) is True
    assert _scrub_for_log(None) is None
    assert _scrub_for_log([1, 2, 3]) == [1, 2, 3]


def test_empty_structures_pass_through() -> None:
    assert _scrub_for_log({}) == {}
    assert _scrub_for_log([]) == []


def test_real_browser_address_message_redacted() -> None:
    """Repro of the exact message shape the bug produced in logs."""
    msg: dict[str, Any] = {
        "type": "message",
        "data": {
            "source": "web_surfer",
            "content": [{"type": "text", "text": "Browser ready at noVNC port 59253"}],
            "metadata": {
                "source": "web_surfer",
                "type": "browser_address",
                "novnc_port": "59253",
                "playwright_port": "51305",
                "password": "secret-token",
            },
        },
    }
    result = _scrub_for_log(msg)
    metadata = result["data"]["metadata"]  # type: ignore[index]
    assert metadata["password"] == "***REDACTED***"
    assert metadata["novnc_port"] == "59253"  # unchanged
    assert metadata["type"] == "browser_address"  # unchanged


def test_original_input_not_mutated() -> None:
    msg = {"password": "secret-token"}
    _scrub_for_log(msg)
    assert msg == {"password": "secret-token"}  # original untouched
