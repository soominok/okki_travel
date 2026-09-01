from app.config import Settings


def test_missing_source_keys_are_none_not_error(monkeypatch):
    """키가 없어도 앱은 떠야 한다. 해당 어댑터만 나중에 disabled 처리된다."""
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)

    s = Settings()

    assert s.travelpayouts_token is None
    assert s.brightdata_api_key is None
    assert s.brightdata_monthly_credits == 5000


def test_quiet_hours_parses_to_times(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("QUIET_HOURS", "23:00-08:00")

    s = Settings()

    assert s.quiet_hours_start.hour == 23
    assert s.quiet_hours_end.hour == 8
