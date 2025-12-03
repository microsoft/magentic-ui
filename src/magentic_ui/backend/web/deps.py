# api/deps.py
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional
from pathlib import Path
from fastapi import HTTPException, status
from pydantic import ValidationError

from ..database import DatabaseManager
from .config import settings
from .managers.connection import WebSocketManager

from ...magentic_ui_config import (
    MagenticUIConfig,
    QuicksandSandboxConfig,
)

if TYPE_CHECKING:
    from ...tools.playwright.browser.quicksand_browser_manager import (
        QuicksandBrowserManager,
    )

logger = logging.getLogger(__name__)

# Global manager instances
_db_manager: Optional[DatabaseManager] = None
_websocket_manager: Optional[WebSocketManager] = None
_quicksand_manager: Optional["QuicksandBrowserManager"] = None


async def wait_for_quicksand() -> Optional["QuicksandBrowserManager"]:
    """Return quicksand manager if configured and started, else None."""
    if _quicksand_manager is None or not _quicksand_manager.is_ready:
        return None
    return _quicksand_manager


# Context manager for database sessions


@contextmanager
def get_db_context():
    """Provide a transactional scope around a series of operations."""
    if not _db_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database manager not initialized",
        )
    try:
        yield _db_manager
    except Exception as e:
        logger.error(f"Database operation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from e


# Dependency providers


async def get_db() -> DatabaseManager:
    """Dependency provider for database manager"""
    if not _db_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database manager not initialized",
        )
    return _db_manager


async def get_websocket_manager() -> WebSocketManager:
    """Dependency provider for connection manager"""
    if not _websocket_manager:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Connection manager not initialized",
        )
    return _websocket_manager


# Manager initialization and cleanup


async def init_db(
    database_uri: str,
    app_root: Path,
) -> None:
    """Initialize the database manager only."""
    global _db_manager

    logger.info("Initializing database...")
    _db_manager = DatabaseManager(engine_uri=database_uri, base_dir=app_root)
    _db_manager.initialize_database(auto_upgrade=settings.UPGRADE_DATABASE)


async def init_managers(
    app_dir: str,
) -> None:
    """Initialize sandbox and connection managers.

    Must be called after init_db() and any config seeding, so that
    config can be read from DB (the single source of truth).
    """
    global _websocket_manager, _quicksand_manager

    if not _db_manager:
        raise RuntimeError("init_db() must be called before init_managers()")

    logger.info("Initializing managers...")

    try:
        # Read config from DB (single source of truth) and validate via pydantic.
        from ...backend.datamodel import Settings

        db_resp = _db_manager.get(
            Settings, filters={"user_id": settings.DEFAULT_USER_ID}
        )
        if not db_resp.status:
            raise RuntimeError("Failed to read settings from DB during startup")
        if db_resp.data:
            cfg_val = db_resp.data[0].config  # pyright: ignore[reportUnknownMemberType]
            raw_config = dict(cfg_val) if isinstance(cfg_val, dict) else {}  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        else:
            raw_config = {}

        try:
            runtime_config = MagenticUIConfig.model_validate(raw_config)
        except ValidationError as e:
            logger.warning("Invalid config in DB: %s. Falling back to defaults.", e)
            runtime_config = MagenticUIConfig()

        # Initialize Quicksand browser manager if sandbox type is quicksand
        if isinstance(runtime_config.sandbox, QuicksandSandboxConfig):
            from ...sandbox._quicksand import QuicksandSandbox
            from ...tools.playwright.browser.quicksand_browser_manager import (
                QuicksandBrowserManager,
            )

            # Create browser manager first (allocates ports in __init__),
            # then create sandbox with those port forwards.
            _quicksand_manager = QuicksandBrowserManager(
                pool_size=runtime_config.sandbox.pool_size,
            )
            _quicksand_sandbox = QuicksandSandbox(
                memory=runtime_config.sandbox.memory,
                cpus=runtime_config.sandbox.cpus,
                port_forwards=_quicksand_manager.port_forwards,
            )
            _quicksand_manager.sandbox = _quicksand_sandbox

            # Boot VM synchronously — users can't do anything until it's ready.
            await _quicksand_sandbox.__aenter__()
            await _quicksand_manager.start()  # type: ignore[union-attr]
            logger.info("Quicksand sandbox + browser manager initialized")

        # Initialize connection manager
        _websocket_manager = WebSocketManager(
            db_manager=_db_manager,
            app_dir=Path(app_dir),
            config=runtime_config,
            quicksand_manager=_quicksand_manager,
        )
        logger.info("Connection manager initialized")

    except Exception as e:
        logger.error(f"Failed to initialize managers: {str(e)}")
        await cleanup_managers()  # Cleanup any partially initialized managers
        raise


async def cleanup_managers() -> None:
    """Cleanup and shutdown all manager instances"""
    global _db_manager, _websocket_manager, _quicksand_manager

    logger.info("Cleaning up managers...")

    # Cleanup connection manager first to ensure all active connections are closed
    if _websocket_manager:
        try:
            await _websocket_manager.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up connection manager: {str(e)}")
        finally:
            _websocket_manager = None

    # Cleanup Quicksand: stop browser manager, then exit sandbox (saves VM + stops QEMU)
    if _quicksand_manager:
        try:
            await _quicksand_manager.stop()
        except Exception:
            logger.exception("Error stopping Quicksand browser manager")
        try:
            await _quicksand_manager.sandbox.__aexit__(None, None, None)
        except Exception:
            logger.exception("Error stopping Quicksand sandbox VM")
        _quicksand_manager = None

    # Cleanup database manager last
    if _db_manager:
        try:
            await _db_manager.close()
        except Exception as e:
            logger.error(f"Error cleaning up database manager: {str(e)}")
        finally:
            _db_manager = None

    logger.info("All managers cleaned up")


# Utility functions for dependency management


# Error handling for manager operations


class ManagerOperationError(Exception):
    """Custom exception for manager operation errors"""

    def __init__(self, manager_name: str, operation: str, detail: str):
        self.manager_name = manager_name
        self.operation = operation
        self.detail = detail
        super().__init__(f"{manager_name} failed during {operation}: {detail}")
