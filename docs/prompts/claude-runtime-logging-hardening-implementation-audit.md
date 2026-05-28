# Claude Prompt: Runtime Logging Hardening Implementation Audit

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Review branch `logging-hardening` for merge readiness. This is an implementation audit after your adversarial QA plan for Runtime Logging Hardening.

## Review Goals

Evaluate whether Codex correctly implemented the runtime logging hardening scope without weakening AutoPulse privacy, read-only OBD-II/UDS security, debug CLI behavior, or test isolation.

Focus on:

- `log_event()` non-finite number handling.
- `vin_hashed` shape validation on runtime logging paths.
- file logging opt-in behavior and explicit path safety.
- no root logger mutation.
- handler idempotency and interaction with the existing debug CLI handler.
- redaction of raw VINs, payload bytes, secrets, tokens, seed/key material, raw exception messages, and rejected frame values.
- whether the new policy doc accurately captures the implemented contract.

Return:

1. Verdict: PASS, CONDITIONAL PASS, or FAIL.
2. Blockers, if any, with file/line references.
3. Non-blocking follow-ups, if any.
4. Missing tests, if any.
5. Explicit merge recommendation.

## Branch and Verification

Branch: `logging-hardening`

Verification already run by Codex:

- `python3 -m pytest tests/test_runtime_logging.py tests/test_debugging.py tests/test_debug_cli_replay.py -q` -> `40 passed`
- `python3 -m pytest tests/test_debugging.py tests/test_runtime_logging.py tests/test_debug_cli_replay.py tests/test_us006_ev_replay_harness.py tests/test_us006_ev_adapter_security.py tests/test_us005_alert_exporter.py -q` -> `153 passed`
- `python3 -m pytest -q` -> `571 passed`

## Relevant File Contents

### `src/autopulse/debugging.py`

```python
"""Safe debugging helpers for AutoPulse telemetry workflows."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Mapping


RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
VIN_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = frozenset(
    {
        "raw_vin",
        "payload_bytes",
        "seed",
        "key",
        "token",
        "secret",
    }
)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger without configuring global handlers."""
    return logging.getLogger(name)


def sanitize_debug_value(value: Any, *, validate_vin_shape: bool = False) -> Any:
    """Return a debug-safe copy of a value.

    Raw VIN-like strings and sensitive key names are redacted. ``vin_hashed`` is
    preserved when it is a valid public vehicle identifier required by AutoPulse
    audit trails. Runtime logging callers can require SHA-256 shape validation
    so malformed ``vin_hashed`` values are redacted instead of preserved.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = _sanitize_vin_hash(
                    item,
                    validate_vin_shape=validate_vin_shape,
                )
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(
                item,
                validate_vin_shape=validate_vin_shape,
            )
        return sanitized

    if isinstance(value, list):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, str):
        return RAW_VIN_PATTERN.sub(REDACTED, value)

    return value


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured, sanitized debug event."""
    if not logger.isEnabledFor(level):
        return

    payload = {
        "event": event,
        **sanitize_debug_value(fields, validate_vin_shape=True),
    }
    _validate_finite_numbers(payload)
    logger.log(level, json.dumps(payload, allow_nan=False, sort_keys=True))


def _sanitize_vin_hash(value: Any, *, validate_vin_shape: bool) -> Any:
    sanitized = sanitize_debug_value(value, validate_vin_shape=validate_vin_shape)
    if not validate_vin_shape:
        return sanitized
    if isinstance(sanitized, str) and VIN_HASH_PATTERN.fullmatch(sanitized):
        return sanitized
    return REDACTED


def _validate_finite_numbers(value: Any) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("log_event fields must not contain non-finite numbers.")
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _validate_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_finite_numbers(item)


__all__ = [
    "RAW_VIN_PATTERN",
    "REDACTED",
    "VIN_HASH_PATTERN",
    "get_logger",
    "log_event",
    "sanitize_debug_value",
]
```

### `src/autopulse/logging_config.py`

```python
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
```

### `tests/test_runtime_logging.py`

```python
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
```

### Relevant additions in `tests/test_debugging.py`

