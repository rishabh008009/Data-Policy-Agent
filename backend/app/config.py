"""Environment configuration for the Data Policy Agent."""

from functools import lru_cache
from typing import List, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = "Data Policy Agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Application database settings (for storing policies, rules, violations)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/policy_agent"

    # LLM settings
    llm_provider: Literal["openai", "gemini"] = "openai"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = "gpt-4o"

    # PDF processing settings
    max_pdf_size_mb: int = 10

    # Monitoring settings
    min_scan_interval_minutes: int = 60
    max_scan_interval_minutes: int = 1440
    default_scan_interval_minutes: int = 360

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
