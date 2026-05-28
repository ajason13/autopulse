# Claude Prompt: Real Vehicle Smoke Harness Fix Re-Review

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Stage: focused re-review after Codex addressed your conditional-pass blockers.

Branch: `vehicle-smoke-harness-planning`

You previously returned **CONDITIONAL PASS** for the Real Vehicle Read-Only Smoke Harness implementation with two merge blockers:

- **B-01:** `output_path` was not checked for `..` traversal.
- **B-02:** Missing harness-level integration test for security abort path.

Codex applied both fixes and added the recommended `CommandBlockedException` integration coverage.

## Requested Output

Return:

1. Verdict: PASS, CONDITIONAL PASS, or FAIL.
2. Whether B-01 is fixed.
3. Whether B-02 is fixed.
4. Any new blockers introduced by the fixes.
5. Non-blocking follow-ups, if any.
6. Merge recommendation.
7. Separate real-vehicle go/no-go recommendation.

Please focus on the changed areas unless you see a cross-cutting safety or privacy issue.

## Verification

Post-fix verification run by Codex:

- `python3 -m pytest tests/live -q` -> `27 passed`
- `python3 -m pytest tests/live tests/test_runtime_logging.py tests/test_debug_cli_replay.py tests/test_us006_ev_adapter_security.py -q` -> `70 passed`
- `python3 -m pytest -q` -> `598 passed`

## Current Project Status

`CONTEXT.md` relevant excerpt:

```markdown
## Active Work: Real Vehicle Read-Only Smoke Harness
*   **Goal:** Prepare the minimum safe bridge from replay-only tooling to a first stationary vehicle check.
*   **Current status:** Claude returned conditional pass on 2026-05-28; Codex fixed both merge blockers and is waiting on Claude re-review before PR/merge or any real vehicle connection.
*   **Required scope before any vehicle connection:**
    *   Define a stationary-only read-only harness with no write-capable UDS services and no clearing/resetting/coding behavior.
    *   Use a strict safe PID allowlist, max 1 Hz polling, explicit sample limits, and operator stop/failure behavior.
    *   Persist only replay-compatible sanitized JSONL; do not store raw VINs or raw diagnostic payload bytes.
    *   Route runtime events through `autopulse.logging_config.configure_logging()` and `log_event()`.
    *   Add adapter-open failure handling, unsupported-protocol behavior, and no-vehicle/no-ECU negative tests.
    *   Add an operator checklist covering stationary setup, ignition state, battery condition, adapter selection, and stop conditions.
*   **Architecture constraint:** Live vehicle code must live in a source package with a clear adapter boundary. Do not reuse `tests.simulation` replay classes as the live adapter implementation.
*   **Claude QA decisions:** first harness is ICE-only; VIN reads are blocked; operator must supply precomputed `vin_hashed`; all six ICE PIDs are required per accepted sample; `vehicle_speed > 0` is a safety abort; `command_filter()` must run before every outgoing request; max 1 Hz cadence and finite sample/duration limits are enforced in code.
*   **Implementation notes:**
    *   Added `src/autopulse/live/` with live adapter boundary, harness loop, and CLI.
    *   Added `docs/operator-checklists/real-vehicle-smoke-harness.md`.
    *   Added Claude implementation-audit prompt: `docs/prompts/claude-real-vehicle-smoke-harness-implementation-audit.md`.
    *   Initial verification: `tests/live` -> `24 passed`; targeted live/logging/debug/security suite -> `67 passed`; full suite -> `595 passed`.
    *   Conditional-pass fixes: `output_path` traversal rejected; harness-level security abort integration tests added for `SecurityViolationRedLine` and `CommandBlockedException`.
    *   Post-fix verification: `tests/live` -> `27 passed`; targeted live/logging/debug/security suite -> `70 passed`; full suite -> `598 passed`.
*   **Go/no-go:** still no-go for real vehicle until implementation tests pass and Claude performs a second implementation audit.
```

## Changed Implementation: `src/autopulse/live/harness.py`

