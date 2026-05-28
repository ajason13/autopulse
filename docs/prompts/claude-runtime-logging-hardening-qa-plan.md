# Claude Adversarial Planning Prompt: Runtime Logging Hardening

You are Claude Sonnet 4.6 acting as the AutoPulse Lead Auditor.

## Stage

Pre-implementation adversarial QA planning for branch `logging-hardening`.

Gemini/Antigravity is temporarily unavailable, so Codex is acting as interim project/product manager for task framing. This is not a request to approve implementation code yet. Produce a QA plan and identify blockers before Codex starts the runtime logging hardening implementation.

## Project Context

AutoPulse is an educational, read-only OBD-II anomaly detection framework. Its mission is to detect statistical drift in read-only telemetry before DTCs appear.

Completed foundations:

- US-001 through US-006 are implemented and Claude-reviewed.
- The first debugging foundation added `src/autopulse/debugging.py` with:
  - `sanitize_debug_value()`
  - `log_event()`
  - `get_logger()`
- Follow-up hardening added precise VIN-key redaction, scoped verbose logging, and adversarial debug-output tests.
- Future Debugging Ergonomics merged via PR #31 and added:
  - robust `replay-ev` and `replay-ice` CLI summaries
  - `preview-alerts`
  - `inspect-guards`
  - shared `.vscode/launch.json`
  - additional privacy/security regression tests

Current decision:

- We will **not** start real-vehicle polling yet because there is no near-term vehicle access and the runtime boundary still needs hardening.
- The next task is **Runtime Logging Hardening**.
- The later task is **Real Vehicle Read-Only Smoke Harness**, deferred until logging hardening, source-level adapter boundaries, safe PID allowlist, and operator safety checklist exist.

## Non-Negotiable Security and Privacy Rules

- AutoPulse remains read-only.
- No ECU writes, clears, controls, routines, security access, diagnostic session escalation, active probing, or arbitrary adapter commands.
- Debug/runtime logs must preserve `vin_hashed` only.
- Logs must never include raw VINs, raw diagnostic payload bytes, seed-key material, tokens, secrets, private workspace links, rejected frame content, or raw exception messages that may embed rejected values.
- `guard_events` and security logging must use safe event codes and service IDs only.
- JSON log output must be RFC 8259-safe: no NaN, Infinity, or `-Infinity`.
- Root logger behavior must not be mutated unexpectedly by library imports.
- File logging must not silently create unsafe logs with sensitive payloads.

## Current Logging Surface

Current helper module:

```python
"""Safe debugging helpers for AutoPulse telemetry workflows."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Mapping


RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
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


def sanitize_debug_value(value: Any) -> Any:
    """Return a debug-safe copy of a value.

    Raw VIN-like strings and sensitive key names are redacted. ``vin_hashed`` is
    preserved because it is the public vehicle identifier required by AutoPulse
    audit trails.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = sanitize_debug_value(item)
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(item)
        return sanitized

    if isinstance(value, list):
        return [sanitize_debug_value(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_debug_value(item) for item in value]

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

    payload = {"event": event, **sanitize_debug_value(fields)}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
```

Current debug CLI logging behavior:

- `python -m autopulse.debug --verbose ...` enables DEBUG logging on the `autopulse` logger only.
- It does not configure the root logger.
- Replay validation warnings log `error_type` and `row_index`, not rejected values.
- Guard/security logs use safe event codes/service IDs.

Relevant current `src/autopulse/debug.py` excerpts:

