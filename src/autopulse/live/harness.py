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


__all__ = [
    "ADAPTER_FAILURE_EXIT",
    "CONFIG_ERROR_EXIT",
    "MIN_POLL_INTERVAL_SECONDS",
    "OK_EXIT",
    "SAFETY_ABORT_EXIT",
    "SmokeAdapter",
    "SmokeHarnessConfig",
    "SmokeHarnessSummary",
    "run_smoke_capture",
    "validate_config",
]
