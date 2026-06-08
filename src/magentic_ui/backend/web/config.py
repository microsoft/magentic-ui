# api/config.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URI: str = "sqlite:///./magentic_ui.db"
    API_DOCS: bool = False
    DEFAULT_USER_ID: str = "guestuser@gmail.com"
    UPGRADE_DATABASE: bool = False

    model_config = {"env_prefix": "MAGENTIC_UI_"}


settings = Settings()