```python
"""Stationary read-only vehicle smoke-capture harness.

LIVE VEHICLE CODE: this module is intentionally ICE-only and stationary-only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import time
from typing import Callable, Protocol

from jsonschema import ValidationError

from autopulse.data.validator import (
    CommandBlockedException,
    ICE_PROTOCOLS,
    SecurityViolationRedLine,
    validate_frame,
)
from autopulse.debugging import VIN_HASH_PATTERN, get_logger, log_event, sanitize_debug_value
from autopulse.live.adapter import LIVE_ALLOWED_PIDS


OK_EXIT = 0
CONFIG_ERROR_EXIT = 1
SAFETY_ABORT_EXIT = 2
ADAPTER_FAILURE_EXIT = 3
MIN_POLL_INTERVAL_SECONDS = 1.0

LOGGER = get_logger(__name__)

_PID_TO_FIELD = {
    0x0C: "engine_rpm",
    0x0D: "vehicle_speed",
    0x05: "coolant_temp",
    0x04: "engine_load",
    0x06: "stft_bank1",
    0x07: "ltft_bank1",
}

_TRANSPORT_PROTOCOL_ALIASES = {
    "SAE_J1979": "SAE_J1979",
    "SAE_J1979-2": "SAE_J1979-2",
    "SAE J1979": "SAE_J1979",
    "ISO 15765-4": "SAE_J1979",
    "ISO_15765_4": "SAE_J1979",
    "ISO 9141-2": "SAE_J1979",
    "ISO_9141_2": "SAE_J1979",
    "ISO 14230-4": "SAE_J1979",
    "ISO_14230_4": "SAE_J1979",
    "SAE J1850 PWM": "SAE_J1979",
    "SAE J1850 VPW": "SAE_J1979",
}


class SmokeAdapter(Protocol):
    """Protocol implemented by live and fake smoke-capture adapters."""

    def connect(self) -> None:
        """Open the adapter connection."""

    def disconnect(self) -> None:
        """Close the adapter connection."""

    def get_protocol_name(self) -> str:
        """Return the connected adapter protocol name."""

    def query_pid(self, pid: int) -> float | int:
        """Read one allowlisted PID value."""


@dataclass(frozen=True)
class SmokeHarnessConfig:
    adapter_port: str
    vin_hashed: str
    output_path: Path
    max_samples: int | None = None
    max_duration_seconds: float | None = None
    confirmed_stationary: bool = False
    dry_run: bool = False


@dataclass
class SmokeHarnessSummary:
    ok: bool
    exit_code: int
    total_samples: int = 0
    accepted_frames: int = 0
    rejected_frames: int = 0
    safety_abort: bool = False
    adapter_failure: bool = False
    interrupted: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict[str, object]:
        return sanitize_debug_value(asdict(self), validate_vin_shape=True)


def validate_config(config: SmokeHarnessConfig) -> None:
    if not config.adapter_port:
        raise ValueError("adapter_port is required.")
    if not VIN_HASH_PATTERN.fullmatch(config.vin_hashed):
        raise ValueError("vin_hashed must be a lowercase 64-character hex string.")
    if config.max_samples is None and config.max_duration_seconds is None:
        raise ValueError("max_samples or max_duration_seconds is required.")
    if config.max_samples is not None and config.max_samples <= 0:
        raise ValueError("max_samples must be positive.")
    if config.max_duration_seconds is not None and config.max_duration_seconds <= 0:
        raise ValueError("max_duration_seconds must be positive.")
    if ".." in config.output_path.parts:
        raise ValueError("output_path must not contain '..'.")
    if not config.output_path.parent.exists():
        raise FileNotFoundError("output_path parent directory does not exist.")
    if not config.dry_run and not config.confirmed_stationary:
        raise ValueError("stationary preflight confirmation is required.")


def run_smoke_capture(
    config: SmokeHarnessConfig,
    adapter: SmokeAdapter,
    *,
    logger: logging.Logger = LOGGER,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> SmokeHarnessSummary:
    """Run a bounded stationary smoke capture against a live-like adapter."""
    try:
        validate_config(config)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "live_smoke_config_rejected",
            error_type=type(exc).__name__,
        )
        return SmokeHarnessSummary(ok=False, exit_code=CONFIG_ERROR_EXIT)

    if config.dry_run:
        log_event(logger, logging.INFO, "live_smoke_dry_run_validated")
        return SmokeHarnessSummary(ok=True, exit_code=OK_EXIT, dry_run=True)

    try:
        adapter.connect()
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "adapter_open_failed",
            error_type=type(exc).__name__,
        )
        return SmokeHarnessSummary(
            ok=False,
            exit_code=ADAPTER_FAILURE_EXIT,
            adapter_failure=True,
        )

    summary = SmokeHarnessSummary(ok=True, exit_code=OK_EXIT)
    started_at = monotonic()

    try:
        protocol = _normalize_protocol(adapter.get_protocol_name())
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "unsupported_protocol_rejected",
            error_type=type(exc).__name__,
        )
        _disconnect(adapter, logger)
        return SmokeHarnessSummary(
            ok=False,
            exit_code=ADAPTER_FAILURE_EXIT,
            adapter_failure=True,
        )

    try:
        with config.output_path.open("w", encoding="utf-8") as output:
            while _should_continue(config, summary.total_samples, started_at, monotonic):
                cycle_start = monotonic()
                enforce_sleep = True
                try:
                    summary.total_samples += 1
                    frame = _read_frame(adapter, config.vin_hashed, protocol)
                    validate_frame(frame)
                    if frame["vehicle_speed"] > 0:
                        summary.ok = False
                        summary.exit_code = SAFETY_ABORT_EXIT
                        summary.safety_abort = True
                        log_event(
                            logger,
                            logging.ERROR,
                            "motion_detected_during_stationary_capture",
                            vehicle_speed=frame["vehicle_speed"],
                        )
                        enforce_sleep = False
                        return summary
                    output.write(json.dumps(frame, allow_nan=False, sort_keys=True) + "\n")
                    output.flush()
                    summary.accepted_frames += 1
                    log_event(
                        logger,
                        logging.DEBUG,
                        "live_smoke_frame_accepted",
                        row_index=summary.total_samples,
                        vin_hashed=config.vin_hashed,
                    )
                except KeyboardInterrupt:
                    summary.interrupted = True
                    enforce_sleep = False
                    return summary
                except (SecurityViolationRedLine, CommandBlockedException) as exc:
                    summary.ok = False
                    summary.exit_code = SAFETY_ABORT_EXIT
                    summary.safety_abort = True
                    log_event(
                        logger,
                        logging.ERROR,
                        "live_smoke_security_abort",
                        error_type=type(exc).__name__,
                    )
                    enforce_sleep = False
                    return summary
                except (ValidationError, ValueError, TypeError) as exc:
                    summary.rejected_frames += 1
                    log_event(
                        logger,
                        logging.WARNING,
                        "live_smoke_frame_rejected",
                        row_index=summary.total_samples,
                        error_type=type(exc).__name__,
                    )
                except Exception as exc:
                    summary.ok = False
                    summary.exit_code = ADAPTER_FAILURE_EXIT
                    summary.adapter_failure = True
                    log_event(
                        logger,
                        logging.ERROR,
                        "adapter_fetch_error",
                        error_type=type(exc).__name__,
                    )
                    enforce_sleep = False
                    return summary
                finally:
                    if enforce_sleep:
                        _enforce_cadence(cycle_start, monotonic, sleep)
    finally:
        _disconnect(adapter, logger)

    return summary


def _read_frame(adapter: SmokeAdapter, vin_hashed: str, protocol: str) -> dict[str, object]:
    values: dict[str, float | int] = {}
    for pid in sorted(LIVE_ALLOWED_PIDS):
        value = adapter.query_pid(pid)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("PID value must be numeric.")
        if not math.isfinite(float(value)):
            raise ValueError("PID value must be finite.")
        values[_PID_TO_FIELD[pid]] = value

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "vin_hashed": vin_hashed,
        "protocol": protocol,
        "engine_rpm": float(values["engine_rpm"]),
        "vehicle_speed": int(values["vehicle_speed"]),
        "coolant_temp": float(values["coolant_temp"]),
        "engine_load": float(values["engine_load"]),
        "stft_bank1": float(values["stft_bank1"]),
        "ltft_bank1": float(values["ltft_bank1"]),
    }


def _normalize_protocol(protocol: str) -> str:
    normalized = _TRANSPORT_PROTOCOL_ALIASES.get(str(protocol))
    if normalized is None or normalized not in ICE_PROTOCOLS:
        raise ValueError("unsupported live capture protocol")
    return normalized


def _should_continue(
    config: SmokeHarnessConfig,
    total_samples: int,
    started_at: float,
    monotonic: Callable[[], float],
) -> bool:
    if config.max_samples is not None and total_samples >= config.max_samples:
        return False
    if (
        config.max_duration_seconds is not None
        and monotonic() - started_at >= config.max_duration_seconds
    ):
        return False
    return True


def _enforce_cadence(
    cycle_start: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> None:
    elapsed = monotonic() - cycle_start
    sleep(max(0.0, MIN_POLL_INTERVAL_SECONDS - elapsed))


def _disconnect(adapter: SmokeAdapter, logger: logging.Logger) -> None:
    try:
        adapter.disconnect()
        log_event(logger, logging.DEBUG, "adapter_disconnected")
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "adapter_disconnect_failed",
            error_type=type(exc).__name__,
        )
```