```python
"""Developer debugging CLI for sanitized AutoPulse workflows."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.alert_exporter import _sanitize_window_summary, _validate_vin_hash
from autopulse.debugging import log_event, sanitize_debug_value
from autopulse.data.validator import (
    EV_OBD_FRAME_SCHEMA,
    EV_PROTOCOLS,
    ICE_PROTOCOLS,
    RESTRICTED_SERVICE_IDS,
    route_and_validate,
    validate_ev_frame,
    validate_frame,
)
from autopulse.replayer import ReplayMode, replay_ev_sequence
from tests.simulation.virtual_replay import (
    EVMockAdapter,
    JSONLProvider,
    MockAdapter,
    PROTOCOL_ALIASES,
    SecurityViolationError,
    US001_BOUNDS,
)


LOGGER = logging.getLogger("autopulse.debug")
_SAFE_GUARD_EVENT_PATTERN = re.compile(
    r"^(?:[A-Z0-9_]+(?::0x[0-9A-F]{2}/0x[0-9A-F]{2})?|0x[0-9A-F]{2})$"
)
_RED_LINE_HEX = frozenset(
    f"0x{service_id:02X}" for service_id in RESTRICTED_SERVICE_IDS
)


def _preview_alerts_command(args: argparse.Namespace) -> int:
    try:
        rows = _load_jsonl(args.jsonl)
    except Exception as exc:
        _write_json(_error_result(exc))
        return 1

    processors: dict[str, PdMProcessor] = {}
    alerts: list[dict[str, Any]] = []
    rejected_frames = 0
    total_rows = 0

    for row_index, row in enumerate(rows, start=1):
        total_rows += 1
        try:
            frame = _normalize_ice_preview_row(row)
            validate_frame(frame)
            vin_hashed = str(frame["vin_hashed"])
            _validate_vin_hash(vin_hashed)
        except (ValidationError, ValueError, TypeError) as exc:
            rejected_frames += 1
            _log_validation_rejection(exc, row_index)
            continue

        processor = processors.setdefault(
            vin_hashed,
            PdMProcessor(vin_hashed=vin_hashed),
        )
        alert = processor.process_frame(frame)
        if alert.failure_type != "NONE" and alert.failure_probability > 0.0:
            alerts.append(_serialize_preview_alert(alert))

    log_event(
        LOGGER,
        logging.DEBUG,
        "preview_alerts_completed",
        total_rows=total_rows,
        rejected_frames=rejected_frames,
        sessions=len(processors),
        alerts=len(alerts),
    )
    _write_json(alerts)
    return 0


def _replay_rows(
    powertrain_type: str,
    rows: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    adapter = (
        EVMockAdapter(JSONLProvider(rows))
        if powertrain_type == "EV"
        else MockAdapter(JSONLProvider(rows))
    )
    total_rows = 0
    accepted_frames = 0
    rejected_frames = 0
    security_violations = 0
    guard_events: list[str] = []
    seen_guard_count = 0
    seen_ice_security_count = 0

    adapter.connect()
    try:
        while True:
            try:
                adapter.fetch_frame()
                total_rows += 1
                accepted_frames += 1
            except StopIteration:
                break
            except SecurityViolationError as exc:
                total_rows += 1
                if powertrain_type == "EV":
                    new_events = _guard_events_from_security_error(exc)
                else:
                    (
                        new_events,
                        seen_guard_count,
                        seen_ice_security_count,
                    ) = _adapter_guard_events(
                        adapter,
                        seen_guard_count,
                        seen_ice_security_count,
                    )
                    if not new_events:
                        new_events = _guard_events_from_security_error(exc)
                guard_events.extend(new_events)
                if _is_red_line_event(exc, new_events):
                    security_violations += 1
                _log_guard_rejection(new_events, total_rows)
            except (ValidationError, ValueError, TypeError) as exc:
                total_rows += 1
                rejected_frames += 1
                _log_validation_rejection(exc, total_rows)
    finally:
        adapter.disconnect()

    return {
        "ok": True,
        "powertrain_type": powertrain_type,
        "total_rows": total_rows,
        "accepted_frames": accepted_frames,
        "rejected_frames": rejected_frames,
        "security_violations": security_violations,
        "guard_events": _safe_guard_events(guard_events),
        "mode": mode,
    }


def _error_result(exc: Exception) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "error_type": type(exc).__name__,
    }
    if isinstance(exc, ValidationError):
        result["path"] = list(exc.path)
        result["validator"] = exc.validator
    else:
        result["error"] = str(exc)
    return sanitize_debug_value(result)


def _serialize_preview_alert(alert: Any) -> dict[str, Any]:
    _validate_vin_hash(alert.vin_hashed)
    payload = asdict(alert)
    payload["window_summary"] = _sanitize_window_summary(alert.window_summary)
    payload.pop("obd_frame", None)
    return sanitize_debug_value(payload)


def _guard_events_from_security_error(exc: SecurityViolationError) -> list[str]:
    message = str(exc)
    if message.startswith("SECURITY_VIOLATION_RED_LINE"):
        return ["SECURITY_VIOLATION_RED_LINE"]
    code = message.split(":", 1)[0]
    return _safe_guard_events([code])


def _safe_guard_events(events: list[str]) -> list[str]:
    return [event for event in events if _SAFE_GUARD_EVENT_PATTERN.fullmatch(event)]


def _is_red_line_event(exc: SecurityViolationError, events: list[str]) -> bool:
    if str(exc).startswith("SECURITY_VIOLATION_RED_LINE"):
        return True
    return any(
        event.startswith("SECURITY_VIOLATION_RED_LINE") or event in _RED_LINE_HEX
        for event in events
    )


def _log_validation_rejection(exc: Exception, row_index: int) -> None:
    log_event(
        LOGGER,
        logging.WARNING,
        "replay_row_rejected",
        error_type=type(exc).__name__,
        row_index=row_index,
    )


def _log_guard_rejection(events: list[str], row_index: int) -> None:
    for event in events:
        log_event(
            LOGGER,
            logging.ERROR,
            "replay_guard_event",
            event_code=event,
            row_index=row_index,
        )


def _write_json(payload: Any) -> None:
    print(json.dumps(sanitize_debug_value(payload), allow_nan=False, sort_keys=True))


def _configure_logging(verbose: bool) -> None:
    if not verbose:
        return
    logger = logging.getLogger("autopulse")
    logger.setLevel(logging.DEBUG)
    if not any(getattr(handler, "_autopulse_debug_cli", False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler._autopulse_debug_cli = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
```

