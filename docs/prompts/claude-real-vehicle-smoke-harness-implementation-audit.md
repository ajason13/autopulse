# Claude Prompt: Real Vehicle Read-Only Smoke Harness Implementation Audit

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Stage: implementation audit after your adversarial QA plan.

Branch: `vehicle-smoke-harness-planning`

Review the completed implementation for merge readiness and for eventual stationary vehicle go/no-go. Do not approve actual vehicle connection unless all safety and privacy constraints are satisfied.

## Verification Already Run By Codex

- `python3 -m pytest tests/live -q` -> `24 passed`
- `python3 -m pytest tests/live tests/test_runtime_logging.py tests/test_debug_cli_replay.py tests/test_us006_ev_adapter_security.py -q` -> `67 passed`
- Initial `python3 -m pytest -q` had one unrelated 10 Hz timing tolerance failure in `tests/test_us002_virtual_replay_harness.py::TestLogReplayer10Hz::test_10hz_no_interval_exceeds_tolerance`; isolated rerun passed.
- Final `python3 -m pytest -q` -> `595 passed`

## Review Goals

Evaluate:

- Whether live code is isolated under `src/autopulse/live/`.
- Whether live code avoids importing `tests.*`, `src/autopulse/adapters.py`, `providers.py`, or `replayer.py`.
- Whether VIN reads are blocked and `--vin-hashed` is mandatory.
- Whether every outgoing request passes through `command_filter()` before transmission.
- Whether only the six initial ICE Mode 01 PIDs are allowed.
- Whether max 1 Hz cadence is enforced in code.
- Whether `vehicle_speed > 0` is a safety abort.
- Whether sample/duration limits prevent unlimited capture.
- Whether adapter exception text, raw VINs, and raw payload bytes are excluded from logs and JSONL.
- Whether CLI preflight and dry-run behavior are sufficient.
- Whether tests are strong enough to support merge.
- Whether actual vehicle connection is still no-go or can become conditionally go after merge.

Return:

1. Verdict: PASS, CONDITIONAL PASS, or FAIL.
2. Blockers with file/function references.
3. Non-blocking follow-ups.
4. Missing tests.
5. Merge recommendation.
6. Separate real-vehicle go/no-go recommendation.

## Implemented Files

### `src/autopulse/live/adapter.py`

```python
"""Narrow live OBD-II adapter boundary for stationary smoke capture.

LIVE VEHICLE CODE: every outgoing request must pass the read-only guard before
an adapter library can transmit anything to the vehicle.
"""

from __future__ import annotations

from typing import Any

from autopulse.data.validator import command_filter


LIVE_ALLOWED_PIDS = frozenset({0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D})
J1979_CURRENT_DATA_SERVICE = 0x01


class LiveAdapterError(RuntimeError):
    """Raised for live adapter setup or query failures."""


class PIDNotAllowedError(ValueError):
    """Raised when a caller attempts to query a PID outside the allowlist."""


class LiveOBDAdapter:
    """Small wrapper around python-obd for read-only ICE Mode 01 queries."""

    _PID_COMMAND_NAMES = {
        0x04: "ENGINE_LOAD",
        0x05: "COOLANT_TEMP",
        0x06: "SHORT_FUEL_TRIM_1",
        0x07: "LONG_FUEL_TRIM_1",
        0x0C: "RPM",
        0x0D: "SPEED",
    }

    def __init__(self, port: str, *, obd_module: Any | None = None) -> None:
        self.port = port
        self._obd = obd_module
        self._connection: Any | None = None

    def connect(self) -> None:
        if self._obd is None:
            try:
                import obd as obd_module  # type: ignore[import-not-found]
            except ImportError as exc:
                raise LiveAdapterError(
                    "python-obd is required for live smoke capture."
                ) from exc
            self._obd = obd_module

        self._connection = self._obd.OBD(self.port, fast=False)
        if hasattr(self._connection, "is_connected") and not self._connection.is_connected():
            raise LiveAdapterError("adapter did not connect")

    def disconnect(self) -> None:
        if self._connection is not None and hasattr(self._connection, "close"):
            self._connection.close()
        self._connection = None

    def get_protocol_name(self) -> str:
        if self._connection is None:
            raise LiveAdapterError("adapter is not connected")
        protocol = getattr(self._connection, "protocol_name", None)
        if callable(protocol):
            return str(protocol())
        if protocol is not None:
            return str(protocol)
        return "SAE_J1979"

    def query_pid(self, pid: int) -> float | int:
        self.validate_outgoing_request(J1979_CURRENT_DATA_SERVICE, pid)
        if self._connection is None or self._obd is None:
            raise LiveAdapterError("adapter is not connected")

        command = self._command_for_pid(pid)
        response = self._connection.query(command)
        if getattr(response, "is_null", lambda: False)():
            raise LiveAdapterError("adapter returned no data")
        value = getattr(response, "value", None)
        if value is None:
            raise LiveAdapterError("adapter returned no value")
        magnitude = getattr(value, "magnitude", value)
        if not isinstance(magnitude, (int, float)) or isinstance(magnitude, bool):
            raise LiveAdapterError("adapter returned non-numeric value")
        return magnitude

    def validate_outgoing_request(self, service_id: int, pid: int | None = None) -> None:
        command_filter(service_id)
        if service_id != J1979_CURRENT_DATA_SERVICE:
            raise PIDNotAllowedError("only SAE J1979 Mode 01 current-data reads are allowed")
        if pid not in LIVE_ALLOWED_PIDS:
            raise PIDNotAllowedError("PID is not in the live smoke allowlist")

    def _command_for_pid(self, pid: int) -> Any:
        name = self._PID_COMMAND_NAMES[pid]
        commands = getattr(self._obd, "commands", None)
        command = getattr(commands, name, None)
        if command is None:
            raise LiveAdapterError("python-obd command is unavailable")
        return command
```

