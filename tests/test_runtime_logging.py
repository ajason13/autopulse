"""Runtime logging configuration tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from autopulse import debug as debug_cli
from autopulse.debugging import REDACTED, log_event
from autopulse.logging_config import configure_logging


RAW_VIN = "1HGCM82633A004352"
VIN_HASHED = "a" * 64


@pytest.fixture(autouse=True)
def restore_autopulse_logger():
    logger = logging.getLogger("autopulse")
    root_logger = logging.getLogger()
    original_level = logger.level
    original_propagate = logger.propagate
    original_handlers = list(logger.handlers)
    original_root_level = root_logger.level
    original_root_handlers = list(root_logger.handlers)
    logger.handlers = []
    try:
        yield
    finally:
        for handler in logger.handlers:
            if handler not in original_handlers:
                handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        root_logger.handlers = original_root_handlers
        root_logger.setLevel(original_root_level)


def runtime_handlers() -> list[logging.Handler]:
    logger = logging.getLogger("autopulse")
    return [
        handler
        for handler in logger.handlers
        if getattr(handler, "_autopulse_runtime_kind", None) is not None
    ]


def test_configure_logging_adds_console_handler_without_root_mutation() -> None:
    root_logger = logging.getLogger()
    root_level = root_logger.level
    root_handlers = list(root_logger.handlers)

    logger = configure_logging(level=logging.DEBUG, console=True)

    assert logger is logging.getLogger("autopulse")
    assert logger.level == logging.DEBUG
    assert logging.getLogger().level == root_level
    assert logging.getLogger().handlers == root_handlers
    assert len(runtime_handlers()) == 1
    assert getattr(runtime_handlers()[0], "_autopulse_runtime_kind") == "console"


def test_configure_logging_is_idempotent_for_console_handler() -> None:
    configure_logging(level=logging.DEBUG, console=True)
    configure_logging(level=logging.INFO, console=True)
    configure_logging(level=logging.WARNING, console=True)

    handlers = runtime_handlers()
    assert len(handlers) == 1
    assert handlers[0].level == logging.WARNING


def test_configure_logging_reuses_debug_cli_console_handler() -> None:
    debug_cli._configure_logging(True)

    configure_logging(level=logging.DEBUG, console=True)

    handlers = [
        handler
        for handler in logging.getLogger("autopulse").handlers
        if getattr(handler, "_autopulse_debug_cli", False)
    ]
    assert len(handlers) == 1
    assert handlers[0].level == logging.DEBUG
    assert len(runtime_handlers()) == 0


def test_configure_logging_file_handler_writes_sanitized_json_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    logger = configure_logging(
        level=logging.DEBUG,
        console=False,
        file_path=log_path,
    )

    log_event(
        logger,
        logging.DEBUG,
        "runtime_test",
        raw_vin=RAW_VIN,
        vin_hashed=VIN_HASHED,
        payload_bytes="2E F4 B2 00",
    )
    for handler in logger.handlers:
        handler.flush()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event"] == "runtime_test"
    assert payload["raw_vin"] == REDACTED
    assert payload["vin_hashed"] == VIN_HASHED
    assert payload["payload_bytes"] == REDACTED
    assert RAW_VIN not in lines[0]
    assert "2E F4 B2 00" not in lines[0]


def test_configure_logging_file_handler_is_idempotent_for_same_path(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"

    configure_logging(level=logging.DEBUG, console=False, file_path=log_path)
    configure_logging(level=logging.INFO, console=False, file_path=log_path)

    handlers = runtime_handlers()
    assert len(handlers) == 1
    assert handlers[0].level == logging.INFO


def test_configure_logging_requires_existing_file_parent(tmp_path: Path) -> None:
    log_path = tmp_path / "missing" / "run.log"

    with pytest.raises(FileNotFoundError):
        configure_logging(level=logging.DEBUG, console=False, file_path=log_path)

    assert not log_path.exists()


def test_configure_logging_can_create_parents_when_explicit(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "run.log"

    configure_logging(
        level=logging.DEBUG,
        console=False,
        file_path=log_path,
        create_parents=True,
    )

    assert log_path.parent.exists()
    assert log_path.exists()


def test_configure_logging_has_no_default_file_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    configure_logging(level=logging.DEBUG, console=True)

    assert not (tmp_path / "logs" / "autopulse.log").exists()


def test_file_logging_rejects_non_finite_before_write(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    logger = configure_logging(
        level=logging.DEBUG,
        console=False,
        file_path=log_path,
    )

    with pytest.raises(ValueError, match="non-finite"):
        log_event(logger, logging.DEBUG, "runtime_test", score=float("nan"))
    for handler in logger.handlers:
        handler.flush()

    assert log_path.read_text(encoding="utf-8") == ""


def test_file_logging_redacts_malformed_vin_hashed(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    logger = configure_logging(
        level=logging.DEBUG,
        console=False,
        file_path=log_path,
    )

    log_event(logger, logging.DEBUG, "runtime_test", vin_hashed="not-a-hash")
    for handler in logger.handlers:
        handler.flush()

    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["vin_hashed"] == REDACTED


def test_disabled_level_does_not_write_file_log(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    logger = configure_logging(
        level=logging.WARNING,
        console=False,
        file_path=log_path,
    )

    log_event(logger, logging.DEBUG, "runtime_test", secret="sk-abc123")
    for handler in logger.handlers:
        handler.flush()

    assert log_path.read_text(encoding="utf-8") == ""
