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


@pytest.fixture(scope="session", autouse=True)
async def _ensure_test_database():
    """세션당 딱 한 번, 테스트 DB가 없으면 만든다.

    autouse + session 스코프라서 세션의 첫 테스트가 시작되기 전에 반드시 실행된다.
    `test_engine`을 쓰지 않는 테스트(예: test_healthz — app.db.engine을 직접 씀)가
    먼저 수집·실행되더라도 이 픽스처가 먼저 돌아 trippick_test가 이미 존재하게 만든다.
    DB 생성 책임은 여기 하나뿐이고, `test_engine`은 이 픽스처에 의존해 중복을 만들지 않는다.
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


@pytest.fixture(scope="session")
async def test_engine(_ensure_test_database):
    """테스트 DB에 접속하는 엔진을 준다. DB 생성 자체는 _ensure_test_database 책임.

    NullPool: `asyncio_default_fixture_loop_scope = "session"`(pyproject.toml)은
    픽스처의 루프 스코프만 세션으로 만든다. 테스트 함수 자체는 기본값(function)이라
    매 테스트마다 새 이벤트 루프에서 돈다. 세션 스코프인 이 엔진이 커넥션을
    풀링하면, 테스트 A에서 맺은 asyncpg 커넥션이 A의 루프가 닫힌 뒤에도 풀에
    남았다가 테스트 B(다른 루프)가 재사용을 시도하며 "Event loop is closed" /
    "another operation is in progress"로 깨진다. NullPool은 커넥션을 풀링하지
    않고 매번 새로 맺고 반환 즉시 닫아서 이 문제를 원천 차단한다.
    """
    eng = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="session")
async def migrated_engine(test_engine):
    """테스트 DB를 downgrade base → upgrade head 로 재적용한 엔진.

    I-005: 마이그레이션 파일을 리비전 ID 변경 없이 직접 고치면, 이미 그 리비전으로
    스탬프된 DB는 `alembic upgrade head`가 no-op이라 내용이 재적용되지 않는다.
    이 상태에서 pytest가 그냥 통과하면 "조용한 거짓 초록"이 된다 — 테스트 DB가
    옛 스키마인 채로 아무도 모르게 넘어간다. 그래서 매 세션 downgrade base를
    먼저 돌려 스키마를 항상 마이그레이션 파일과 일치시킨다. 부수 효과로 downgrade
    경로도 매 실행마다 검증된다 (예: op.drop_constraint(None, ...) 같은 이름 없는
    downgrade 결함이 즉시 드러남).

    세션 스코프라 pytest 실행당 1회만 돈다. 테스트마다 도는 게 아니다.
    """
    import subprocess

    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    downgrade_result = subprocess.run(
        ["uv", "run", "alembic", "downgrade", "base"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert downgrade_result.returncode == 0, (
        f"alembic downgrade base 실패:\n{downgrade_result.stderr}"
    )

    upgrade_result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert upgrade_result.returncode == 0, f"alembic upgrade head 실패:\n{upgrade_result.stderr}"

    return test_engine