## Changed Tests: `tests/live/test_smoke_harness_cli.py`

```python
"""Live smoke harness CLI tests."""

from __future__ import annotations

import json

import pytest

from autopulse.live import cli


VIN_HASHED = "a" * 64


def test_cli_dry_run_validates_without_opening_adapter(tmp_path, capsys):
    exit_code = cli.main(
        [
            "--adapter-port",
            "/dev/tty.fake",
            "--vin-hashed",
            VIN_HASHED,
            "--output-path",
            str(tmp_path / "capture.jsonl"),
            "--max-samples",
            "1",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert not (tmp_path / "capture.jsonl").exists()


def test_cli_requires_vin_hashed_before_adapter_open(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                "A" * 64,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )


def test_cli_requires_limit(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--dry-run",
            ]
        )


def test_cli_requires_stationary_confirmation_for_live_capture(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--max-samples",
                "1",
            ]
        )


def test_cli_rejects_runtime_log_path_traversal_before_opening_file(tmp_path):
    log_path = tmp_path / ".." / "run.log"

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--runtime-log-path",
                str(log_path),
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )

    assert not log_path.exists()


def test_cli_rejects_output_path_traversal(tmp_path):
    output_path = tmp_path / ".." / "capture.jsonl"

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(output_path),
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )

    assert not output_path.exists()
```

