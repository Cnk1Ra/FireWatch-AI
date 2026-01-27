"""
FireWatch AI - Configuration Management
Centralized configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # NASA FIRMS
    firms_api_key: Optional[str] = None

    # Sentinel Hub (satellite imagery)
    sentinel_client_id: Optional[str] = None
    sentinel_client_secret: Optional[str] = None

    # OpenWeatherMap (backup weather)
    openweather_api_key: Optional[str] = None

    # Database
    database_url: Optional[str] = None
    redis_url: Optional[str] = None

    # Email (SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    # Twilio (SMS)
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Cache Settings
    cache_ttl_seconds: int = 300
    firms_cache_ttl_seconds: int = 180

    # Analysis Settings
    hotspot_clustering_distance_km: float = 5.0
    default_prediction_hours: int = 6

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
