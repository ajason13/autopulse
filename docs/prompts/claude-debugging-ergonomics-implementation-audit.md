# Claude Implementation Audit Prompt: Future Debugging Ergonomics

You are Claude Sonnet 4.6 acting as the AutoPulse Lead Auditor.

## Stage

Implementation audit / merge-readiness review for branch `debugging-ergonomics`.

This branch has not been merged into `main`. The relevant changed file contents are included below so you can review in Claude Chat without repository access.

## Project Context

AutoPulse is an educational, read-only OBD-II anomaly detection framework. It detects statistical drift in read-only telemetry before DTCs appear.

The governance model is:

- Antigravity / Gemini owns architecture and coordination.
- Codex owns implementation and local verification.
- Claude owns adversarial QA and final sign-off before merge.

Security and privacy constraints:

- AutoPulse must remain read-only. No writes, clears, controls, routines, security access, diagnostic session escalation, or active probing.
- Data contracts in `schemas/` are the source of truth.
- Debug logs and CLI stdout must preserve `vin_hashed` only.
- Raw VINs, raw diagnostic payload bytes, seed-key material, tokens, secrets, private workspace links, and rejected frame content must not be logged or serialized.
- `guard_events` must contain safe code strings only, never raw exception messages, frame field values, or DTC values.
- JSON output must be RFC 8259-safe: no NaN, Infinity, or `-Infinity`.

## What Codex Implemented

Codex implemented the Future Debugging Ergonomics scope:

- Robust row-by-row `replay-ev` summaries with accepted/rejected/security tallies.
- New robust row-by-row `replay-ice` summaries.
- `preview-alerts --jsonl <path>` for ICE frames, using one `PdMProcessor` per `vin_hashed`.
- `inspect-guards` JSON output for ICE bounds, EV bounds, restricted services, and protocol constants.
- Shared `.vscode/launch.json` debug profiles.
- New regression tests in `tests/test_debug_cli_replay.py`.
- `CONTEXT.md` updated with implementation status and verification.

## Verification Evidence

Codex ran:

- `python3 -m pytest tests/test_debug_cli_replay.py tests/test_debugging.py -q` -> `22 passed`
- `python3 -m pytest tests/test_debug_cli_replay.py tests/test_debugging.py tests/test_us006_ev_replay_harness.py tests/test_us006_ev_adapter_security.py tests/test_us005_alert_exporter.py tests/test_us003_pdm_algorithms.py tests/test_us004_smoothing.py -q` -> `272 passed`
- `python3 -m pytest -q` -> `553 passed`
- `git diff --check` -> passed

## Review Targets

Please review the embedded file contents below, especially:

- `src/autopulse/debug.py`
- `tests/test_debug_cli_replay.py`
- `.vscode/launch.json`
- `CONTEXT.md` excerpt

Focus on:

- Privacy leaks in stdout or logs.
- Whether row-level replay failures are categorized correctly.
- Whether security guard events are counted and serialized safely.
- Whether red-line UDS/security behavior remains blocked and fail-closed.
- Whether `preview-alerts` session partitioning by `vin_hashed` is correct.
- Whether importing replay adapters from `tests.simulation.virtual_replay` in the CLI is acceptable or a blocker.
- Whether `_sanitize_window_summary` and `_validate_vin_hash` private imports from `alert_exporter.py` are acceptable or should be replaced before merge.
- Whether `.vscode/launch.json` should be committed or documented only.
- Missing adversarial tests or regression coverage.

## Required Output

Return:

1. PASS/FAIL verdict.
2. Blockers ordered by severity, with file/function references.
3. Non-blocking recommendations.
4. Missing tests or edge cases.
5. Explicit sign-off language: either "approved for merge" or "not approved for merge."

Distinguish security/privacy blockers from maintainability concerns and future-work recommendations.

## File Contents

### `src/autopulse/debug.py`

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


