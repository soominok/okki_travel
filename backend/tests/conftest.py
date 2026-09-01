"""테스트 프로세스 부트스트랩.

app.main은 임포트 시점에 CORSMiddleware 설정을 위해 get_settings()를 호출한다.
pytest는 테스트 함수의 monkeypatch가 실행되기 전에 모듈 수집(import) 단계에서
app.main을 임포트하므로, 필수 필드(app_api_token, database_url)가 이미 os.environ에
있어야 수집이 성공한다. pytest_configure는 수집보다 먼저 실행되므로 여기서 최소값을
채운다. 개별 테스트가 monkeypatch로 값을 다시 덮어써도 문제없다.

테스트는 Postgres에서 돈다. SQLite로 대체하지 않는다 (CLAUDE.md 1번).
docker compose 의 db 서비스에 trippick_test 데이터베이스를 별도로 만들어 쓴다.
호스트 포트는 5434 (5432·5433 은 다른 프로젝트가 점유).
"""

import os
from urllib.parse import urlsplit

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# 테스트 DB URL의 단일 정의처. pytest_configure의 기본값과 test_engine이 각자
# 리터럴을 따로 들고 있으면 한쪽만 바뀔 때 app.db.engine과 test_engine이 서로
# 다른 DB를 보게 된다. 이 상수 하나만 바꾸면 양쪽에 반영된다.
_DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://trip:trip@localhost:5434/trippick_test"


def pytest_configure(config):
    os.environ.setdefault("APP_API_TOKEN", "x" * 32)

    test_db_url = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DATABASE_URL)
    db_name = urlsplit(test_db_url).path.lstrip("/")
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL이 테스트용 DB를 가리키지 않는다 (DB 이름 {db_name!r}이 "
            "'_test'로 끝나지 않음). pytest가 개발 DB에 붙어 데이터를 건드리는 사고를 "
            "막기 위한 가드다. 테스트 DB 이름은 반드시 '_test'로 끝나야 한다."
        )
    # setdefault가 아니라 무조건 대입한다. 개발자가 같은 셸에서
    # `DATABASE_URL=...(개발 DB) uv run alembic upgrade head`를 돌린 뒤 이어서
    # pytest를 돌리면, DATABASE_URL이 이미 os.environ에 있으므로 setdefault로는
    # 개발 DB를 그대로 물려받는다. pytest 프로세스 안에서는 항상 테스트 DB를
    # 보도록 강제한다.
    os.environ["DATABASE_URL"] = test_db_url


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


TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DATABASE_URL)
_TEST_DB_NAME = urlsplit(TEST_DB_URL).path.lstrip("/")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """테스트 DB가 없으면 만들고, 엔진을 준다.

    NullPool: `asyncio_default_fixture_loop_scope = "session"`(pyproject.toml)은
    픽스처의 루프 스코프만 세션으로 만든다. 테스트 함수 자체는 기본값(function)이라
    매 테스트마다 새 이벤트 루프에서 돈다. 세션 스코프인 이 엔진이 커넥션을
    풀링하면, 테스트 A에서 맺은 asyncpg 커넥션이 A의 루프가 닫힌 뒤에도 풀에
    남았다가 테스트 B(다른 루프)가 재사용을 시도하며 "Event loop is closed" /
    "another operation is in progress"로 깨진다. NullPool은 커넥션을 풀링하지
    않고 매번 새로 맺고 반환 즉시 닫아서 이 문제를 원천 차단한다.
    """
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _TEST_DB_NAME}
        )
        if not exists:
            # DB 이름은 바인드 파라미터로 넘길 수 없다(DDL 식별자). _TEST_DB_NAME은
            # 위 가드(pytest_configure)를 통과한 "_test"로 끝나는 로컬 테스트 DB
            # 이름이라 외부 입력이 아니다.
            await conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    await admin.dispose()

    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield eng
    await eng.dispose()