## Changed Tests: `tests/live/test_smoke_harness_security.py`

```python
"""Live smoke harness security tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from autopulse.data.validator import CommandBlockedException, SecurityViolationRedLine
from autopulse.live.adapter import LIVE_ALLOWED_PIDS, LiveOBDAdapter, PIDNotAllowedError
from autopulse.live.harness import SAFETY_ABORT_EXIT, SmokeHarnessConfig, run_smoke_capture
from tests.live.fakes import FakeICEAdapter, frame_values


@pytest.mark.parametrize("service_id", [0x2E, 0x31, 0x10, 0x27, 0x2F, 0x08, 0x04])
def test_live_adapter_blocks_write_capable_services_before_transmission(service_id):
    adapter = LiveOBDAdapter("/dev/tty.fake", obd_module=object())

    with pytest.raises(SecurityViolationRedLine):
        adapter.validate_outgoing_request(service_id, 0x0C)


def test_live_adapter_rejects_pid_outside_allowlist():
    adapter = LiveOBDAdapter("/dev/tty.fake", obd_module=object())

    with pytest.raises(PIDNotAllowedError):
        adapter.validate_outgoing_request(0x01, 0x09)


def test_live_pid_allowlist_is_exact_initial_ice_set():
    assert LIVE_ALLOWED_PIDS == {0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D}


def test_live_package_does_not_import_tests_namespace():
    live_root = Path("src/autopulse/live")
    for path in live_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("tests")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("tests")


@pytest.mark.parametrize(
    "exc",
    [
        SecurityViolationRedLine(0x2E),
        CommandBlockedException("SECURITY_VIOLATION_RED_LINE", "blocked"),
    ],
)
def test_security_violation_during_capture_aborts_and_disconnects(
    tmp_path,
    fake_vin_hashed,
    exc,
):
    adapter = FakeICEAdapter([frame_values()], fetch_error=exc)
    config = SmokeHarnessConfig(
        adapter_port="/dev/tty.fake",
        vin_hashed=fake_vin_hashed,
        output_path=tmp_path / "capture.jsonl",
        max_samples=1,
        confirmed_stationary=True,
    )

    summary = run_smoke_capture(config, adapter, sleep=lambda _: None)

    assert summary.exit_code == SAFETY_ABORT_EXIT
    assert summary.safety_abort is True
    assert adapter.disconnected is True
    assert (tmp_path / "capture.jsonl").read_text(encoding="utf-8") == ""
```

## Notes

No actual vehicle connection has been attempted. Current Codex recommendation remains no-go for actual vehicle until this re-review returns PASS and the branch is merged.
