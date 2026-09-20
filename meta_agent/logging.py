"""Logging utilities and context-bound request ID management."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import logging
from typing import Any
import uuid

_request_id_var: ContextVar[str | None] = ContextVar("meta_agent_request_id", default=None)


def get_current_request_id() -> str | None:
    """Return the active request ID in the current execution context, if any."""
    return _request_id_var.get()


def set_current_request_id(request_id: str | None) -> None:
    """Set or clear the request ID in the current execution context."""
    _request_id_var.set(request_id)


def generate_request_id() -> str:
    """Generate a new unique UUID string for a request."""
    return str(uuid.uuid4())


@contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Context manager to bind a request ID to the current execution context."""
    req_id = request_id or get_current_request_id() or generate_request_id()
    token = _request_id_var.set(req_id)
    try:
        yield req_id
    finally:
        _request_id_var.reset(token)


_old_factory = logging.getLogRecordFactory()


def _request_id_log_record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
    record = _old_factory(*args, **kwargs)
    req_id = get_current_request_id()
    record.request_id = req_id if req_id else "-"
    return record


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging with timestamp, level, request_id, and message."""
    logging.setLogRecordFactory(_request_id_log_record_factory)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    fmt = "%(asctime)s [%(levelname)s] [%(request_id)s] %(filename)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(fmt)

    # Configure existing handlers or add a standard StreamHandler
    if not root_logger.handlers:
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        root_logger.addHandler(sh)
    else:
        for h in root_logger.handlers:
            h.setFormatter(formatter)
