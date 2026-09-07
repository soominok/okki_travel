"""structlog JSON 로깅. 클라우드 이전 시 로그 수집기가 그대로 파싱한다.

stdlib logging(APScheduler·uvicorn·SQLAlchemy·httpx가 쓴다)도 structlog와 같은
JSON 파이프라인을 거치도록 root logger를 structlog.stdlib.ProcessorFormatter로
감싼다. 이걸 안 하면 이 라이브러리들의 로그가 평문으로 stdout에 샌다.
"""

import logging
import sys

import structlog

_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def setup_logging(level: str = "INFO") -> None:
    level_name = level.upper()
    level_value = logging.getLevelNamesMapping()[level_name]

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level_value),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_value)

    # uvicorn은 자체 dictConfig로 이 로거들에 자기 핸들러(평문)를 달고
    # propagate=False로 root와 끊어놓는다. 그 dictConfig는 여기(FastAPI startup
    # 이벤트에서 호출되는 setup_logging())보다 먼저 실행되므로, 핸들러를 비우고
    # propagate를 되살려 root의 JSON 핸들러로 흘러가게 한다.
    # 주의: uvicorn --reload 의 부모 reloader 프로세스가 찍는 줄
    # ("Will watch for changes...")은 앱 코드를 아예 임포트하지 않아 이 함수가
    # 호출될 일이 없다 — 개발 전용 경로라 여기서 잡지 않는다.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
