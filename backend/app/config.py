"""
Application configuration.

Loads settings from environment variables.
All secrets and configuration live here — never hardcoded elsewhere.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic API
    anthropic_api_key: str = ""
    primary_model: str = "claude-sonnet-4-6"
    secondary_model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 8192
    api_timeout: int = 120  # seconds
    max_llm_retries: int = 3
    llm_retry_base_delay_seconds: float = 2.0

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

    # Build checker
    enable_full_build_check: bool = False
    full_build_timeout_seconds: int = 180
    build_check_node_path: str = "node"

    def validate_required(self) -> None:
        """Validate that required settings are configured. Call at startup."""
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to your .env file."
            )


# Singleton instance — import this wherever settings are needed
settings = Settings()