def main(argv: list[str] | None = None) -> int:
    """Run the AutoPulse debug CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    return args.func(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m autopulse.debug",
        description="Run sanitized AutoPulse validation and replay debug helpers.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logs from AutoPulse modules.",
    )

    subparsers = parser.add_subparsers(required=True)

    validate_parser = subparsers.add_parser(
        "validate-frame",
        help="Validate one ICE, EV, or routed telemetry frame.",
    )
    validate_parser.add_argument(
        "--powertrain",
        choices=["ICE", "EV", "ROUTED"],
        required=True,
        help="Validation path to use.",
    )
    _add_json_input_args(validate_parser)
    validate_parser.set_defaults(func=_validate_frame_command)

    replay_parser = subparsers.add_parser(
        "replay-ev",
        help="Replay EV JSONL rows through the US-006 replay adapter.",
    )
    replay_parser.add_argument(
        "--jsonl",
        required=True,
        type=Path,
        help="Path to a JSONL file containing EV rows.",
    )
    replay_parser.add_argument(
        "--mode",
        choices=[ReplayMode.PASSIVE, ReplayMode.BURST],
        default=ReplayMode.PASSIVE,
        help="Replay mode. BURST remains test-scoped by env guardrails.",
    )
    replay_parser.add_argument(
        "--env",
        default="test",
        help="Replay environment flag used by the burst-mode guard.",
    )
    replay_parser.set_defaults(func=_replay_ev_command)

    replay_ice_parser = subparsers.add_parser(
        "replay-ice",
        help="Replay ICE JSONL rows through the US-002 replay adapter.",
    )
    replay_ice_parser.add_argument(
        "--jsonl",
        required=True,
        type=Path,
        help="Path to a JSONL file containing ICE rows.",
    )
    replay_ice_parser.set_defaults(func=_replay_ice_command)

    preview_alerts_parser = subparsers.add_parser(
        "preview-alerts",
        help="Preview ICE PdM alerts from a JSONL replay file.",
    )
    preview_alerts_parser.add_argument(
        "--jsonl",
        required=True,
        type=Path,
        help="Path to a JSONL file containing ICE rows.",
    )
    preview_alerts_parser.set_defaults(func=_preview_alerts_command)

    inspect_guards_parser = subparsers.add_parser(
        "inspect-guards",
        help="Print read-only diagnostic guard constants.",
    )
    inspect_guards_parser.set_defaults(func=_inspect_guards_command)

    return parser


def _add_json_input_args(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="Inline JSON object to validate.")
    source.add_argument("--file", type=Path, help="Path to a JSON object file.")


def _validate_frame_command(args: argparse.Namespace) -> int:
    frame = _load_json_object(args)
    try:
        if args.powertrain == "ICE":
            validate_frame(frame)
            result: dict[str, Any] = {"ok": True, "powertrain_type": "ICE"}
        elif args.powertrain == "EV":
            validate_ev_frame(frame)
            result = {"ok": True, "powertrain_type": "EV"}
        else:
            routed = route_and_validate(frame)
            result = {"ok": True, "powertrain_type": routed}
    except Exception as exc:
        result = _error_result(exc)
        _write_json(result)
        return 1

    _write_json(result)
    return 0


def _replay_ev_command(args: argparse.Namespace) -> int:
    try:
        rows = _load_jsonl(args.jsonl)
    except Exception as exc:
        _write_json(_error_result(exc))
        return 1

    if args.mode == ReplayMode.BURST and args.env != "test":
        try:
            replay_ev_sequence(rows, mode=args.mode, env=args.env)
        except Exception as exc:
            _write_json(_error_result(exc))
            return 1

    _write_json(_replay_rows("EV", rows, mode=args.mode))
    return 0


def _replay_ice_command(args: argparse.Namespace) -> int:
    try:
        rows = _load_jsonl(args.jsonl)
    except Exception as exc:
        _write_json(_error_result(exc))
        return 1

    _write_json(_replay_rows("ICE", rows, mode=ReplayMode.PASSIVE))
    return 0


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


def _inspect_guards_command(args: argparse.Namespace) -> int:
    del args
    _write_json(
        {
            "ice_bounds": {
                name: {"minimum": lower, "maximum": upper}
                for name, (lower, upper) in sorted(US001_BOUNDS.items())
            },
            "ev_bounds": _ev_bounds(),
            "restricted_service_ids": [
                f"0x{service_id:02X}" for service_id in sorted(RESTRICTED_SERVICE_IDS)
            ],
            "ice_protocols": sorted(ICE_PROTOCOLS),
            "ev_protocols": sorted(EV_PROTOCOLS),
        }
    )
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


def _load_json_object(args: argparse.Namespace) -> dict[str, Any]:
    if args.json is not None:
        value = json.loads(args.json)
    else:
        value = json.loads(args.file.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise TypeError("debug input must be a JSON object.")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSONL row {line_number}.") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Malformed JSONL row {line_number}.")
            rows.append(value)
    return rows


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


def _normalize_ice_preview_row(row: dict[str, Any]) -> dict[str, Any]:
    frame = dict(row.get("payload") if isinstance(row.get("payload"), dict) else row)
    protocol = str(frame.get("protocol", row.get("protocol", "SAE_J1979")))
    frame["protocol"] = PROTOCOL_ALIASES.get(protocol, protocol)
    if frame["protocol"] == "J1979_MODE01":
        frame["protocol"] = "SAE_J1979"
    elif frame["protocol"] == "J1979_2_SERVICE22":
        frame["protocol"] = "SAE_J1979-2"
    return frame


def _serialize_preview_alert(alert: Any) -> dict[str, Any]:
    _validate_vin_hash(alert.vin_hashed)
    payload = asdict(alert)
    payload["window_summary"] = _sanitize_window_summary(alert.window_summary)
    payload.pop("obd_frame", None)
    return sanitize_debug_value(payload)


def _adapter_guard_events(
    adapter: Any,
    seen_guard_count: int,
    seen_ice_security_count: int,
) -> tuple[list[str], int, int]:
    events: list[str] = []
    adapter_events = getattr(adapter, "events", [])
    if isinstance(adapter_events, list):
        events.extend(str(event) for event in adapter_events[seen_guard_count:])
        seen_guard_count = len(adapter_events)

    security_events = getattr(adapter, "security_violations", [])
    if isinstance(security_events, list):
        events.extend(str(event) for event in security_events[seen_ice_security_count:])
        seen_ice_security_count = len(security_events)

    return _safe_guard_events(events), seen_guard_count, seen_ice_security_count


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
        event.startswith("SECURITY_VIOLATION_RED_LINE") or event.startswith("0x")
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


def _ev_bounds() -> dict[str, dict[str, float]]:
    payload = EV_OBD_FRAME_SCHEMA["properties"]["payload"]["properties"]
    bounds: dict[str, dict[str, float]] = {}
    for name, schema in payload.items():
        if "minimum" in schema and "maximum" in schema:
            bounds[name] = {
                "minimum": schema["minimum"],
                "maximum": schema["maximum"],
            }
    return bounds


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


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
```

### `tests/test_debug_cli_replay.py`

```python
"""Debug CLI replay, alert preview, and guard inspection tests."""

from __future__ import annotations

import json
import logging
import math
import re

import pytest

from autopulse.debug import main as debug_main
from tests.simulation.virtual_replay import NoiseGenerator


RAW_VIN = "1HGCM82633A004352"


def write_jsonl(tmp_path, rows, filename="rows.jsonl"):
    path = tmp_path / filename
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def ev_row(**overrides):
    row = {
        "timestamp": "2026-05-26T10:00:00.000Z",
        "vin_hashed": "e" * 64,
        "protocol": "SAE_J1979-3",
        "battery_soh": 95.0,
        "battery_soce": 80.0,
        "battery_temp_avg": 35.0,
    }
    row.update(overrides)
    return row


def ice_row(**overrides):
    row = {
        "timestamp": "2026-05-26T10:00:00.000Z",
        "vin_hashed": "c" * 64,
        "protocol": "J1979_MODE01",
        "engine_rpm": 1200.0,
        "vehicle_speed": 30,
        "coolant_temp": 88.0,
        "engine_load": 22.0,
        "stft_bank1": 0.5,
        "ltft_bank1": -0.5,
    }
    row.update(overrides)
    return row


def parsed_stdout(capsys: pytest.CaptureFixture[str]):
    captured = capsys.readouterr()
    return json.loads(captured.out), captured


def assert_no_raw_vin(stdout: str) -> None:
    assert RAW_VIN not in stdout
    assert not re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", stdout)


def test_replay_ev_robust_loop_tallies_schema_rejections_without_crash(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(),
            ev_row(battery_temp_avg=999),
            ev_row(),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["ok"] is True
    assert summary["powertrain_type"] == "EV"
    assert summary["total_rows"] == 3
    assert summary["accepted_frames"] == 2
    assert summary["rejected_frames"] == 1
    assert summary["security_violations"] == 0
    assert summary["guard_events"] == []
    assert_no_raw_vin(captured.out)


def test_replay_ev_all_invalid_rows_still_returns_success_summary(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(battery_soce=math.nan),
            ev_row(battery_temp_avg=999),
            ev_row(battery_soh=None),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["ok"] is True
    assert summary["accepted_frames"] == 0
    assert summary["rejected_frames"] == 3
    assert summary["security_violations"] == 0


def test_replay_ev_malformed_jsonl_is_pre_loop_error(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(ev_row()) + "\nnot-json\n", encoding="utf-8")

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    payload, captured = parsed_stdout(capsys)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValueError"
    assert "not-json" not in captured.out


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
    assert summary["security_violations"] == 1
    assert "SECURITY_VIOLATION_RED_LINE" in summary["guard_events"]
    assert "TESTER_PRESENT_RATE_LIMIT" in summary["guard_events"]
    assert_no_raw_vin(captured.out)


def test_replay_ice_robust_loop_tallies_out_of_bounds_rpm(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ice_row(),
            ice_row(engine_rpm=9501),
            ice_row(),
        ],
    )

    exit_code = debug_main(["replay-ice", "--jsonl", str(path)])

    summary, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["powertrain_type"] == "ICE"
    assert summary["accepted_frames"] == 2
    assert summary["rejected_frames"] == 1


def test_replay_ice_security_violation_uses_safe_guard_event(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ice_row(),
            NoiseGenerator.inject_restricted_service(ice_row(), "0x2E"),
        ],
    )

    exit_code = debug_main(["replay-ice", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["accepted_frames"] == 1
    assert summary["security_violations"] == 1
    assert summary["guard_events"] == ["0x2E"]
    assert_no_raw_vin(captured.out)


def test_preview_alerts_outputs_hdf_alerts_partitioned_by_vin(tmp_path, capsys):
    healthy_vin = "a" * 64
    fault_vin = "b" * 64
    rows = [
        ice_row(vin_hashed=healthy_vin, engine_load=5.0),
        ice_row(
            vin_hashed=fault_vin,
            engine_rpm=900.0,
            engine_load=5.0,
            coolant_temp=30.0,
            ambient_temp=25.0,
        ),
    ]
    path = write_jsonl(tmp_path, rows)

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert len(alerts) == 1
    assert alerts[0]["vin_hashed"] == fault_vin
    assert alerts[0]["failure_type"] == "HDF"
    assert alerts[0]["failure_probability"] > 0.0
    assert_no_raw_vin(captured.out)


def test_preview_alerts_schema_invalid_frame_does_not_stop_vin_session(tmp_path, capsys):
    vin = "d" * 64
    rows = [
        ice_row(
            vin_hashed=vin,
            timestamp="2026-05-26T10:00:00.000Z",
            engine_rpm=1200.0,
            engine_load=5.0,
        ),
        ice_row(vin_hashed=vin, engine_rpm=99999.0),
        ice_row(
            vin_hashed=vin,
            timestamp="2026-05-26T10:01:00.000Z",
            engine_rpm=900.0,
            engine_load=5.0,
            coolant_temp=30.0,
            ambient_temp=25.0,
        ),
    ]
    path = write_jsonl(tmp_path, rows)

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert alerts[-1]["vin_hashed"] == vin
    assert alerts[-1]["failure_probability"] > 0.0


def test_inspect_guards_output_contains_expected_safe_constants(capsys):
    exit_code = debug_main(["inspect-guards"])

    payload, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert set(payload) == {
        "ice_bounds",
        "ev_bounds",
        "restricted_service_ids",
        "ice_protocols",
        "ev_protocols",
    }
    assert payload["restricted_service_ids"] == [
        "0x04",
        "0x08",
        "0x10",
        "0x14",
        "0x27",
        "0x2E",
        "0x2F",
        "0x31",
    ]


def test_replay_ev_verbose_logging_omits_rejected_field_values(tmp_path, caplog):
    path = write_jsonl(tmp_path, [ev_row(battery_temp_avg=999)])

    with caplog.at_level(logging.WARNING, logger="autopulse"):
        exit_code = debug_main(["--verbose", "replay-ev", "--jsonl", str(path)])

    assert exit_code == 0
    assert "ValidationError" in caplog.text
    assert "999" not in caplog.text
    assert RAW_VIN not in caplog.text
```

### `.vscode/launch.json`

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "AutoPulse: Validate ICE Frame",
      "type": "debugpy",
      "request": "launch",
      "module": "autopulse.debug",
      "args": [
        "validate-frame",
        "--powertrain",
        "ICE",
        "--file",
        "${workspaceFolder}/tmp/ice-frame.json"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "AutoPulse: Validate EV Frame",
      "type": "debugpy",
      "request": "launch",
      "module": "autopulse.debug",
      "args": [
        "validate-frame",
        "--powertrain",
        "EV",
        "--file",
        "${workspaceFolder}/tmp/ev-frame.json"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "AutoPulse: Replay EV JSONL",
      "type": "debugpy",
      "request": "launch",
      "module": "autopulse.debug",
      "args": [
        "--verbose",
        "replay-ev",
        "--jsonl",
        "${workspaceFolder}/tmp/ev-replay.jsonl"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "AutoPulse: Preview ICE Alerts",
      "type": "debugpy",
      "request": "launch",
      "module": "autopulse.debug",
      "args": [
        "preview-alerts",
        "--jsonl",
        "${workspaceFolder}/tmp/ice-replay.jsonl"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      },
      "console": "integratedTerminal"
    }
  ]
}
```

### `CONTEXT.md` Excerpt

```markdown
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.
*   **EV Implementation Boundary:** US-006 is complete within schema/routing/adapter/replay/JSON-LD safety scope. Do not backfill EV-HDF, EV-OSF, or EV anomaly scoring into US-006; those require a separate story and QA plan.
*   **Debugging Safety:** Debug logs and CLI output must preserve `vin_hashed` only; raw VINs, raw diagnostic payload bytes, seed-key material, tokens, and private workspace links must be redacted or omitted.

## Future Debugging Work
*   Claude signed off on the first debugging layer on 2026-05-25: approved to remain on `main` with no blockers.
*   Branch `debugging-audit-followup` addresses Claude's recommended privacy hardening: precise VIN-key redaction, scoped verbose logging, and adversarial debug-output tests.
*   Future Debugging Ergonomics implementation is in progress on branch `debugging-ergonomics`.
    *   Implemented robust row-by-row `replay-ev` and `replay-ice` summaries with accepted/rejected/security tallies and sanitized guard events.
    *   Implemented `preview-alerts` with per-`vin_hashed` ICE `PdMProcessor` sessions and sanitized alert output.
    *   Implemented `inspect-guards` JSON output for ICE bounds, EV bounds, restricted service IDs, and supported protocol constants.
    *   Added shared `.vscode/launch.json` debug profiles for contributor CLI workflows.
    *   Verification: targeted debug/replay/PdM/alert suites `272 passed`; full suite `553 passed`.
*   Track forward-looking validation-error logging risk if future schemas add string-valued fields.
*   Debugging PR audit requires a file-grounded Claude response. Off-topic ideation or unrelated project recommendations are not accepted as merge sign-off; use `docs/prompts/claude-debugging-foundation-audit.md` for the hardened audit prompt.
```
