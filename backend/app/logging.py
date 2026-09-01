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
