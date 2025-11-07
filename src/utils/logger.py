"""Structured logging configuration."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


def setup_logging(log_level: str = None) -> logging.Logger:
    """
    Set up structured logging for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  Defaults to LOG_LEVEL env var or INFO

    Returns:
        Configured logger instance
    """
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    # Create logger
    logger = logging.getLogger("discord_host_scheduler")
    logger.setLevel(log_level.upper())

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)

    # File handler with JSON formatting
    file_handler = logging.FileHandler("bot.log")
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def log_with_context(
    logger: logging.Logger, level: str, message: str, context: dict[str, Any] = None
) -> None:
    """
    Log message with additional context.

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        context: Additional context dictionary
    """
    if context:
        # Create log record with extra data
        log_method = getattr(logger, level.lower())
        log_method(message, extra={"extra_data": context})
    else:
        getattr(logger, level.lower())(message)


def sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize log data to remove secrets and sensitive information.

    Args:
        data: Data dictionary to sanitize

    Returns:
        Sanitized data dictionary
    """
    sensitive_keys = {
        "token",
        "password",
        "secret",
        "api_key",
        "credentials",
        "auth",
        "authorization",
    }

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value

    return sanitized