Relevant current `tests/test_debugging.py` contents:

```python
"""Debugging support tests for sanitized logs and CLI output."""

from __future__ import annotations

import json
import logging

import pytest

from autopulse import debug as debug_module
from autopulse.debug import main as debug_main
from autopulse.debugging import REDACTED, log_event, sanitize_debug_value
from autopulse.data.validator import command_filter


RAW_VIN = "1HGCM82633A004352"
VIN_HASHED = "a" * 64


def test_sanitize_debug_value_redacts_raw_vin_and_sensitive_keys() -> None:
    value = {
        "raw_vin": RAW_VIN,
        "vin_hashed": VIN_HASHED,
        "nested": {
            "payload_bytes": "2E F4 B2 00",
            "message": f"blocked raw VIN {RAW_VIN}",
        },
    }

    sanitized = sanitize_debug_value(value)

    assert sanitized["raw_vin"] == REDACTED
    assert sanitized["vin_hashed"] == VIN_HASHED
    assert sanitized["nested"]["payload_bytes"] == REDACTED
    assert sanitized["nested"]["message"] == f"blocked raw VIN {REDACTED}"
    assert RAW_VIN not in json.dumps(sanitized)
    assert "2E F4 B2 00" not in json.dumps(sanitized)


def test_sanitize_debug_value_redacts_nested_raw_vins() -> None:
    value = {"outer": {"inner": {"msg": f"VIN is {RAW_VIN}"}}}

    sanitized = sanitize_debug_value(value)

    assert RAW_VIN not in json.dumps(sanitized)
    assert sanitized["outer"]["inner"]["msg"] == f"VIN is {REDACTED}"


def test_sanitize_debug_value_preserves_non_sensitive_vin_substrings() -> None:
    sanitized = sanitize_debug_value(
        {
            "conviction_score": 0.9,
            "provisioning_step": "validate",
            "raw_vin": RAW_VIN,
        }
    )

    assert sanitized["conviction_score"] == 0.9
    assert sanitized["provisioning_step"] == "validate"
    assert sanitized["raw_vin"] == REDACTED


def test_sanitize_debug_value_redacts_raw_vin_in_lists() -> None:
    sanitized = sanitize_debug_value(["normal", RAW_VIN, f"seen {RAW_VIN}"])

    assert sanitized == ["normal", REDACTED, f"seen {REDACTED}"]


def test_log_event_emits_json_without_raw_vin_or_payload_bytes(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging"):
        log_event(
            logger,
            logging.DEBUG,
            "debug_test",
            raw_vin=RAW_VIN,
            vin_hashed=VIN_HASHED,
            payload_bytes="2E F4 B2 00",
            service_id="0x2E",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["event"] == "debug_test"
    assert payload["raw_vin"] == REDACTED
    assert payload["vin_hashed"] == VIN_HASHED
    assert payload["payload_bytes"] == REDACTED
    assert payload["service_id"] == "0x2E"
    assert RAW_VIN not in caplog.text
    assert "2E F4 B2 00" not in caplog.text


def test_log_event_redacts_secret_and_token(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging.secrets")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.secrets"):
        log_event(
            logger,
            logging.DEBUG,
            "auth_attempt",
            secret="sk-abc123",
            token="Bearer xyz",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["secret"] == REDACTED
    assert payload["token"] == REDACTED
    assert "sk-abc123" not in caplog.text
    assert "Bearer xyz" not in caplog.text


def test_log_event_emits_nothing_when_level_disabled(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.level_guard")
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        with caplog.at_level(logging.WARNING, logger="tests.level_guard"):
            log_event(logger, logging.DEBUG, "should_not_emit", secret="sk-abc")
    finally:
        logger.setLevel(original_level)

    assert len(caplog.records) == 0
    assert "sk-abc" not in caplog.text


def test_security_block_logging_omits_raw_payload_bytes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="autopulse.data.validator"):
        with pytest.raises(Exception):
            command_filter(0x2E)

    assert "security_service_blocked" in caplog.text
    assert "0x2E" in caplog.text
    assert RAW_VIN not in caplog.text
    assert "payload_bytes" not in caplog.text


def test_debug_cli_validate_ev_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979-3",
        "powertrain_type": "EV",
        "payload": {
            "battery_soh": 95.0,
            "battery_soce": 80.0,
            "battery_temp_avg": 35.0,
            "payload_bytes": "2E F4 B2 00",
        },
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "EV",
            "--json",
            json.dumps(frame),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValidationError"
    assert RAW_VIN not in captured.out
    assert "2E F4 B2 00" not in captured.out


def test_debug_cli_validate_ice_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979",
        "engine_rpm": 900.0,
        "vehicle_speed": 40,
        "coolant_temp": 90.0,
        "engine_load": 32.0,
        "stft_bank1": 1.0,
        "ltft_bank1": -1.0,
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "ICE",
            "--json",
            json.dumps(frame),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValidationError"
    assert RAW_VIN not in captured.out


def test_debug_cli_validate_routed_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979-3",
        "powertrain_type": "EV",
        "payload": {
            "battery_soh": 95.0,
            "battery_soce": 80.0,
            "battery_temp_avg": 35.0,
        },
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "ROUTED",
            "--json",
            json.dumps(frame),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValidationError"
    assert RAW_VIN not in captured.out


def test_debug_cli_verbose_logging_is_scoped_to_autopulse_logger() -> None:
    root_logger = logging.getLogger()
    autopulse_logger = logging.getLogger("autopulse")
    original_root_level = root_logger.level
    original_autopulse_level = autopulse_logger.level
    original_handlers = list(autopulse_logger.handlers)

    try:
        debug_module._configure_logging(True)

        assert root_logger.level == original_root_level
        assert autopulse_logger.level == logging.DEBUG
        assert any(
            getattr(handler, "_autopulse_debug_cli", False)
            for handler in autopulse_logger.handlers
        )
    finally:
        autopulse_logger.handlers = original_handlers
        autopulse_logger.setLevel(original_autopulse_level)
        root_logger.setLevel(original_root_level)
```

