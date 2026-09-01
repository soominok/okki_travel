"""테스트 프로세스 부트스트랩.

app.main은 임포트 시점에 CORSMiddleware 설정을 위해 get_settings()를 호출한다.
pytest는 테스트 함수의 monkeypatch가 실행되기 전에 모듈 수집(import) 단계에서
app.main을 임포트하므로, 필수 필드(app_api_token, database_url)가 이미 os.environ에
있어야 수집이 성공한다. pytest_configure는 수집보다 먼저 실행되므로 여기서 최소값을
채운다. 개별 테스트가 monkeypatch로 값을 다시 덮어써도 문제없다.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def pytest_configure(config):
    os.environ.setdefault("APP_API_TOKEN", "x" * 32)
    os.environ.setdefault(
        "DATABASE_URL", "postgresql+asyncpg://trip:trip@localhost:5434/trippick_test"
    )


@pytest.fixture(autouse=True)
async def _dispose_app_engine():
    """각 테스트가 함수 스코프 이벤트 루프를 쓰므로(pytest-asyncio 기본값),
    app.db.engine(모듈 전역, 커넥션 풀 보유)에 이전 테스트의 루프에 묶인 커넥션이
    남아 있으면 다음 테스트에서 "Event loop is closed" 로 깨진다.
    매 테스트 뒤 풀을 비워 다음 테스트가 현재 루프에서 새 커넥션을 맺도록 한다.
    """
    yield
    from app.db import engine

    await engine.dispose()


TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://trip:trip@localhost:5434/trippick_test"
)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """테스트 DB가 없으면 만들고, 엔진을 준다."""
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = 'trippick_test'")
        )
        if not exists:
            await conn.execute(text("CREATE DATABASE trippick_test"))
    await admin.dispose()

    eng = create_async_engine(TEST_DB_URL)
    yield eng
    await eng.dispose()
