import pytest
from pydantic import ValidationError

from app.config import Settings


def test_missing_source_keys_are_none_not_error(monkeypatch):
    """키가 없어도 앱은 떠야 한다. 해당 어댑터만 나중에 disabled 처리된다."""
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.delenv("TRAVELPAYOUTS_TOKEN", raising=False)
    monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)

    s = Settings(_env_file=None)

    assert s.travelpayouts_token is None
    assert s.brightdata_api_key is None
    assert s.brightdata_monthly_credits == 5000


def test_empty_string_env_is_none_not_empty_string(monkeypatch):
    """.env.example이 배포하는 기본 경로: 변수는 있지만 값이 빈 문자열.
    실제로 cp .env.example .env만 한 사람의 Settings에는 이 경로가 기본값이다."""
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("BRIGHTDATA_API_KEY", "")
    monkeypatch.setenv("DATA_GO_KR_KEY", "")
    monkeypatch.setenv("EXIM_API_KEY", "")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "")

    s = Settings(_env_file=None)

    assert s.travelpayouts_token is None
    assert s.brightdata_api_key is None
    assert s.data_go_kr_key is None
    assert s.exim_api_key is None
    assert s.slack_webhook_url is None


def test_quiet_hours_parses_to_times(monkeypatch):
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("QUIET_HOURS", "23:00-08:00")

    s = Settings(_env_file=None)

    assert s.quiet_hours_start.hour == 23
    assert s.quiet_hours_end.hour == 8


@pytest.mark.parametrize(
    "bad_value",
    [
        "23:00~08:00",  # 구분자 오타 (- 가 아니라 ~)
        "23:00-08:00-10:00",  # 시각이 3개
        "23-08",  # 콜론 없는 축약형 (조용히 23:00으로 파싱되면 안 됨)
    ],
)
def test_quiet_hours_rejects_malformed_values_at_startup(monkeypatch, bad_value):
    """형식 오타는 알림 디스패처 한복판이 아니라 Settings() 생성 시점에 바로 터져야 한다."""
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("QUIET_HOURS", bad_value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_quiet_hours_rejects_empty_value_via_direct_kwarg(monkeypatch):
    """빈 문자열 env는 env_ignore_empty=True 때문에 '미설정'으로 취급되어 기본값으로
    폴백한다(정상 동작, 픽스 1). 검증기 자체가 빈 값을 거부하는지는 env를 우회해
    직접 kwarg로 넘겨 확인한다."""
    monkeypatch.setenv("APP_API_TOKEN", "x" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, quiet_hours="")


def test_app_api_token_is_secret_and_not_leaked_in_repr(monkeypatch):
    """토큰이 ValidationError나 repr로 평문 노출되면 안 된다."""
    token = "x" * 32
    monkeypatch.setenv("APP_API_TOKEN", token)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")

    s = Settings(_env_file=None)

    assert token not in repr(s.app_api_token)
    assert token not in str(s.app_api_token)
    assert s.app_api_token.get_secret_value() == token
