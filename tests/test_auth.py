"""Unit tests for the session-auth helpers in backend/web/auth.py."""

from unittest.mock import MagicMock

import pytest
from fastapi import Request

from magentic_ui.backend.web import auth


class TestTokenValidation:
    def test_valid_token_accepts_current_session_token(self):
        assert auth.is_valid_token(auth.SESSION_TOKEN)

    def test_valid_token_rejects_wrong(self):
        assert not auth.is_valid_token("wrong-token")

    def test_valid_token_rejects_empty(self):
        assert not auth.is_valid_token("")

    def test_bearer_header_valid(self):
        assert auth.is_valid_bearer_header(f"Bearer {auth.SESSION_TOKEN}")

    def test_bearer_header_wrong_scheme(self):
        assert not auth.is_valid_bearer_header(f"Token {auth.SESSION_TOKEN}")

    def test_bearer_header_missing_token(self):
        assert not auth.is_valid_bearer_header("Bearer ")

    def test_bearer_header_empty(self):
        assert not auth.is_valid_bearer_header("")


class TestPublicPath:
    @pytest.mark.parametrize("path", ["/api/health", "/api/version"])
    def test_public(self, path: str):
        assert auth.is_public_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            "/api/sessions",
            "/api/runs",
            "/api/onboarding/status",
            "/api/filesystem/list",
            "/",
            "/api/",
        ],
    )
    def test_not_public(self, path: str):
        assert not auth.is_public_path(path)


class TestDevOriginRequest:
    def _request(self, origin: str = "", referer: str = "") -> Request:
        req = MagicMock(spec=Request)
        headers = {}
        if origin:
            headers["origin"] = origin
        if referer:
            headers["referer"] = referer
        req.headers = headers
        return req

    @pytest.mark.parametrize(
        "origin",
        ["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    def test_dev_origins_accepted(self, origin: str):
        assert auth.is_dev_origin_request(self._request(origin=origin))

    @pytest.mark.parametrize(
        "origin",
        [
            "",
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://evil.com",
            "http://localhost:3000",
            "https://localhost:5173",  # different scheme
        ],
    )
    def test_non_dev_origins_rejected(self, origin: str):
        assert not auth.is_dev_origin_request(self._request(origin=origin))

    @pytest.mark.parametrize(
        "referer",
        [
            "http://localhost:5173",
            "http://localhost:5173/",
            "http://localhost:5173/sessions/abc",
            "http://127.0.0.1:5173/anything",
        ],
    )
    def test_dev_referer_accepted_when_origin_missing(self, referer: str):
        assert auth.is_dev_origin_request(self._request(referer=referer))

    @pytest.mark.parametrize(
        "referer",
        [
            "",
            "http://evil.com/",
            "http://localhost:5173.evil.com/",  # prefix-match attack
            "http://localhost:5173evil.com/",
            "http://localhost:3000/",
        ],
    )
    def test_non_dev_referer_rejected(self, referer: str):
        assert not auth.is_dev_origin_request(self._request(referer=referer))

    def test_origin_wins_when_both_present(self):
        # An evil Referer cannot override a trusted Origin check; just
        # verify the function still returns True when at least one source
        # vouches for the request.
        assert auth.is_dev_origin_request(
            self._request(
                origin="http://localhost:5173",
                referer="http://evil.com/",
            )
        )


class TestInjectTokenIntoHtml:
    def test_injected_before_close_head(self):
        html = "<html><head><title>x</title></head><body></body></html>"
        out = auth.inject_token_into_html(html)
        assert "window.__MAGUI_TOKEN__" in out
        assert auth.SESSION_TOKEN in out
        # Script must appear before </head>
        assert out.index("window.__MAGUI_TOKEN__") < out.index("</head>")

    def test_prepended_when_no_head(self):
        html = "<html><body></body></html>"
        out = auth.inject_token_into_html(html)
        assert out.startswith("<script>")
        assert "window.__MAGUI_TOKEN__" in out

    def test_only_replaces_first_close_head(self):
        html = "<html><head></head><body><!-- </head> --></body></html>"
        out = auth.inject_token_into_html(html)
        # Script injected once, at the real </head>
        assert out.count("<script>window.__MAGUI_TOKEN__") == 1


class TestAllowedHost:
    @pytest.mark.parametrize(
        "host",
        [
            "",  # Missing header allowed
            "localhost",
            "localhost:8081",
            "127.0.0.1",
            "127.0.0.1:5173",
        ],
    )
    def test_allowed(self, host: str):
        assert auth.is_allowed_host(host)

    @pytest.mark.parametrize(
        "host",
        [
            "evil.com",
            "evil.com:8081",
            "attacker.example",
            "192.168.1.10:8081",
        ],
    )
    def test_rejected(self, host: str):
        assert not auth.is_allowed_host(host)
