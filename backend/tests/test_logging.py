"""setup_logging()이 stdlib 로거까지 JSON으로 감싸는지 검증한다.

APScheduler·uvicorn·SQLAlchemy·httpx는 전부 stdlib logging을 쓴다. structlog만
설정하고 stdlib 핸들러를 감싸지 않으면 이 로거들의 출력이 평문으로 새어나간다
(계획 1 whole-branch 리뷰에서 발견, worker stdout 실측으로 확인됨).
"""

import json
import logging

from app.logging import setup_logging


def test_stdlib_logger_output_is_valid_json(capsys):
    """APScheduler 같은 stdlib 로거의 출력도 JSON 한 줄이어야 한다."""
    setup_logging("INFO")

    logging.getLogger("apscheduler").info("Running job")

    out = capsys.readouterr().out.strip()
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 1, f"stdlib 로그가 한 줄의 JSON이어야 한다: {out!r}"

    payload = json.loads(lines[0])
    assert payload["event"] == "Running job"
    assert payload["level"] == "info"
    assert payload["logger"] == "apscheduler"


def test_stdlib_logger_output_is_not_duplicated(capsys):
    """핸들러를 여러 번 붙이면 같은 로그가 두 줄로 찍힌다. setup_logging을 두 번
    불러도(예: main과 worker가 각자 임포트 시점에 호출) 중복 출력이 없어야 한다."""
    setup_logging("INFO")
    setup_logging("INFO")

    logging.getLogger("apscheduler").info("Running job")

    out = capsys.readouterr().out.strip()
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 1, f"핸들러 중복으로 로그가 두 줄 찍혔다: {out!r}"


def test_lowercase_log_level_does_not_crash():
    """LOG_LEVEL=info(소문자)로 설정해도 기동이 죽으면 안 된다."""
    setup_logging("info")


def test_structlog_logger_output_is_still_valid_json(capsys):
    """structlog 쪽 로거도 여전히 정상 동작해야 한다 (회귀 방지)."""
    import structlog

    setup_logging("INFO")

    structlog.get_logger("worker").info("worker.heartbeat", tick=1)

    out = capsys.readouterr().out.strip()
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["event"] == "worker.heartbeat"
    assert payload["tick"] == 1
