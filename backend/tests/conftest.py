"""테스트 프로세스 부트스트랩.

app.main은 임포트 시점에 CORSMiddleware 설정을 위해 get_settings()를 호출한다.
pytest는 테스트 함수의 monkeypatch가 실행되기 전에 모듈 수집(import) 단계에서
app.main을 임포트하므로, 필수 필드(app_api_token, database_url)가 이미 os.environ에
있어야 수집이 성공한다. pytest_configure는 수집보다 먼저 실행되므로 여기서 최소값을
채운다. 개별 테스트가 monkeypatch로 값을 다시 덮어써도 문제없다.
"""

import os


def pytest_configure(config):
    os.environ.setdefault("APP_API_TOKEN", "x" * 32)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
