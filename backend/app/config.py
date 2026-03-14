"""
Application configuration.

Loads settings from environment variables.
All secrets and configuration live here — never hardcoded elsewhere.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API
    anthropic_api_key: str
    primary_model: str = "claude-sonnet-4-5-20250514"
    secondary_model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 8192
    api_timeout: int = 120  # seconds

    # Pipeline settings
    max_code_revision_cycles: int = 2
    max_design_revision_cycles: int = 1
    max_clarification_rounds: int = 3

    # API security
    api_key: str = ""  # Shared secret for frontend-backend auth

    # Database
    database_path: str = "aegis.db"

    # Output
    output_dir: str = "outputs"  # Where generated code projects are saved

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance — import this wherever settings are needed
settings = Settings()
