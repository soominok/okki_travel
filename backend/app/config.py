"""모든 환경변수의 단일 출입구.

CLAUDE.md 3번 규칙: os.getenv()를 코드 곳곳에 흩뿌리지 않는다.
어떤 모듈도 이 파일 밖에서 환경변수를 직접 읽지 않는다.
"""

from datetime import time
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core ---
    app_env: Literal["local", "staging", "prod"] = "local"
    app_api_token: str = Field(min_length=16)
    database_url: str
    public_web_url: str = "http://localhost:3000"
    log_level: str = "INFO"

    # --- Sources (없으면 해당 어댑터만 disabled. 앱은 정상 기동) ---
    travelpayouts_token: str | None = None
    travelpayouts_marker: str | None = None
    brightdata_api_key: str | None = None
    brightdata_monthly_credits: int = 5000
    brightdata_sample_cap_ratio: float = 0.70
    data_go_kr_key: str | None = None
    exim_api_key: str | None = None

    # --- Notify ---
    notify_channels: str = "slack,inapp"
    slack_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    alert_cooldown_hours: int = 12
    quiet_hours: str = "23:00-08:00"

    # --- Collect ---
    default_interval_min: int = 360
    verify_threshold_ratio: float = 1.15
    offer_retention_days: int = 90

    # --- Crawl (기본 off) ---
    crawl_enabled: bool = False
    crawl_min_interval_sec: int = 5
    http_user_agent: str = "TripPick/0.1 (personal price watcher)"

    @field_validator("brightdata_sample_cap_ratio")
    @classmethod
    def _ratio_in_range(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("brightdata_sample_cap_ratio must be in (0, 1]")
        return v

    @property
    def notify_channel_list(self) -> list[str]:
        return [c.strip() for c in self.notify_channels.split(",") if c.strip()]

    @property
    def quiet_hours_start(self) -> time:
        return self._parse_quiet()[0]

    @property
    def quiet_hours_end(self) -> time:
        return self._parse_quiet()[1]

    def _parse_quiet(self) -> tuple[time, time]:
        start_s, end_s = self.quiet_hours.split("-")
        return (time.fromisoformat(start_s.strip()), time.fromisoformat(end_s.strip()))


@lru_cache
def get_settings() -> Settings:
    return Settings()
