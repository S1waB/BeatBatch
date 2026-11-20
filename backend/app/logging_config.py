"""
Structured logging configuration for BeatBatch backend.
Formats log records with ISO-8601 timestamps, log level, component name,
message, and any extra structured metadata.
"""

import json
import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Formats log records as structured text with JSON metadata if present."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        base_log = f"{timestamp} | {record.levelname:<8} | {record.name} | {record.getMessage()}"

        # Capture extra fields if attached
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord.__dict__
            and not k.startswith("_")
            and k not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName"
            )
        }

        if extra_fields:
            try:
                base_log += f" | {json.dumps(extra_fields, default=str)}"
            except Exception:
                pass

        if record.exc_info:
            base_log += "\n" + self.formatException(record.exc_info)

        return base_log


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that handles Windows charmap/cp1252 encoding and closed test streams."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                enc = getattr(stream, "encoding", None) or "ascii"
                safe_msg = msg.encode(enc, errors="backslashreplace").decode(enc)
                stream.write(safe_msg + self.terminator)
            self.flush()
        except (ValueError, OSError):
            pass


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Initialize structured logging on the root logger."""
    handler = SafeStreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Replace existing handlers to prevent duplicates
    root.handlers.clear()
    root.addHandler(handler)
