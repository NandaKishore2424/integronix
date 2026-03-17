"""
logger.py — Structured JSON logging for Integronix.

Every log line is machine-readable JSON with:
  timestamp, level, module, session_id, node_name, event, ...extra fields

Usage:
    from logger import get_logger
    log = get_logger(__name__)
    log.info("icd_resolved", session_id=sid, code="E11.22", method="direct")
"""
import logging
import json
import sys
import time
from typing import Any


# Define the logger at the top of the file
log = logging.getLogger("backend_logger")


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }

        # Merge any extra fields passed via log.info("event", key=val, ...)
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class StructuredLogger(logging.LoggerAdapter):
    """Logger that accepts ANY keyword args as structured fields."""

    # Standard logging kwargs that must NOT be moved to extra_fields
    _LOGGING_RESERVED = {"exc_info", "stack_info", "stacklevel", "extra"}

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra_fields = kwargs.pop("extra_fields", {})

        # Move ALL non-reserved kwargs into extra_fields so they become
        # structured JSON fields instead of being passed to logging._log()
        for key in list(kwargs.keys()):
            if key not in self._LOGGING_RESERVED:
                extra_fields[key] = kwargs.pop(key)

        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        return msg, kwargs



def get_logger(name: str) -> StructuredLogger:
    """Returns a structured logger for the given module name."""
    base_logger = logging.getLogger(name)

    if not base_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        base_logger.addHandler(handler)
        base_logger.setLevel(logging.INFO)
        base_logger.propagate = False

    return StructuredLogger(base_logger, {})


class Timer:
    """Context manager to measure and log latency."""

    def __init__(self, name: str = "Timer"):
        self.name = name
        self._start: float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self):
        self._start = time.perf_counter()
        log.info("%s started.", self.name)
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)
        log.info("%s completed in %d ms.", self.name, self.elapsed_ms)
