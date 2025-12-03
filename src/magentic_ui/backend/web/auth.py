"""Session-token authentication for the backend API and WebSocket.

Random per-process token, injected into the served ``index.html`` for
the prod frontend and bypassed when requests come from Vite's dev
origin. See README for the full threat model.
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

# 256 bits of entropy, URL-safe base64. Process-lifetime only.
SESSION_TOKEN: str = secrets.token_urlsafe(32)

# Sec-WebSocket-Protocol tag used for the WS handshake. Client offers
# [WS_PROTOCOL_TAG, <token>], server echoes WS_PROTOCOL_TAG on accept.
WS_PROTOCOL_TAG = "magui.auth.bearer"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def is_valid_token(token: str) -> bool:
    return hmac.compare_digest(token.encode(), SESSION_TOKEN.encode())


def is_valid_bearer_header(header_value: str) -> bool:
    if not header_value.startswith("Bearer "):
        return False
    return is_valid_token(header_value[len("Bearer ") :])


# ---------------------------------------------------------------------------
# Public-path allowlist
# ---------------------------------------------------------------------------

PUBLIC_API_PATHS: frozenset[str] = frozenset(
    {
        "/api/health",
        "/api/version",
    }
)


def is_public_path(path: str) -> bool:
    return path in PUBLIC_API_PATHS


# ---------------------------------------------------------------------------
# Dev-mode origin bypass
# ---------------------------------------------------------------------------

# Defends against browser-based attackers only: Origin and Referer are
# forbidden request headers, so in-browser JavaScript cannot forge
# them. Non-browser clients (curl, shell scripts, malicious local
# processes) can set any header they want and bypass this check —
# that's out of scope, matching the token-in-HTML model (a local
# process can also scrape the token from the HTML shell).
DEV_ORIGINS: frozenset[str] = frozenset(
    {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
)


def is_dev_origin_request(request: Request) -> bool:
    if request.headers.get("origin", "") in DEV_ORIGINS:
        return True
    referer = request.headers.get("referer", "")
    return any(referer == dev or referer.startswith(dev + "/") for dev in DEV_ORIGINS)


# ---------------------------------------------------------------------------
# HTML injection
# ---------------------------------------------------------------------------


def inject_token_into_html(html: str) -> str:
    # SESSION_TOKEN is URL-safe base64 (A-Za-z0-9_-), so no JS string
    # escaping is needed when wrapped in double quotes.
    script = f'<script>window.__MAGUI_TOKEN__="{SESSION_TOKEN}";</script>'
    if "</head>" in html:
        return html.replace("</head>", f"{script}</head>", 1)
    return script + html


# ---------------------------------------------------------------------------
# Host header allowlist (DNS-rebinding defense)
# ---------------------------------------------------------------------------

_ALLOWED_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1"})


def is_allowed_host(host_header: str) -> bool:
    if not host_header:
        return True
    host = host_header.rsplit(":", 1)[0]
    return host in _ALLOWED_HOSTS


# ---------------------------------------------------------------------------
# Middleware helpers (wired up in app.py)
# ---------------------------------------------------------------------------


def unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"status": False, "message": "Unauthorized"},
    )


def bad_host_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"status": False, "message": "Bad Host header"},
    )


async def require_api_auth(request: Request) -> JSONResponse | None:
    """Return a 401 response if auth is required and missing; ``None`` otherwise."""
    path = request.url.path
    if not path.startswith("/api/"):
        return None
    if is_public_path(path):
        return None
    if is_dev_origin_request(request):
        return None
    if not is_valid_bearer_header(request.headers.get("authorization", "")):
        return unauthorized_response()
    return None
