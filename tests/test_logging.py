"""Unit tests for meta_agent.logging module and request context tracking."""

import logging

from meta_agent.logging import (
    generate_request_id,
    get_current_request_id,
    request_context,
    set_current_request_id,
    setup_logging,
)


def test_generate_request_id() -> None:
    """Test generating a unique UUID string."""
    id1 = generate_request_id()
    id2 = generate_request_id()
    assert id1 != id2
    assert len(id1) > 0


def test_set_and_get_current_request_id() -> None:
    """Test manual set and get of request id."""
    set_current_request_id(None)
    assert get_current_request_id() is None
    set_current_request_id("custom-req-id")
    assert get_current_request_id() == "custom-req-id"
    set_current_request_id(None)


def test_request_context_manager() -> None:
    """Test request_context sets and restores request ID."""
    assert get_current_request_id() is None
    with request_context("my-ctx-id") as req_id:
        assert req_id == "my-ctx-id"
        assert get_current_request_id() == "my-ctx-id"
    assert get_current_request_id() is None


def test_request_context_generates_id_if_none() -> None:
    """Test request_context generates new UUID if none active."""
    with request_context() as req_id:
        assert req_id is not None
        assert get_current_request_id() == req_id
    assert get_current_request_id() is None


def test_request_id_factory() -> None:
    """Test _request_id_log_record_factory attaches request_id to LogRecord."""
    setup_logging()
    with request_context("test-uuid-123"):
        logger = logging.getLogger("test_logger")
        record = logger.makeRecord("test_logger", logging.INFO, "test.py", 10, "msg", (), None)
        assert getattr(record, "request_id", None) == "test-uuid-123"

    record = logger.makeRecord("test_logger", logging.INFO, "test.py", 10, "msg", (), None)
    assert getattr(record, "request_id", None) == "-"


def test_setup_logging() -> None:
    """Test setup_logging configures root logger without errors."""
    setup_logging()
    root = logging.getLogger()
    assert len(root.handlers) > 0
