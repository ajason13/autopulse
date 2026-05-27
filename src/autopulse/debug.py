"""Developer debugging CLI for sanitized AutoPulse workflows."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from jsonschema import ValidationError

from autopulse.debugging import sanitize_debug_value
from autopulse.data.validator import route_and_validate, validate_ev_frame, validate_frame
from autopulse.replayer import ReplayMode, replay_ev_sequence


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
        frames = replay_ev_sequence(rows, mode=args.mode, env=args.env)
    except Exception as exc:
        _write_json(_error_result(exc))
        return 1

    _write_json(
        {
            "ok": True,
            "powertrain_type": "EV",
            "frames": len(frames),
            "mode": args.mode,
        }
    )
    return 0


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
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise TypeError(f"JSONL row {line_number} must be an object.")
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


def _write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(sanitize_debug_value(payload), sort_keys=True))


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
