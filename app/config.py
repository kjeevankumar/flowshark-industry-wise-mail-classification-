"""Configuration management for Gmail FastAPI Integration and AI Lead Intelligence.

Handles reading environment variables from .env files or system environment,
validates values with Pydantic, and prevents sensitive credentials from leaking in logs
or string representations.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for locating .env
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application configuration, database connection, and credentials."""

    # Gmail Credentials
    GMAIL_ADDRESS: Optional[str] = Field(
        default=None,
        description="Gmail email address used for IMAP and SMTP authentication",
    )
    GMAIL_APP_PASSWORD: Optional[SecretStr] = Field(
        default=None,
        description="Google Account App Password (16 characters, spaces optional)",
    )

    # IMAP Configuration
    IMAP_HOST: str = Field(default="imap.gmail.com", description="Gmail IMAP server host")
    IMAP_PORT: int = Field(default=993, description="Gmail IMAP SSL port (default 993)")
    IMAP_TIMEOUT_SECONDS: int = Field(default=30, description="Socket timeout in seconds for IMAP operations")

    # SMTP Configuration
    SMTP_HOST: str = Field(default="smtp.gmail.com", description="Gmail SMTP server host")
    SMTP_PORT: int = Field(default=587, description="Gmail SMTP STARTTLS port (default 587)")
    SMTP_TIMEOUT_SECONDS: int = Field(default=30, description="Socket timeout in seconds for SMTP operations")

    # Synchronization Configuration
    SYNC_INTERVAL_SECONDS: int = Field(default=30, ge=5, le=3600, description="Interval in seconds between automated background mailbox syncs")
    BACKGROUND_SYNC_ENABLED: bool = Field(default=True, description="Enable automated background email synchronization worker")

    # Database Configuration
    DATABASE_URL: str = Field(
        default=f"sqlite:///{BASE_DIR / 'data' / 'flowshark.db'}",
        description="SQLAlchemy database connection string (SQLite for local, PostgreSQL ready)",
    )

    # AI / LLM Configuration
    LLM_PROVIDER: str = Field(default="gemini", description="LLM provider: 'gemini', 'openai', or 'fallback'")
    LLM_MODEL: str = Field(default="gemini-2.5-flash", description="Model identifier for semantic classification")
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None, description="Google Gemini API Key")
    OPENAI_API_KEY: Optional[SecretStr] = Field(default=None, description="OpenAI API Key")

    # Classification Thresholds
    CONFIDENCE_HIGH: float = Field(default=0.85, description="High confidence threshold for auto-acceptance")
    CONFIDENCE_MEDIUM: float = Field(default=0.60, description="Medium confidence threshold")

    # Application settings
    APP_ENV: str = Field(default="development", description="Environment: development, testing, or production")
    APP_DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_configured(self) -> bool:
        """Returns True if both Gmail address and App Password are provided and non-empty."""
        if not self.GMAIL_ADDRESS or not self.GMAIL_ADDRESS.strip():
            return False
        if not self.GMAIL_APP_PASSWORD or not self.GMAIL_APP_PASSWORD.get_secret_value().strip():
            return False
        return True

    @property
    def clean_app_password(self) -> Optional[str]:
        """Returns the app password stripped of internal spaces (Google displays them as 4 groups of 4)."""
        if not self.GMAIL_APP_PASSWORD:
            return None
        raw = self.GMAIL_APP_PASSWORD.get_secret_value()
        if not raw:
            return None
        # Remove whitespace/tabs/newlines
        return "".join(raw.split())

    @property
    def masked_gmail_address(self) -> Optional[str]:
        """Safely mask email address for status inspection (e.g. j***e@gmail.com)."""
        if not self.GMAIL_ADDRESS or "@" not in self.GMAIL_ADDRESS:
            return None
        local_part, domain = self.GMAIL_ADDRESS.split("@", 1)
        if len(local_part) <= 2:
            masked_local = local_part[0] + "***"
        else:
            masked_local = local_part[0] + "***" + local_part[-1]
        return f"{masked_local}@{domain}"

    @property
    def clean_gemini_api_key(self) -> Optional[str]:
        """Return clean Gemini API key if set."""
        if not self.GEMINI_API_KEY:
            return None
        val = self.GEMINI_API_KEY.get_secret_value().strip()
        return val if val else None

    @property
    def clean_openai_api_key(self) -> Optional[str]:
        """Return clean OpenAI API key if set."""
        if not self.OPENAI_API_KEY:
            return None
        val = self.OPENAI_API_KEY.get_secret_value().strip()
        return val if val else None

    @property
    def is_llm_configured(self) -> bool:
        """Check if active LLM provider has an API key configured."""
        provider = self.LLM_PROVIDER.lower()
        if provider == "gemini":
            return bool(self.clean_gemini_api_key)
        elif provider == "openai":
            return bool(self.clean_openai_api_key)
        return False


@lru_cache
def get_settings() -> Settings:
    """Cached settings provider for dependency injection and application use."""
    return Settings()
