"""Runtime logging configuration for AutoPulse observability."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


AUTOPULSE_LOGGER_NAME = "autopulse"
_CONSOLE_HANDLER_KIND = "console"
_FILE_HANDLER_KIND = "file"


class JsonLineFormatter(logging.Formatter):
    """Pass through structured event messages as one line per record."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def configure_logging(
    *,
    level: int = logging.INFO,
    console: bool = True,
    file_path: Path | str | None = None,
    create_parents: bool = False,
) -> logging.Logger:
    """Configure AutoPulse runtime logging without mutating the root logger.

    File logging is opt-in and requires an explicit path. Parent directories are
    only created when the caller explicitly requests it.
    """
    logger = logging.getLogger(AUTOPULSE_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if console:
        _ensure_console_handler(logger, level)

    if file_path is not None:
        _ensure_file_handler(
            logger,
            Path(file_path),
            level,
            create_parents=create_parents,
        )

    return logger


def _ensure_console_handler(logger: logging.Logger, level: int) -> None:
    for handler in logger.handlers:
        if getattr(handler, "_autopulse_runtime_kind", None) == _CONSOLE_HANDLER_KIND:
            handler.setLevel(level)
            handler.setFormatter(JsonLineFormatter())
            return
        if getattr(handler, "_autopulse_debug_cli", False):
            handler.setLevel(level)
            handler.setFormatter(JsonLineFormatter())
            return

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(JsonLineFormatter())
    handler._autopulse_runtime_kind = _CONSOLE_HANDLER_KIND  # type: ignore[attr-defined]
    logger.addHandler(handler)


def _ensure_file_handler(
    logger: logging.Logger,
    path: Path,
    level: int,
    *,
    create_parents: bool,
) -> None:
    resolved_path = path.expanduser()
    if not resolved_path.parent.exists():
        if not create_parents:
            raise FileNotFoundError(
                "log file parent directory does not exist; pass create_parents=True"
            )
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

    for handler in logger.handlers:
        if (
            getattr(handler, "_autopulse_runtime_kind", None) == _FILE_HANDLER_KIND
            and getattr(handler, "_autopulse_runtime_path", None) == str(resolved_path)
        ):
            handler.setLevel(level)
            return

    handler = logging.FileHandler(resolved_path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(JsonLineFormatter())
    handler._autopulse_runtime_kind = _FILE_HANDLER_KIND  # type: ignore[attr-defined]
    handler._autopulse_runtime_path = str(resolved_path)  # type: ignore[attr-defined]
    logger.addHandler(handler)


__all__ = ["AUTOPULSE_LOGGER_NAME", "JsonLineFormatter", "configure_logging"]
