import os
from typing import Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""
    app_name: str = "Signal2Insight API"
    app_version: str = "1.0.0"
    app_env: str = "production"
    debug: bool = False
    port: int = 8000
    host: str = "0.0.0.0"

    # LLM API Keys (optional; system falls back to smart mock engine if absent)
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    llm_provider: str = "auto"  # 'openai', 'gemini', or 'auto'

    # Storage settings
    sqlite_db_path: str = "signal2insight.db"
    enable_seed_data: bool = False  # Production real-data mode: No demo data loaded

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, v: Any) -> bool:
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in ("release", "prod", "production", "false", "0", "no"):
                return False
            if clean in ("debug", "dev", "development", "true", "1", "yes"):
                return True
        return bool(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
