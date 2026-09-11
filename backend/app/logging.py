import logging
import re

import structlog

_SENSITIVE = frozenset(
    {
        "authorization",
        "body",
        "cookie",
        "csrf",
        "email",
        "name",
        "output",
        "password",
        "phone",
        "preview",
        "prompt",
        "refresh_token",
        "resume_token",
        "token",
    }
)
_QUERY = re.compile(r"[?#][^\s]*")


class _StripQueryFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _QUERY.sub("", arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


def _drop_sensitive(_logger: object, _method: str, event_dict: dict) -> dict:
    for key in list(event_dict):
        lowered = key.lower()
        if lowered in _SENSITIVE or "token" in lowered or "password" in lowered:
            event_dict.pop(key, None)
            continue
        value = event_dict[key]
        if isinstance(value, str) and ("?" in value or "#" in value) and "://" in value:
            event_dict[key] = value.split("#", 1)[0].split("?", 1)[0]
    return event_dict


def configure_logging() -> None:
    logging.getLogger("uvicorn.access").addFilter(_StripQueryFilter())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _drop_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
