# api/config.py

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URI: str = "sqlite:///./magentic_ui.db"
    API_DOCS: bool = False
    CLEANUP_INTERVAL: int = 300  # 5 minutes
    SESSION_TIMEOUT: int = 3600 * 100  # 24 hour
    CONFIG_DIR: str = "configs"  # Default config directory relative to app_root
    DEFAULT_USER_ID: str = "guestuser@gmail.com"
    UPGRADE_DATABASE: bool = False

    # --- Alerting (real-time alerts for stuck / failed runs) ---------------
    # All alert channels are disabled by default; opt in per-deployment.
    ALERTS_ENABLED: bool = False
    # How often the stuck-run monitor polls the database (seconds).
    ALERTS_POLL_INTERVAL_SECONDS: int = 30
    # Thresholds (seconds). Set any value to 0 to disable the corresponding rule.
    ALERTS_STUCK_INACTIVITY_SECONDS: int = 120
    ALERTS_START_TIMEOUT_SECONDS: int = 60
    ALERTS_AWAITING_INPUT_SECONDS: int = 600
    # Broadcast alerts to every connected UI WebSocket (safe default).
    ALERTS_WS_BROADCAST_ENABLED: bool = True
    # Optional outbound channels; leaving URLs empty disables them.
    ALERTS_WEBHOOK_URL: Optional[str] = None
    ALERTS_SLACK_WEBHOOK_URL: Optional[str] = None
    # Include a (potentially sensitive) task_summary / error_message in the
    # payload sent to external channels. Off by default to prevent leaks.
    ALERTS_INCLUDE_TASK_SUMMARY: bool = False

    model_config = {"env_prefix": "MAGENTIC_UI_"}


settings = Settings()