Relevant current `tests/test_debug_cli_replay.py` excerpts:

```python
def test_replay_ev_security_events_distinguish_red_line_and_rate_limit(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(__service_id__="0x2E"),
            ev_row(__service_id__="0x3E", __now__=10.0),
            ev_row(__service_id__="0x3E", __now__=12.0),
            ev_row(),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["accepted_frames"] == 2
    assert summary["security_violations"] == 1  # rate-limit must not count as red-line
    assert "SECURITY_VIOLATION_RED_LINE" in summary["guard_events"]
    assert "TESTER_PRESENT_RATE_LIMIT" in summary["guard_events"]
    assert_no_raw_vin(captured.out)


def test_preview_alerts_raw_vin_in_vin_hashed_is_rejected_cleanly(tmp_path, capsys):
    path = write_jsonl(tmp_path, [ice_row(vin_hashed=RAW_VIN)])

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert alerts == []
    assert RAW_VIN not in captured.out


def test_inspect_guards_output_is_rfc8259_safe(capsys):
    exit_code = debug_main(["inspect-guards"])

    payload, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert payload["restricted_service_ids"]
    assert "NaN" not in captured.out
    assert "Infinity" not in captured.out


def test_replay_ev_verbose_logging_omits_rejected_field_values(tmp_path, caplog):
    path = write_jsonl(tmp_path, [ev_row(battery_temp_avg=999)])

    with caplog.at_level(logging.WARNING, logger="autopulse"):
        exit_code = debug_main(["--verbose", "replay-ev", "--jsonl", str(path)])

    assert exit_code == 0
    assert "ValidationError" in caplog.text
    assert "999" not in caplog.text
    assert RAW_VIN not in caplog.text
```

