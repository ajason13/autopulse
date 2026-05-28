"""CLI for the stationary read-only live smoke harness."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from autopulse.live.adapter import LiveOBDAdapter
from autopulse.live.harness import SmokeHarnessConfig, run_smoke_capture, validate_config
from autopulse.logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        _validate_runtime_log_path(args.runtime_log_path)
    except Exception as exc:
        parser.error(str(exc))

    logger = configure_logging(
        level=logging.DEBUG if args.verbose else logging.INFO,
        console=True,
        file_path=args.runtime_log_path,
    )

    config = SmokeHarnessConfig(
        adapter_port=args.adapter_port,
        vin_hashed=args.vin_hashed,
        output_path=args.output_path,
        max_samples=args.max_samples,
        max_duration_seconds=args.max_duration_seconds,
        confirmed_stationary=args.confirmed_stationary,
        dry_run=args.dry_run,
    )

    try:
        validate_config(config)
    except Exception as exc:
        parser.error(str(exc))

    adapter = LiveOBDAdapter(args.adapter_port)
    summary = run_smoke_capture(config, adapter, logger=logger)
    print(json.dumps(summary.to_dict(), allow_nan=False, sort_keys=True))
    return summary.exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m autopulse.live.cli",
        description="Run a stationary read-only AutoPulse vehicle smoke capture.",
    )
    parser.add_argument("--adapter-port", required=True)
    parser.add_argument("--vin-hashed", required=True)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--runtime-log-path", type=Path)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--max-duration-seconds", type=float)
    parser.add_argument("--confirmed-stationary", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _validate_runtime_log_path(path: Path | None) -> None:
    if path is None:
        return
    if ".." in path.parts:
        raise ValueError("runtime log path must not contain '..'.")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