### `src/autopulse/live/harness.py`

```python
OK_EXIT = 0
CONFIG_ERROR_EXIT = 1
SAFETY_ABORT_EXIT = 2
ADAPTER_FAILURE_EXIT = 3
MIN_POLL_INTERVAL_SECONDS = 1.0

@dataclass(frozen=True)
class SmokeHarnessConfig:
    adapter_port: str
    vin_hashed: str
    output_path: Path
    max_samples: int | None = None
    max_duration_seconds: float | None = None
    confirmed_stationary: bool = False
    dry_run: bool = False

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
    if not config.output_path.parent.exists():
        raise FileNotFoundError("output_path parent directory does not exist.")
    if not config.dry_run and not config.confirmed_stationary:
        raise ValueError("stationary preflight confirmation is required.")
```

Core loop excerpt:

```python
def run_smoke_capture(...):
    try:
        validate_config(config)
    except Exception as exc:
        log_event(logger, logging.ERROR, "live_smoke_config_rejected",
                  error_type=type(exc).__name__)
        return SmokeHarnessSummary(ok=False, exit_code=CONFIG_ERROR_EXIT)

    if config.dry_run:
        log_event(logger, logging.INFO, "live_smoke_dry_run_validated")
        return SmokeHarnessSummary(ok=True, exit_code=OK_EXIT, dry_run=True)

    try:
        adapter.connect()
    except Exception as exc:
        log_event(logger, logging.ERROR, "adapter_open_failed",
                  error_type=type(exc).__name__)
        return SmokeHarnessSummary(ok=False, exit_code=ADAPTER_FAILURE_EXIT,
                                   adapter_failure=True)

    ...
    with config.output_path.open("w", encoding="utf-8") as output:
        while _should_continue(...):
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
                    log_event(logger, logging.ERROR,
                              "motion_detected_during_stationary_capture",
                              vehicle_speed=frame["vehicle_speed"])
                    enforce_sleep = False
                    return summary
                output.write(json.dumps(frame, allow_nan=False, sort_keys=True) + "\n")
                output.flush()
                summary.accepted_frames += 1
            except KeyboardInterrupt:
                summary.interrupted = True
                enforce_sleep = False
                return summary
            except (SecurityViolationRedLine, CommandBlockedException) as exc:
                summary.ok = False
                summary.exit_code = SAFETY_ABORT_EXIT
                summary.safety_abort = True
                log_event(logger, logging.ERROR, "live_smoke_security_abort",
                          error_type=type(exc).__name__)
                enforce_sleep = False
                return summary
            except (ValidationError, ValueError, TypeError) as exc:
                summary.rejected_frames += 1
                log_event(logger, logging.WARNING, "live_smoke_frame_rejected",
                          row_index=summary.total_samples,
                          error_type=type(exc).__name__)
            except Exception as exc:
                summary.ok = False
                summary.exit_code = ADAPTER_FAILURE_EXIT
                summary.adapter_failure = True
                log_event(logger, logging.ERROR, "adapter_fetch_error",
                          error_type=type(exc).__name__)
                enforce_sleep = False
                return summary
            finally:
                if enforce_sleep:
                    _enforce_cadence(cycle_start, monotonic, sleep)
```

### `src/autopulse/live/cli.py`

```python
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
```

### Operator Checklist

`docs/operator-checklists/real-vehicle-smoke-harness.md` was added. It requires stationary setup, explicit adapter/port, precomputed `vin_hashed`, explicit output path, finite limits, `--confirmed-stationary`, dry-run first, and stop conditions.

## Tests Added

New tests live under `tests/live/`:

- `test_smoke_harness_cli.py`
- `test_smoke_harness_capture.py`
- `test_smoke_harness_safety.py`
- `test_smoke_harness_security.py`
- `fakes.py`
- `conftest.py`

Highlights:

- dry-run validates without opening adapter;
- malformed `vin_hashed` rejected before adapter open;
- finite limits required;
- runtime log path traversal rejected before opening file;
- valid capture writes replay-compatible JSONL;
- invalid frames are rejected and not written;
- cadence enforces one-second minimum;
- motion abort disconnects and returns safety exit code;
- adapter exception strings with raw VIN/payload do not reach logs;
- write-capable services are blocked before transmission;
- PID allowlist is exact;
- live package does not import `tests.*`.

## Current Go/No-Go

Codex recommendation remains **No-Go for actual vehicle until Claude completes this implementation audit**.
