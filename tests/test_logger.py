from __future__ import annotations

import json
import logging

from src.utils.logger import JsonFormatter, get_logger


def make_record(msg: str = "hello", level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=level,
        pathname="x.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_json_formatter_produces_valid_json():
    fmt = JsonFormatter()
    record = make_record()
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["msg"] == "hello"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test"
    assert "ts" in parsed


def test_json_formatter_includes_exception():
    fmt = JsonFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="x.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    out = fmt.format(record)
    parsed = json.loads(out)
    assert "exc" in parsed
    assert "RuntimeError" in parsed["exc"]


def test_json_formatter_with_args():
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    out = fmt.format(record)
    parsed = json.loads(out)
    assert parsed["msg"] == "hello world"


def test_get_logger_returns_named_logger():
    log = get_logger("foo.bar")
    assert log.name == "foo.bar"
    assert isinstance(log, logging.Logger)
