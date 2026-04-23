# api/deps.py
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional
from pathlib import Path
from fastapi import HTTPException, status

from ..database import DatabaseManager
from .alerts import AlertDispatcher
from .alerts.channels import (
    SlackChannel,
    WebhookChannel,
    WebSocketBroadcastChannel,
)
from .config import settings
from .managers.alert_monitor import AlertMonitor, AlertThresholds
from .managers.connection import WebSocketManager

logger = logging.getLogger(__name__)

# Global manager instances
_db_manager: Optional[DatabaseManager] = None
_websocket_manager: Optional[WebSocketManager] = None
_alert_dispatcher: Optional[AlertDispatcher] = None
_alert_monitor: Optional[AlertMonitor] = None

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


def get_alert_dispatcher() -> Optional[AlertDispatcher]:
    """Return the configured alert dispatcher, if any."""
    return _alert_dispatcher


# Manager initialization and cleanup


async def init_managers(
    database_uri: str,
    config_dir: Path,
    app_root: Path,
    internal_workspace_root: str,
    external_workspace_root: str,
    inside_docker: bool,
    config: Dict[str, Any],
    run_without_docker: bool,
) -> None:
    """Initialize all manager instances"""
    global _db_manager, _websocket_manager, _team_manager
    global _alert_dispatcher, _alert_monitor

    logger.info("Initializing managers...")

    try:
        # Initialize database manager
        _db_manager = DatabaseManager(engine_uri=database_uri, base_dir=app_root)
        _db_manager.initialize_database(auto_upgrade=settings.UPGRADE_DATABASE)

        # Initialize connection manager
        _websocket_manager = WebSocketManager(
            db_manager=_db_manager,
            internal_workspace_root=Path(internal_workspace_root),
            external_workspace_root=Path(external_workspace_root),
            inside_docker=inside_docker,
            config=config,
            run_without_docker=run_without_docker,
        )
        logger.info("Connection manager initialized")

        # Initialize alerting (opt-in via MAGENTIC_UI_ALERTS_* env vars).
        if settings.ALERTS_ENABLED:
            _alert_dispatcher = AlertDispatcher()
            if settings.ALERTS_WS_BROADCAST_ENABLED:
                _alert_dispatcher.register(
                    WebSocketBroadcastChannel(
                        _websocket_manager.broadcast,
                        include_task_summary=settings.ALERTS_INCLUDE_TASK_SUMMARY,
                    )
                )
            if settings.ALERTS_WEBHOOK_URL:
                _alert_dispatcher.register(
                    WebhookChannel(
                        settings.ALERTS_WEBHOOK_URL,
                        include_task_summary=settings.ALERTS_INCLUDE_TASK_SUMMARY,
                    )
                )
            if settings.ALERTS_SLACK_WEBHOOK_URL:
                _alert_dispatcher.register(
                    SlackChannel(
                        settings.ALERTS_SLACK_WEBHOOK_URL,
                        include_task_summary=settings.ALERTS_INCLUDE_TASK_SUMMARY,
                    )
                )
            _websocket_manager.set_alert_dispatcher(_alert_dispatcher)
            thresholds = AlertThresholds(
                stuck_inactivity_seconds=settings.ALERTS_STUCK_INACTIVITY_SECONDS
                or None,
                start_timeout_seconds=settings.ALERTS_START_TIMEOUT_SECONDS or None,
                awaiting_input_seconds=settings.ALERTS_AWAITING_INPUT_SECONDS
                or None,
                poll_interval_seconds=settings.ALERTS_POLL_INTERVAL_SECONDS,
            )
            _alert_monitor = AlertMonitor(
                db_manager=_db_manager,
                dispatcher=_alert_dispatcher,
                thresholds=thresholds,
            )
            await _alert_monitor.start()
            logger.info(
                "Alert monitor started with %d channel(s)",
                len(_alert_dispatcher.channels),
            )
        else:
            logger.info("Alerting disabled (MAGENTIC_UI_ALERTS_ENABLED=false)")

    except Exception as e:
        logger.error(f"Failed to initialize managers: {str(e)}")
        await cleanup_managers()  # Cleanup any partially initialized managers
        raise


async def cleanup_managers() -> None:
    """Cleanup and shutdown all manager instances"""
    global _db_manager, _websocket_manager, _team_manager
    global _alert_dispatcher, _alert_monitor

    logger.info("Cleaning up managers...")

    # Stop the alert monitor before tearing down its dependencies.
    if _alert_monitor:
        try:
            await _alert_monitor.stop()
        except Exception as e:
            logger.error(f"Error stopping alert monitor: {str(e)}")
        finally:
            _alert_monitor = None
    _alert_dispatcher = None

    # Cleanup connection manager first to ensure all active connections are closed
    if _websocket_manager:
        try:
            await _websocket_manager.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up connection manager: {str(e)}")
        finally:
            _websocket_manager = None

    # TeamManager doesn't need explicit cleanup since WebSocketManager handles it
    _team_manager = None

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
