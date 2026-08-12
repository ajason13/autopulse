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
from autopulse.virtual_replay import (
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
