# pyright: reportUnusedFunction=false
#
# FastAPI route handlers inside _build_app() are registered via `@app.get(...)`
# / `@app.middleware(...)` decorators; pyright can't follow that indirection
# and would flag each handler as unused. We don't need any other suppressions.

"""Integration tests for the session-auth middleware and WS handshake.

These build a minimal FastAPI app that wires the same middleware + a
WebSocket endpoint that reuses the real authentication helper. Keeping
the test app small avoids pulling the full magentic-ui server
(database init, sandbox managers, etc.) into the fixture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Generator

import pytest
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.testclient import TestClient

from magentic_ui.backend.web.app import SPAStaticFiles
from magentic_ui.backend.web.auth import (
    SESSION_TOKEN,
    WS_PROTOCOL_TAG,
    bad_host_response,
    is_allowed_host,
    require_api_auth,
)
from magentic_ui.backend.web.routes.ws import authenticate_websocket


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def api_auth_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        unauthorized = await require_api_auth(request)
        if unauthorized is not None:
            return unauthorized
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def host_header_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not is_allowed_host(request.headers.get("host", "")):
            return bad_host_response()
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/version")
    async def version() -> dict[str, str]:
        return {"version": "test"}

    @app.get("/api/sessions")
    async def sessions() -> dict[str, object]:
        return {"ok": True, "data": []}

    @app.websocket("/api/ws/runs/{run_id}")
    async def ws_endpoint(websocket: WebSocket, run_id: int) -> None:
        allowed, subprotocol = authenticate_websocket(websocket)
        if not allowed:
            await websocket.close(code=4401, reason="Unauthorized")
            return
        await websocket.accept(subprotocol=subprotocol)
        await websocket.send_json({"run_id": run_id, "ok": True})
        await websocket.close()

    return app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # Override default Host (`testserver`) so the Host-header middleware
    # accepts TestClient requests out of the box. Using `with` ensures
    # lifespan + WS cleanup between tests — without it, a successful WS
    # connect can leave event-loop state that pollutes the next test.
    with TestClient(_build_app(), base_url="http://localhost") as c:
        yield c


# ---------------------------------------------------------------------------
# HTTP auth middleware
# ---------------------------------------------------------------------------


class TestApiAuthMiddleware:
    def test_health_public(self, client: TestClient):
        assert client.get("/api/health").status_code == 200

    def test_version_public(self, client: TestClient):
        assert client.get("/api/version").status_code == 200

    def test_protected_route_requires_token(self, client: TestClient):
        r = client.get("/api/sessions")
        assert r.status_code == 401
        assert r.json()["status"] is False

    def test_protected_route_accepts_valid_token(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )
        assert r.status_code == 200

    def test_protected_route_rejects_wrong_token(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Authorization": "Bearer not-the-real-token"},
        )
        assert r.status_code == 401

    def test_protected_route_rejects_wrong_scheme(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Authorization": f"Token {SESSION_TOKEN}"},
        )
        assert r.status_code == 401

    def test_dev_origin_bypass(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Origin": "http://localhost:5173"},
        )
        assert r.status_code == 200

    def test_dev_origin_loopback_variant(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        assert r.status_code == 200

    def test_other_origin_still_requires_token(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Origin": "http://evil.com"},
        )
        assert r.status_code == 401

    def test_dev_referer_bypass_when_origin_missing(self, client: TestClient):
        # Simulates a browser same-origin GET from Vite: no Origin, but
        # Referer is populated from the page URL.
        r = client.get(
            "/api/sessions",
            headers={"Referer": "http://localhost:5173/sessions"},
        )
        assert r.status_code == 200

    def test_non_dev_referer_still_requires_token(self, client: TestClient):
        r = client.get(
            "/api/sessions",
            headers={"Referer": "http://evil.com/"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Host header middleware (DNS-rebinding defense)
# ---------------------------------------------------------------------------


class TestHostHeaderMiddleware:
    def test_allowed_localhost(self, client: TestClient):
        r = client.get("/api/health", headers={"Host": "localhost:8081"})
        assert r.status_code == 200

    def test_allowed_loopback(self, client: TestClient):
        r = client.get("/api/health", headers={"Host": "127.0.0.1:8081"})
        assert r.status_code == 200

    def test_rejects_foreign_host(self, client: TestClient):
        r = client.get("/api/health", headers={"Host": "evil.com"})
        assert r.status_code == 400
        assert r.json()["status"] is False


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCors:
    def test_preflight_from_allowed_origin(self, client: TestClient):
        r = client.options(
            "/api/sessions",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_preflight_from_disallowed_origin(self, client: TestClient):
        r = client.options(
            "/api/sessions",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code == 400
        assert "access-control-allow-origin" not in r.headers


# ---------------------------------------------------------------------------
# WebSocket auth
# ---------------------------------------------------------------------------


class TestSPAStaticFilesInjection:
    """Regression test: the mounted SPA handler must inject the token into
    the HTML shell for every entry point (`/`, `/index.html`, and SPA
    fallback paths). Starlette hands the path ``"."`` for `GET /`, which
    is easy to miss in a naive equality check.
    """

    @pytest.fixture
    def spa_client(self, tmp_path: Path) -> TestClient:
        (tmp_path / "index.html").write_text(
            "<html><head></head><body></body></html>", encoding="utf-8"
        )
        app = FastAPI()
        app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
        return TestClient(app, base_url="http://localhost")

    @pytest.mark.parametrize(
        "path",
        ["/", "/index.html", "/settings", "/sessions/abc/xyz"],
    )
    def test_token_is_injected(self, spa_client: TestClient, path: str):
        r = spa_client.get(path)
        assert r.status_code == 200
        assert 'window.__MAGUI_TOKEN__="' in r.text
        # Guard against caching the token in a CDN or browser.
        assert "no-store" in (r.headers.get("cache-control") or "")


class TestWebSocketAuth:
    """Tests for `authenticate_websocket()`: subprotocol bearer, dev-origin
    bypass, and Host-header check."""

    @staticmethod
    def _ws(
        *,
        host: str = "localhost",
        origin: str = "",
        subprotocols: list[str] | None = None,
    ):
        from unittest.mock import MagicMock
        from fastapi import WebSocket

        ws = MagicMock(spec=WebSocket)
        ws.headers = {"host": host}
        if origin:
            ws.headers["origin"] = origin
        ws.scope = {"subprotocols": subprotocols or []}
        return ws

    def test_accepts_valid_subprotocol_token(self):
        ws = self._ws(subprotocols=[WS_PROTOCOL_TAG, SESSION_TOKEN])
        assert authenticate_websocket(ws) == (True, WS_PROTOCOL_TAG)

    def test_rejects_wrong_token(self):
        ws = self._ws(subprotocols=[WS_PROTOCOL_TAG, "wrong-token"])
        assert authenticate_websocket(ws) == (False, None)

    def test_rejects_no_subprotocol_from_non_dev_origin(self):
        ws = self._ws()
        assert authenticate_websocket(ws) == (False, None)

    def test_rejects_wrong_subprotocol_tag(self):
        ws = self._ws(subprotocols=["wrong.tag", SESSION_TOKEN])
        assert authenticate_websocket(ws) == (False, None)

    def test_accepts_dev_origin_without_token(self):
        ws = self._ws(origin="http://localhost:5173")
        assert authenticate_websocket(ws) == (True, None)

    def test_rejects_disallowed_host(self):
        ws = self._ws(
            host="evil.com",
            subprotocols=[WS_PROTOCOL_TAG, SESSION_TOKEN],
        )
        assert authenticate_websocket(ws) == (False, None)

    def test_smoke_end_to_end_handshake(self):
        """End-to-end handshake through a real TestClient."""
        with TestClient(_build_app(), base_url="http://localhost") as c:
            with c.websocket_connect(
                "/api/ws/runs/42",
                subprotocols=[WS_PROTOCOL_TAG, SESSION_TOKEN],
                headers={"Host": "localhost"},
            ) as ws:
                assert ws.receive_json() == {"run_id": 42, "ok": True}
