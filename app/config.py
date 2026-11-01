import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings."""
    app_name: str = "Signal2Insight API"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    port: int = 8000
    host: str = "0.0.0.0"

    # LLM API Keys (optional; system falls back to smart mock engine if absent)
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    llm_provider: str = "auto"  # 'openai', 'gemini', or 'auto'

    # Storage settings
    sqlite_db_path: str = "signal2insight.db"
    enable_seed_data: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