## Proposed Runtime Logging Hardening Scope

Codex is considering implementing:

1. **Runtime Logging Policy**
   - Define a documented event taxonomy for:
     - schema validation
     - replay accepted/rejected rows
     - guard/security events
     - alert serialization/preview
     - adapter connect/disconnect
     - future live capture start/stop/failure events
   - Define allowed and forbidden log fields.

2. **Logging Configuration Helper**
   - Add an explicit helper, likely in `src/autopulse/debugging.py`, for configuring AutoPulse logging.
   - Requirements:
     - no root logger mutation
     - idempotent handler setup
     - optional console handler
     - optional file handler under a caller-provided path
     - explicit log level
     - structured JSON output where practical
     - always sanitize values before emission

3. **File Logging Safety**
   - If file logging is added:
     - no default unsafe path
     - no automatic capture of raw frame payloads
     - parent directories should be explicit or safely created only when requested
     - file content must be sanitized and RFC 8259-safe
     - future retention/rotation expectations documented

4. **Tests**
   - Extend `tests/test_debugging.py` or create `tests/test_runtime_logging.py`.
   - Cover:
     - redaction in console and file logs
     - no root logger mutation
     - duplicate handler/idempotency behavior
     - level filtering
     - non-finite numeric rejection or safe serialization
     - raw VIN and sensitive-key redaction
     - rejected frame values absent from log output
     - interaction with existing `--verbose` CLI behavior

5. **Documentation**
   - Update `CONTEXT.md` and possibly `docs/` with:
     - runtime logging policy
     - local operator guidance
     - retention/rotation notes
     - explicit statement that live vehicle capture remains deferred

## Open Design Questions for Claude

Please evaluate these before Codex implements:

1. Should runtime logs use only JSON events, or is a mixed model acceptable for startup/configuration messages?
2. Should `log_event()` raise on non-finite numbers, or should the logging config use `json.dumps(..., allow_nan=False)` and fail closed?
3. Should file logging require an explicit path every time, or is a conventional local path such as `logs/autopulse.log` acceptable?
4. Should runtime logging include `vin_hashed` in all vehicle-related events, or only when needed for traceability?
5. Should `sanitize_debug_value()` continue preserving `vin_hashed` blindly, or should it validate the value shape when logging runtime events?
6. Should file handlers use rotation now, or should rotation be documented as future work?
7. Should logging configuration belong in `autopulse.debugging`, or should it be promoted to a new `autopulse.logging`/`autopulse.observability` module to avoid the "debug-only" name?

## Required Output

Produce a Markdown adversarial QA plan with these sections:

1. **Audit Verdict**
   - Is the proposed logging-hardening scope safe to implement?
   - Identify any blockers or required design changes before Codex starts.

2. **Threat Model**
   - Privacy leakage paths.
   - Security boundary weakening paths.
   - Operational risks from file logging or handler configuration.

3. **Required Implementation Constraints**
   - Exact must/never rules for log fields, handlers, file output, levels, and serialization.

4. **Positive Test Scenarios**
   - Expected successful behavior for console logging, file logging, structured events, CLI verbose mode, and idempotent config.

5. **Negative and Adversarial Test Scenarios**
   - Raw VIN leakage attempts.
   - Sensitive key leakage attempts.
   - Rejected validation value leakage.
   - Non-finite numbers.
   - Duplicate handlers.
   - Root logger mutation.
   - Unsafe file path or accidental log creation.
   - Guard/security event pollution.

6. **Recommended Test Structure**
   - Test file placement and naming.
   - `caplog`/tmp_path patterns.
   - Assertions to prefer and assertions to avoid.

7. **Open Questions / Blockers**
   - Decisions that must be resolved before Codex implements.

8. **Sign-Off Language**
   - State whether Codex is approved to begin implementation after addressing any blockers.

Do not write implementation code. This is a pre-implementation adversarial planning handoff for Runtime Logging Hardening.