```python
def test_sanitize_debug_value_can_redact_malformed_vin_hashed() -> None:
    sanitized = sanitize_debug_value(
        {"vin_hashed": "not-a-sha256-hash"},
        validate_vin_shape=True,
    )

    assert sanitized["vin_hashed"] == REDACTED


def test_log_event_redacts_malformed_vin_hashed(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging.vin_hash")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.vin_hash"):
        log_event(
            logger,
            logging.DEBUG,
            "debug_test",
            vin_hashed="not-a-sha256-hash",
        )

    payload = json.loads(caplog.records[0].message)
    assert payload["vin_hashed"] == REDACTED


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_log_event_rejects_non_finite_numbers(
    value: float,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.debugging.non_finite")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.non_finite"):
        with pytest.raises(ValueError, match="non-finite"):
            log_event(logger, logging.DEBUG, "debug_test", score=value)

    assert len(caplog.records) == 0
```

### `docs/runtime-logging-policy.md`

```markdown
# AutoPulse Runtime Logging Policy

AutoPulse runtime logging exists to support replay debugging, future live-capture triage, and auditability without weakening the read-only diagnostic boundary.

This policy applies to `autopulse.debugging.log_event()` and `autopulse.logging_config.configure_logging()`.

## Logging Model

Runtime events that carry vehicle, diagnostic, replay, guard, or alert context must be emitted as structured JSON through `log_event()`.

Plain text `INFO` messages are allowed only for startup or configuration state that does not include vehicle data, frame data, adapter payloads, exception messages, guard context, or alert payloads.

## Logger Scope

All runtime handlers are attached to the `autopulse` logger or its children. AutoPulse must not configure the root logger.

`configure_logging()`:

- sets the `autopulse` logger level;
- disables propagation from `autopulse` to root;
- adds a console handler only when requested;
- adds a file handler only when an explicit path is provided;
- reuses existing AutoPulse runtime/debug CLI handlers instead of duplicating them.

Console logging writes to `stderr`. CLI JSON command output remains on `stdout`.

## Event Payload Rules

Allowed structured fields include:

- `event`
- `row_index`
- `error_type`
- `event_code`
- `service_id`
- validated `vin_hashed` only when traceability requires it

Forbidden fields or values include:

- raw VINs;
- raw diagnostic payload bytes;
- seed/key/security access material;
- tokens or secrets;
- raw exception messages from validation or adapter paths;
- tracebacks or `exc_info` content;
- rejected frame content;
- non-finite numbers such as `NaN`, `Infinity`, and `-Infinity`.

`log_event()` sanitizes fields before serialization, validates `vin_hashed` shape before preserving it, rejects non-finite numbers, and serializes with `allow_nan=False`.

## File Logging

File logging is opt-in.

Callers must pass an explicit `file_path`; AutoPulse does not create `logs/autopulse.log` or any other default file. Parent directories must already exist unless the caller passes `create_parents=True`.

File handlers use UTF-8 and append mode. Rotation is intentionally deferred. Any future rotation support must define max size, backup count, retention behavior, and whether backups are compressed before implementation.

## Event Taxonomy

Current and planned event families:

- `validation_*`: schema or physics validation outcomes; use `row_index` and `error_type`, not raw exception text.
- `replay_*`: replay lifecycle and row-level accepted/rejected counts; avoid frame payloads.
- `guard_*` / `security_*`: read-only guard events; use safe event codes and service IDs only.
- `alert_*`: alert preview or export events; include `vin_hashed` only after shape validation.
- `adapter_*`: connect/disconnect/lifecycle events; do not include payload bytes or raw adapter frames.
- `live_capture_*`: reserved for a future read-only smoke harness after separate QA planning.

## Live Vehicle Boundary

This logging layer does not authorize live polling, road testing, write-capable services, or new OBD/UDS access. Real-vehicle work remains deferred until a separate stationary read-only smoke harness, PID allowlist, runtime stop behavior, and operator checklist are reviewed.
```

## Context

`CONTEXT.md` now records Runtime Logging Hardening as in development, notes that Claude's planning blockers were resolved, and identifies `docs/runtime-logging-policy.md` as the durable policy document.
