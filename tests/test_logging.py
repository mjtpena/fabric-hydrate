"""Tests for logging module."""

import json
import logging
from pathlib import Path

from fabric_hydrate.logging import (
    JsonFormatter,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_default_setup(self) -> None:
        """Test default logging setup."""
        logger = setup_logging()

        assert logger.name == "fabric_hydrate"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    def test_debug_level(self) -> None:
        """Test debug level setup with string parameter."""
        logger = setup_logging(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_warning_level(self) -> None:
        """Test warning level setup."""
        logger = setup_logging(level="WARNING")

        assert logger.level == logging.WARNING

    def test_error_level(self) -> None:
        """Test error level setup."""
        logger = setup_logging(level="ERROR")

        assert logger.level == logging.ERROR

    def test_critical_level(self) -> None:
        """Test critical level setup."""
        logger = setup_logging(level="CRITICAL")

        assert logger.level == logging.CRITICAL

    def test_json_format(self) -> None:
        """Test JSON format setup."""
        logger = setup_logging(json_format=True)

        # Check that at least one handler has JsonFormatter
        has_json_formatter = any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers)
        assert has_json_formatter

    def test_log_file(self, tmp_path: Path) -> None:
        """Test logging to file."""
        log_file = tmp_path / "test.log"
        logger = setup_logging(log_file=str(log_file))

        # Log a message
        logger.info("Test message")

        # Force flush
        for handler in logger.handlers:
            handler.flush()

        # Check file exists and contains the message
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_handlers_cleared_on_setup(self) -> None:
        """Test that previous handlers are cleared."""
        logger1 = setup_logging()
        initial_count = len(logger1.handlers)

        # Setup again
        logger2 = setup_logging()

        # Should not have accumulated handlers
        assert len(logger2.handlers) == initial_count


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_basic_format(self) -> None:
        """Test basic JSON formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_format_includes_module_info(self) -> None:
        """Test JSON formatting includes module information."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "module" in data
        assert "function" in data
        assert "line" in data

    def test_format_with_exception(self) -> None:
        """Test JSON formatting with exception info."""
        formatter = JsonFormatter()

        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_format_with_extra_attribute(self) -> None:
        """Test JSON formatting includes extra attribute."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"custom_key": "custom_value"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["extra"] == {"custom_key": "custom_value"}

    def test_format_all_log_levels(self) -> None:
        """Test JSON formatting for all log levels."""
        formatter = JsonFormatter()

        for level in [
            logging.DEBUG,
            logging.INFO,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        ]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=10,
                msg="test message",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert data["level"] == logging.getLevelName(level)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_default_logger(self) -> None:
        """Test getting default logger."""
        logger = get_logger()

        assert logger.name == "fabric_hydrate"

    def test_get_named_logger(self) -> None:
        """Test getting named logger."""
        logger = get_logger("mymodule")

        assert logger.name == "fabric_hydrate.mymodule"

    def test_logger_hierarchy(self) -> None:
        """Test logger follows hierarchy."""
        parent = get_logger()
        child = get_logger("child")

        assert child.parent == parent or child.name.startswith(parent.name + ".")

    def test_get_multiple_named_loggers(self) -> None:
        """Test getting multiple named loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "fabric_hydrate.module1"
        assert logger2.name == "fabric_hydrate.module2"
        assert logger1 is not logger2
