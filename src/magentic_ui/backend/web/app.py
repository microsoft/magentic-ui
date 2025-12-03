# api/app.py
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Any, Callable, Awaitable

# import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from ...version import VERSION
from .auth import (
    bad_host_response,
    inject_token_into_html,
    is_allowed_host,
    require_api_auth,
)
from .config import settings
from .deps import cleanup_managers, get_db, init_db, init_managers
from .initialization import AppInitializer
from .routes.onboarding import reset_onboarding_config
from ..database.config_file_loader import load_config_file
from .routes import (
    filesystem,
    onboarding,
    runs,
    sessions,
    settings as settings_routes,
    trusted_folders,
    ws,
)

# Initialize application
app_file_path = os.path.dirname(os.path.abspath(__file__))
initializer = AppInitializer(settings, app_file_path)


class SPAStaticFiles(StaticFiles):
    """
    Static files handler with SPA fallback and session-token injection.

    Reads ``index.html`` once at construction (before the server accepts
    traffic), then serves an injected copy for every SPA entrypoint.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        index_path = Path(str(self.directory)) / "index.html"
        try:
            self._index_html: str | None = index_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._index_html = None

    async def get_response(self, path: str, scope: Any) -> Any:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                return self._serve_index_with_token()
            raise

        # StaticFiles with html=True serves index.html for GET "/" (which
        # Starlette normalises to path="."), and for direct /index.html
        # requests. In either case, inject the token.
        if path in ("", ".", "index.html"):
            return self._serve_index_with_token()
        return response

    def _serve_index_with_token(self) -> HTMLResponse:
        if self._index_html is None:
            return HTMLResponse("index.html not found", status_code=500)
        return HTMLResponse(
            inject_token_into_html(self._index_html),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifecycle manager for the FastAPI application.
    Handles initialization and cleanup of application resources.
    """
    try:
        # Step 1: Initialize database
        await init_db(
            database_uri=initializer.database_uri,
            app_root=initializer.app_root,
        )

        # Step 2: Seed DB from YAML / reset config (before sandbox startup)
        db = await get_db()
        if os.environ.get("_RESET_CONFIG") == "1":
            reset_onboarding_config(db)
            logger.info("Onboarding config reset via --reset-config flag")
        config_file = os.environ.get("_CONFIG")
        if config_file:
            logger.info(f"Loading config from file: {config_file}")
            if load_config_file(
                db,
                config_path=Path(config_file),
                user_id=settings.DEFAULT_USER_ID,
            ):
                logger.info("DB seeded from config file")

        # Step 3: Initialize sandbox + connection managers (reads config from DB)
        await init_managers(
            app_dir=os.environ.get("_APPDIR", str(Path.home() / ".magentic_ui")),
        )

        logger.info(
            f"Application startup complete. Navigate to http://{os.environ.get('_HOST', '127.0.0.1')}:{os.environ.get('_PORT', '8081')}"
        )

    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise

    yield  # Application runs here

    # Shutdown
    try:
        logger.info("Cleaning up application resources...")
        await cleanup_managers()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI application
app = FastAPI(lifespan=lifespan, debug=True)


# Request flow (outermost first): Host check → CORS → API auth → handler.
# FastAPI runs the LAST-registered middleware first, so we register in
# reverse: auth, then CORS, then Host validation.


@app.middleware("http")
async def api_auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
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
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if not is_allowed_host(request.headers.get("host", "")):
        return bad_host_response()
    return await call_next(request)


# Create API router with version and documentation
api = FastAPI(
    root_path="/api",
    title="MagenticLite API",
    version=VERSION,
    description="MagenticLite is an application to interact with web agents.",
    docs_url="/docs" if settings.API_DOCS else None,
)

# Include all routers with their prefixes
api.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["sessions"],
    responses={404: {"description": "Not found"}},
)

api.include_router(
    runs.router,
    prefix="/runs",
    tags=["runs"],
    responses={404: {"description": "Not found"}},
)

api.include_router(
    ws.router,
    prefix="/ws",
    tags=["websocket"],
    responses={404: {"description": "Not found"}},
)

api.include_router(
    filesystem.router,
    prefix="/filesystem",
    tags=["filesystem"],
)

api.include_router(
    trusted_folders.router,
    prefix="/trusted-folders",
    tags=["trusted-folders"],
)

api.include_router(
    onboarding.router,
    prefix="/onboarding",
    tags=["onboarding"],
    responses={404: {"description": "Not found"}},
)

api.include_router(
    settings_routes.router,
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}},
)


# Version endpoint


@api.get("/version")
async def get_version():
    """Get API version"""
    return {
        "status": True,
        "message": "Version retrieved successfully",
        "data": {"version": VERSION},
    }


# Health check endpoint


@api.get("/health")
async def health_check():
    """API health check endpoint"""
    return {
        "status": True,
        "message": "Service is healthy",
    }


# Mount static file directories
app.mount("/api", api)
app.mount(
    "/files",
    StaticFiles(directory=initializer.static_root, html=True),
    name="files",
)
# UI with SPA fallback - serves index.html for client-side routes
app.mount("/", SPAStaticFiles(directory=initializer.ui_root, html=True), name="ui")

# Error handlers


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Internal error: {str(exc)}")
    return {
        "status": False,
        "message": "Internal server error",
        "detail": str(exc) if settings.API_DOCS else "Internal server error",
    }


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    Useful for testing and different deployment scenarios.
    """
    return app
