"""Configuration with fail-closed Phase 1 environment protection."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEMO_REST_URL = "https://demo-api-capital.backend-capital.com"
LIVE_REST_URL = "https://api-capital.backend-capital.com"
STREAM_URL = "wss://api-streaming-capital.backend-capital.com/connect"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    capital_env: Literal["demo", "live"] = "demo"
    capital_api_key: SecretStr = Field(default=SecretStr(""))
    capital_identifier: str = ""
    capital_api_password: SecretStr = Field(default=SecretStr(""))
    capital_account_id: str | None = None
    phase1_allow_live: bool = False
    capital_http_timeout_seconds: float = Field(default=15, gt=0)
    capital_max_retries: int = Field(default=3, ge=0, le=8)
    capital_flush_ticks: int = Field(default=1000, ge=1)
    capital_flush_interval_seconds: float = Field(default=10, gt=0)
    instruments_file: Path = Path("config/instruments.json")
    ticks_dir: Path = Path("data/ticks")
    reports_dir: Path = Path("data/reports")

    @model_validator(mode="after")
    def demo_only(self) -> "Settings":
        # The flag is intentionally not an override in Phase 1; it documents the hard guard.
        if self.capital_env != "demo" or self.phase1_allow_live:
            raise ValueError("Phase 1 permits DEMO only; live access is disabled")
        return self

    @property
    def rest_url(self) -> str:
        return DEMO_REST_URL

    def require_credentials(self) -> None:
        missing = []
        if not self.capital_api_key.get_secret_value():
            missing.append("CAPITAL_API_KEY")
        if not self.capital_identifier:
            missing.append("CAPITAL_IDENTIFIER")
        if not self.capital_api_password.get_secret_value():
            missing.append("CAPITAL_API_PASSWORD")
        if missing:
            raise ValueError("Missing demo credentials: " + ", ".join(missing))
