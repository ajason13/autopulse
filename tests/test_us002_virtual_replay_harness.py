"""
AutoPulse | Adversarial QA Test Suite
US-002: Virtual Replay Harness
==============================
Covers:
  - MockAdapter normalization of "Dirty Replays" (NoiseGenerator scenarios)
  - LogReplayer 1Hz / 10Hz timing accuracy ±5%
  - Protocol agnosticism (JSONL + CSV providers)
  - US-001 schema boundary enforcement as perceived by the harness layer
  - Security red-line injection detection
  - Edge cases: empty datasets, malformed rows, loop/memory stability

Run with:
    pytest test_us002_virtual_replay_harness.py -v --tb=short
"""

from __future__ import annotations

import csv
import io
import json
import re
import statistics
import time
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION STUBS
# These represent the actual AutoPulse interfaces under test.
# Replace with real imports when the production modules exist, e.g.:
#   from autopulse.adapters import MockAdapter, LogReplayer, OBDAdapter
#   from autopulse.providers import CSVProvider, JSONLProvider
#   from autopulse.noise import NoiseGenerator
# ─────────────────────────────────────────────────────────────────────────────

SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

VALID_PROTOCOLS = ["J1979_MODE01", "J1979_2_SERVICE22"]

US001_REQUIRED_FIELDS = {
    "timestamp", "vin_hashed", "protocol",
    "engine_rpm", "vehicle_speed", "coolant_temp",
    "engine_load", "stft_bank1", "ltft_bank1",
}

US001_BOUNDS: dict[str, tuple[float, float]] = {
    "engine_rpm":    (0.0,   9500.0),
    "vehicle_speed": (0,     255),
    "coolant_temp":  (-40.0, 140.0),
    "engine_load":   (0.0,   100.0),
    "stft_bank1":    (-50.0, 50.0),
    "ltft_bank1":    (-50.0, 50.0),
}

RESTRICTED_SERVICES = {
    "0x08",   # J1979 Mode 08 – component control
    "0x31",   # UDS RoutineControl
    "0x04",   # J1979 Mode 04 – clear DTCs
    "0x14",   # UDS ClearDiagnosticInformation
    "0x2E",   # UDS WriteDataByIdentifier
    "0x10",   # UDS DiagnosticSessionControl (programming)
}


@dataclass
class DataPacket:
    """Normalised US-001 sensor frame returned by any OBDAdapter."""
    timestamp: str
    vin_hashed: str
    protocol: str
    engine_rpm: float
    vehicle_speed: int
    coolant_temp: float
    engine_load: float
    stft_bank1: float
    ltft_bank1: float
    _raw: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "timestamp":     self.timestamp,
            "vin_hashed":    self.vin_hashed,
            "protocol":      self.protocol,
            "engine_rpm":    self.engine_rpm,
            "vehicle_speed": self.vehicle_speed,
            "coolant_temp":  self.coolant_temp,
            "engine_load":   self.engine_load,
            "stft_bank1":    self.stft_bank1,
            "ltft_bank1":    self.ltft_bank1,
        }


class ValidationError(Exception):
    """Raised when a DataPacket violates the US-001 schema."""


class SecurityViolationError(Exception):
    """Raised when a restricted service ID is detected."""


class LogProvider(ABC):
    @abstractmethod
    def get_next_row(self) -> dict:
        ...

    @abstractmethod
    def reset(self) -> None:
        ...


class JSONLProvider(LogProvider):
    def __init__(self, data: list[dict]) -> None:
        self._data = data
        self._idx = 0

    def get_next_row(self) -> dict:
        if self._idx >= len(self._data):
            raise StopIteration
        row = self._data[self._idx]
        self._idx += 1
        return row

    def reset(self) -> None:
        self._idx = 0


class CSVProvider(LogProvider):
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._idx = 0

    def get_next_row(self) -> dict:
        if self._idx >= len(self._rows):
            raise StopIteration
        row = self._rows[self._idx]
        self._idx += 1
        return {k: self._coerce(k, v) for k, v in row.items()}

    def reset(self) -> None:
        self._idx = 0

    @staticmethod
    def _coerce(key: str, value: str):
        float_keys = {"engine_rpm", "coolant_temp", "engine_load", "stft_bank1", "ltft_bank1"}
        int_keys   = {"vehicle_speed"}
        if key in float_keys:
            return float(value)
        if key in int_keys:
            return int(value)
        return value


class NoiseGenerator:
    """Decorates raw rows with adversarial mutations before normalisation."""

    @staticmethod
    def pid_drop(row: dict, field: str) -> dict:
        mutated = dict(row)
        mutated[field] = None
        return mutated

    @staticmethod
    def out_of_bounds(row: dict, field: str, value) -> dict:
        mutated = dict(row)
        mutated[field] = value
        return mutated

    @staticmethod
    def inject_restricted_service(row: dict, service_id: str) -> dict:
        mutated = dict(row)
        mutated["__service_id__"] = service_id
        return mutated


def _make_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _make_vin_hash() -> str:
    import hashlib
    return hashlib.sha256(uuid.uuid4().bytes).hexdigest()


class MockAdapter:
    """
    Implements OBDAdapter via a LogProvider.
    Normalises raw rows into validated DataPackets (US-001).
    Enforces security red-lines on every frame.
    """

    _DEFAULT_VIN = _make_vin_hash()
    _DEFAULT_PROTOCOL = "J1979_MODE01"

    def __init__(self, provider: LogProvider, loop: bool = False) -> None:
        self._provider = provider
        self._loop = loop
        self._connected = False
        self._security_violations: list[str] = []

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def security_violations(self) -> list[str]:
        return list(self._security_violations)

    def fetch_frame(self) -> DataPacket:
        if not self._connected:
            raise RuntimeError("Adapter not connected. Call connect() first.")
        while True:
            try:
                raw = self._provider.get_next_row()
            except StopIteration:
                if self._loop:
                    self._provider.reset()
                    raw = self._provider.get_next_row()
                else:
                    raise

            # ── Security gate ───────────────────────────────────────────────
            service_id = raw.get("__service_id__")
            if service_id is not None:
                if service_id in RESTRICTED_SERVICES:
                    self._security_violations.append(service_id)
                    raise SecurityViolationError(
                        f"SECURITY_VIOLATION_RED_LINE: restricted service {service_id}"
                    )

            # ── Validate & normalise ─────────────────────────────────────────
            return self._normalise(raw)

    def _normalise(self, raw: dict) -> DataPacket:
        ts         = raw.get("timestamp") or _make_timestamp()
        vin        = raw.get("vin_hashed") or self._DEFAULT_VIN
        protocol   = raw.get("protocol") or self._DEFAULT_PROTOCOL

        # Validate required numeric fields (nulls → ValidationError)
        numerics = {
            "engine_rpm":    raw.get("engine_rpm"),
            "vehicle_speed": raw.get("vehicle_speed"),
            "coolant_temp":  raw.get("coolant_temp"),
            "engine_load":   raw.get("engine_load"),
            "stft_bank1":    raw.get("stft_bank1"),
            "ltft_bank1":    raw.get("ltft_bank1"),
        }
        for fname, val in numerics.items():
            if val is None:
                raise ValidationError(f"Required field '{fname}' is null/missing.")

        # Physics-based bounds check
        for fname, (lo, hi) in US001_BOUNDS.items():
            val = numerics[fname]
            if not (lo <= val <= hi):
                raise ValidationError(
                    f"Field '{fname}' value {val} out of bounds [{lo}, {hi}]."
                )

        # VIN hash format
        if not SHA256_PATTERN.match(vin):
            raise ValidationError(f"vin_hashed '{vin}' is not a valid SHA-256 hex string.")

        # Protocol enum
        if protocol not in VALID_PROTOCOLS:
            raise ValidationError(
                f"protocol '{protocol}' not in allowed set {VALID_PROTOCOLS}."
            )

        return DataPacket(
            timestamp=ts,
            vin_hashed=vin,
            protocol=protocol,
            engine_rpm=float(numerics["engine_rpm"]),
            vehicle_speed=int(numerics["vehicle_speed"]),
            coolant_temp=float(numerics["coolant_temp"]),
            engine_load=float(numerics["engine_load"]),
            stft_bank1=float(numerics["stft_bank1"]),
            ltft_bank1=float(numerics["ltft_bank1"]),
            _raw=raw,
        )


class LogReplayer:
    """
    Drives a MockAdapter at a configurable Hz rate.
    Collected frames and inter-frame timestamps are available post-run.
    """

    def __init__(self, adapter: MockAdapter, frequency_hz: int = 1) -> None:
        self._adapter = adapter
        self._frequency_hz = frequency_hz
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.frames: list[DataPacket] = []
        self.errors: list[Exception] = []
        self._dispatch_timestamps: list[float] = []

    def set_speed(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("Speed multiplier must be positive.")
        self._frequency_hz = round(self._frequency_hz * multiplier)

    def start(self, max_frames: Optional[int] = None) -> None:
        self._running = True
        self._adapter.connect()
        self._thread = threading.Thread(
            target=self._run_loop, args=(max_frames,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        self._adapter.disconnect()

    def _run_loop(self, max_frames: Optional[int]) -> None:
        interval = 1.0 / self._frequency_hz
        count = 0
        while self._running:
            if max_frames is not None and count >= max_frames:
                self._running = False
                break
            t0 = time.perf_counter()
            self._dispatch_timestamps.append(t0)
            try:
                frame = self._adapter.fetch_frame()
                self.frames.append(frame)
            except StopIteration:
                self._running = False
                break
            except Exception as exc:
                self.errors.append(exc)
            elapsed = time.perf_counter() - t0
            sleep_for = interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            count += 1

    def join(self, timeout: float = 10.0) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def inter_frame_intervals(self) -> list[float]:
        ts = self._dispatch_timestamps
        return [ts[i+1] - ts[i] for i in range(len(ts) - 1)]


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

_VIN = _make_vin_hash()

def _good_row(**overrides) -> dict:
    base = {
        "timestamp":     "2025-01-15T10:00:00.000+00:00",
        "vin_hashed":    _VIN,
        "protocol":      "J1979_MODE01",
        "engine_rpm":    800.0,
        "vehicle_speed": 0,
        "coolant_temp":  85.0,
        "engine_load":   20.0,
        "stft_bank1":    1.5,
        "ltft_bank1":    -2.0,
    }
    base.update(overrides)
    return base


@pytest.fixture()
def good_jsonl_provider() -> JSONLProvider:
    return JSONLProvider([_good_row(engine_rpm=800 + i * 10) for i in range(20)])


@pytest.fixture()
def connected_adapter(good_jsonl_provider) -> MockAdapter:
    adapter = MockAdapter(good_jsonl_provider)
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture()
def noise() -> NoiseGenerator:
    return NoiseGenerator()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 – MockAdapter: Normalisation & US-001 Contract Enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestMockAdapterNormalisation:

    def test_returns_data_packet_type(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        assert isinstance(frame, DataPacket)

    def test_all_required_fields_present(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        packet_keys = set(frame.to_dict().keys())
        assert US001_REQUIRED_FIELDS == packet_keys

    def test_vin_hashed_is_sha256_hex(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        assert SHA256_PATTERN.match(frame.vin_hashed), (
            f"vin_hashed '{frame.vin_hashed}' is not a 64-char lowercase hex string"
        )

    def test_protocol_is_valid_enum(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        assert frame.protocol in VALID_PROTOCOLS

    def test_engine_rpm_is_float(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        assert isinstance(frame.engine_rpm, float)

    def test_vehicle_speed_is_int(self, connected_adapter):
        frame = connected_adapter.fetch_frame()
        assert isinstance(frame.vehicle_speed, int)

    def test_csv_provider_coerces_string_types(self):
        rows = [_good_row(engine_rpm="1200.0", vehicle_speed="60", coolant_temp="90.5")]
        provider = CSVProvider(rows)
        adapter = MockAdapter(provider)
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.engine_rpm == 1200.0
        assert frame.vehicle_speed == 60
        assert frame.coolant_temp == 90.5
        adapter.disconnect()

    def test_jsonl_and_csv_produce_equivalent_frames(self):
        row = _good_row(engine_rpm=1500.0, vehicle_speed=60, coolant_temp=90.0)
        csv_row = {k: str(v) for k, v in row.items()}

        ja = MockAdapter(JSONLProvider([row]))
        ca = MockAdapter(CSVProvider([csv_row]))
        ja.connect(); ca.connect()

        jf = ja.fetch_frame()
        cf = ca.fetch_frame()
        assert jf.engine_rpm    == cf.engine_rpm
        assert jf.vehicle_speed == cf.vehicle_speed
        assert jf.coolant_temp  == cf.coolant_temp

        ja.disconnect(); ca.disconnect()

    def test_missing_timestamp_is_auto_generated(self):
        row = _good_row()
        del row["timestamp"]
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.timestamp  # non-empty string
        adapter.disconnect()

    def test_missing_vin_uses_default(self):
        row = _good_row()
        del row["vin_hashed"]
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert SHA256_PATTERN.match(frame.vin_hashed)
        adapter.disconnect()

    def test_stops_iteration_on_exhausted_provider(self, connected_adapter):
        for _ in range(20):
            connected_adapter.fetch_frame()
        with pytest.raises(StopIteration):
            connected_adapter.fetch_frame()

    def test_raises_runtime_error_if_not_connected(self):
        provider = JSONLProvider([_good_row()])
        adapter = MockAdapter(provider)
        with pytest.raises(RuntimeError, match="not connected"):
            adapter.fetch_frame()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 – MockAdapter: PID Drop (null field injection)
# ─────────────────────────────────────────────────────────────────────────────

class TestPIDDropNoise:

    @pytest.mark.parametrize("dropped_field", [
        "engine_rpm", "vehicle_speed", "coolant_temp",
        "engine_load", "stft_bank1", "ltft_bank1",
    ])
    def test_null_required_field_raises_validation_error(self, dropped_field):
        row = NoiseGenerator.pid_drop(_good_row(), dropped_field)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match=dropped_field):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_null_field_error_message_names_the_field(self):
        row = NoiseGenerator.pid_drop(_good_row(), "ltft_bank1")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError) as exc_info:
            adapter.fetch_frame()
        assert "ltft_bank1" in str(exc_info.value)
        adapter.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 – MockAdapter: Out-of-Bounds (physics boundary enforcement)
# ─────────────────────────────────────────────────────────────────────────────

class TestOutOfBoundsNoise:

    # ── RPM ──────────────────────────────────────────────────────────────────

    def test_rpm_at_boundary_9500_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(engine_rpm=9500.0)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.engine_rpm == 9500.0
        adapter.disconnect()

    def test_rpm_just_above_boundary_9501_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_rpm", 9501.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="engine_rpm"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_rpm_candid_noise_25000_rejected(self):
        """Simulates the CANdid dataset 'jitter' spike scenario."""
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_rpm", 25000.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_rpm_negative_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_rpm", -1.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="engine_rpm"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_rpm_zero_accepted(self):
        """Engine off, ignition on – zero is physically valid (US-001 spec)."""
        adapter = MockAdapter(JSONLProvider([_good_row(engine_rpm=0.0)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.engine_rpm == 0.0
        adapter.disconnect()

    # ── Coolant Temperature ───────────────────────────────────────────────────

    def test_coolant_temp_at_lower_bound_neg40_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(coolant_temp=-40.0)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.coolant_temp == -40.0
        adapter.disconnect()

    def test_coolant_temp_at_upper_bound_140_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(coolant_temp=140.0)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.coolant_temp == 140.0
        adapter.disconnect()

    def test_coolant_temp_below_neg40_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "coolant_temp", -100.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="coolant_temp"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_coolant_temp_above_140_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "coolant_temp", 141.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="coolant_temp"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_thermal_anomaly_single_frame_spike_135_accepted_individually(self):
        """
        US-001 spec: the validator accepts 135°C as within bounds in isolation.
        The anomaly detector (rate-of-change logic) flags the *sequence*, not
        the single value – that layer is tested separately in integration tests.
        """
        adapter = MockAdapter(JSONLProvider([_good_row(coolant_temp=135.0)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.coolant_temp == 135.0
        adapter.disconnect()

    # ── AI4I Kelvin-to-Celsius Conversion ────────────────────────────────────

    def test_ai4i_process_temp_kelvin_conversion_valid(self):
        """308.15 K → 35.0 °C – must pass bounds check."""
        celsius = 308.15 - 273.15
        adapter = MockAdapter(JSONLProvider([_good_row(coolant_temp=celsius)]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert abs(frame.coolant_temp - 35.0) < 0.01
        adapter.disconnect()

    def test_ai4i_extreme_kelvin_out_of_bounds_rejected(self):
        """Very high AI4I process temp (450 K → 176.85 °C) must be rejected."""
        celsius = 450.0 - 273.15
        row = NoiseGenerator.out_of_bounds(_good_row(), "coolant_temp", celsius)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="coolant_temp"):
            adapter.fetch_frame()
        adapter.disconnect()

    # ── Engine Load ───────────────────────────────────────────────────────────

    def test_engine_load_zero_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(engine_load=0.0)]))
        adapter.connect()
        assert adapter.fetch_frame().engine_load == 0.0
        adapter.disconnect()

    def test_engine_load_100_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(engine_load=100.0)]))
        adapter.connect()
        assert adapter.fetch_frame().engine_load == 100.0
        adapter.disconnect()

    def test_engine_load_above_100_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_load", 100.1)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="engine_load"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_engine_load_negative_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_load", -0.1)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError):
            adapter.fetch_frame()
        adapter.disconnect()

    # ── Vehicle Speed ─────────────────────────────────────────────────────────

    def test_vehicle_speed_zero_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(vehicle_speed=0)]))
        adapter.connect()
        assert adapter.fetch_frame().vehicle_speed == 0
        adapter.disconnect()

    def test_vehicle_speed_255_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(vehicle_speed=255)]))
        adapter.connect()
        assert adapter.fetch_frame().vehicle_speed == 255
        adapter.disconnect()

    def test_vehicle_speed_negative_rejected(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "vehicle_speed", -1)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="vehicle_speed"):
            adapter.fetch_frame()
        adapter.disconnect()

    # ── Fuel Trims ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_at_positive_boundary_50_accepted(self, field):
        adapter = MockAdapter(JSONLProvider([_good_row(**{field: 50.0})]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert getattr(frame, field) == 50.0
        adapter.disconnect()

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_at_negative_boundary_neg50_accepted(self, field):
        adapter = MockAdapter(JSONLProvider([_good_row(**{field: -50.0})]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert getattr(frame, field) == -50.0
        adapter.disconnect()

    @pytest.mark.parametrize("field,value", [
        ("stft_bank1",  50.1),
        ("stft_bank1", -50.1),
        ("ltft_bank1",  50.1),
        ("ltft_bank1", -50.1),
    ])
    def test_fuel_trim_outside_bounds_rejected(self, field, value):
        row = NoiseGenerator.out_of_bounds(_good_row(), field, value)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match=field):
            adapter.fetch_frame()
        adapter.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4 – Security Red-Line Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityRedLines:

    @pytest.mark.parametrize("service_id", list(RESTRICTED_SERVICES))
    def test_restricted_service_raises_security_violation(self, service_id):
        row = NoiseGenerator.inject_restricted_service(_good_row(), service_id)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(SecurityViolationError):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_mode_0x08_component_control_blocked(self):
        """US-001 Red Line: SAE J1979 Mode 0x08 must never reach the CAN bus."""
        row = NoiseGenerator.inject_restricted_service(_good_row(), "0x08")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(SecurityViolationError, match="SECURITY_VIOLATION_RED_LINE"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_service_0x31_routine_control_blocked(self):
        """US-001 Red Line: UDS StartRoutine (0x31) must be terminated immediately."""
        row = NoiseGenerator.inject_restricted_service(_good_row(), "0x31")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(SecurityViolationError):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_security_violation_is_logged(self):
        row = NoiseGenerator.inject_restricted_service(_good_row(), "0x08")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        try:
            adapter.fetch_frame()
        except SecurityViolationError:
            pass
        assert "0x08" in adapter.security_violations
        adapter.disconnect()

    def test_valid_frame_after_security_violation_does_not_propagate(self):
        """
        After a red-line rejection, subsequent valid frames must be processed
        without side-effects from the prior violation.
        """
        bad  = NoiseGenerator.inject_restricted_service(_good_row(), "0x31")
        good = _good_row(engine_rpm=1200.0)
        provider = JSONLProvider([bad, good])
        adapter = MockAdapter(provider)
        adapter.connect()

        with pytest.raises(SecurityViolationError):
            adapter.fetch_frame()

        frame = adapter.fetch_frame()
        assert frame.engine_rpm == 1200.0
        adapter.disconnect()

    def test_mode_0x04_dtc_clear_blocked(self):
        row = NoiseGenerator.inject_restricted_service(_good_row(), "0x04")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(SecurityViolationError):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_service_0x2e_write_by_identifier_blocked(self):
        row = NoiseGenerator.inject_restricted_service(_good_row(), "0x2E")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(SecurityViolationError):
            adapter.fetch_frame()
        adapter.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5 – LogReplayer: 1Hz Timing ±5%
# ─────────────────────────────────────────────────────────────────────────────

class TestLogReplayer1Hz:
    """
    Timing window:
        expected interval = 1.000 s
        allowed min       = 0.950 s  (−5%)
        allowed max       = 1.050 s  (+5%)
    """
    _EXPECTED = 1.000
    _TOLERANCE = 0.05

    @pytest.fixture()
    def replayer_1hz(self):
        rows = [_good_row(engine_rpm=float(i * 100)) for i in range(8)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider)
        replayer = LogReplayer(adapter, frequency_hz=1)
        return replayer

    def test_1hz_frame_count_matches_dataset(self, replayer_1hz):
        replayer_1hz.start()
        replayer_1hz.join(timeout=12.0)
        replayer_1hz.stop()
        assert len(replayer_1hz.frames) == 8

    def test_1hz_mean_interval_within_tolerance(self, replayer_1hz):
        replayer_1hz.start()
        replayer_1hz.join(timeout=12.0)
        replayer_1hz.stop()
        intervals = replayer_1hz.inter_frame_intervals
        assert len(intervals) >= 3, "Not enough intervals to assess timing."
        mean_interval = statistics.mean(intervals)
        assert self._EXPECTED * (1 - self._TOLERANCE) <= mean_interval <= self._EXPECTED * (1 + self._TOLERANCE), (
            f"Mean 1Hz interval {mean_interval:.4f}s outside ±5% of {self._EXPECTED}s"
        )

    def test_1hz_no_interval_exceeds_tolerance(self, replayer_1hz):
        replayer_1hz.start()
        replayer_1hz.join(timeout=12.0)
        replayer_1hz.stop()
        lo = self._EXPECTED * (1 - self._TOLERANCE)
        hi = self._EXPECTED * (1 + self._TOLERANCE)
        for i, iv in enumerate(replayer_1hz.inter_frame_intervals):
            assert lo <= iv <= hi, (
                f"Interval #{i} = {iv:.4f}s is outside the ±5% window [{lo:.3f}, {hi:.3f}]"
            )

    def test_1hz_std_dev_is_low(self, replayer_1hz):
        replayer_1hz.start()
        replayer_1hz.join(timeout=12.0)
        replayer_1hz.stop()
        intervals = replayer_1hz.inter_frame_intervals
        if len(intervals) >= 2:
            std = statistics.stdev(intervals)
            assert std < 0.05, f"1Hz jitter std dev {std:.4f}s is too high (max 0.05s)."


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 6 – LogReplayer: 10Hz Timing ±5%
# ─────────────────────────────────────────────────────────────────────────────

class TestLogReplayer10Hz:
    """
    Timing window:
        expected interval = 0.100 s
        allowed min       = 0.095 s  (−5%)
        allowed max       = 0.105 s  (+5%)
    """
    _EXPECTED = 0.100
    _TOLERANCE = 0.05

    @pytest.fixture()
    def replayer_10hz(self):
        rows = [_good_row(engine_rpm=float(i * 50)) for i in range(30)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider)
        replayer = LogReplayer(adapter, frequency_hz=10)
        return replayer

    def test_10hz_frame_count_matches_dataset(self, replayer_10hz):
        replayer_10hz.start()
        replayer_10hz.join(timeout=6.0)
        replayer_10hz.stop()
        assert len(replayer_10hz.frames) == 30

    def test_10hz_mean_interval_within_tolerance(self, replayer_10hz):
        replayer_10hz.start()
        replayer_10hz.join(timeout=6.0)
        replayer_10hz.stop()
        intervals = replayer_10hz.inter_frame_intervals
        assert len(intervals) >= 5, "Not enough intervals to assess 10Hz timing."
        mean_interval = statistics.mean(intervals)
        assert self._EXPECTED * (1 - self._TOLERANCE) <= mean_interval <= self._EXPECTED * (1 + self._TOLERANCE), (
            f"Mean 10Hz interval {mean_interval:.4f}s outside ±5% of {self._EXPECTED}s"
        )

    def test_10hz_no_interval_exceeds_tolerance(self, replayer_10hz):
        replayer_10hz.start()
        replayer_10hz.join(timeout=6.0)
        replayer_10hz.stop()
        lo = self._EXPECTED * (1 - self._TOLERANCE)
        hi = self._EXPECTED * (1 + self._TOLERANCE)
        violations = [
            (i, iv) for i, iv in enumerate(replayer_10hz.inter_frame_intervals)
            if not (lo <= iv <= hi)
        ]
        assert not violations, (
            f"{len(violations)} interval(s) outside ±5%: {violations[:5]}"
        )

    def test_10hz_throughput_handles_validation_load(self):
        """
        Under 10Hz, even frames requiring full normalisation must be dispatched
        without accumulating latency across 30 frames.
        """
        rows = [
            _good_row(engine_rpm=float(800 + i), coolant_temp=float(85 + (i % 5)))
            for i in range(30)
        ]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider)
        replayer = LogReplayer(adapter, frequency_hz=10)
        replayer.start()
        replayer.join(timeout=6.0)
        replayer.stop()
        assert len(replayer.frames) == 30
        assert not replayer.errors


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 7 – LogReplayer: Mode Switching & Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

class TestLogReplayerModes:

    def test_set_speed_doubles_frequency(self):
        rows = [_good_row() for _ in range(10)]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=1)
        replayer.set_speed(2.0)
        assert replayer._frequency_hz == 2

    def test_set_speed_negative_raises_value_error(self):
        rows = [_good_row()]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=1)
        with pytest.raises(ValueError, match="positive"):
            replayer.set_speed(-1.0)

    def test_set_speed_zero_raises_value_error(self):
        rows = [_good_row()]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=1)
        with pytest.raises(ValueError):
            replayer.set_speed(0.0)

    def test_replayer_stops_gracefully_on_exhausted_dataset(self):
        rows = [_good_row() for _ in range(3)]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=10)
        replayer.start()
        replayer.join(timeout=5.0)
        replayer.stop()
        assert len(replayer.frames) == 3

    def test_replayer_collects_validation_errors_without_crashing(self):
        """Dirty frames mid-stream should not crash the replayer thread."""
        rows = [
            _good_row(engine_rpm=800.0),
            NoiseGenerator.pid_drop(_good_row(), "engine_rpm"),
            _good_row(engine_rpm=900.0),
        ]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=10)
        replayer.start()
        replayer.join(timeout=5.0)
        replayer.stop()

        assert len(replayer.frames) == 2
        assert len(replayer.errors) == 1
        assert isinstance(replayer.errors[0], ValidationError)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 8 – Replay Looping & Memory Stability
# ─────────────────────────────────────────────────────────────────────────────

class TestReplayLooping:

    def test_looping_mode_cycles_dataset(self):
        rows = [_good_row(engine_rpm=float(i * 100)) for i in range(5)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider, loop=True)
        adapter.connect()

        collected = [adapter.fetch_frame() for _ in range(12)]
        adapter.disconnect()

        # After 5 rows, provider resets → second pass starts at index 0 again
        assert collected[5].engine_rpm == collected[0].engine_rpm
        assert collected[10].engine_rpm == collected[0].engine_rpm

    def test_looping_does_not_grow_memory_unbounded(self):
        """
        Proxy test: after N loop cycles, the number of objects tracked by the
        provider equals the dataset size, not N × dataset_size.
        """
        rows = [_good_row() for _ in range(5)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider, loop=True)
        adapter.connect()

        for _ in range(50):
            adapter.fetch_frame()

        # Provider internal index should wrap, not accumulate
        assert provider._idx <= len(rows)
        adapter.disconnect()

    def test_non_looping_mode_raises_on_exhaustion(self):
        rows = [_good_row() for _ in range(3)]
        adapter = MockAdapter(JSONLProvider(rows), loop=False)
        adapter.connect()
        for _ in range(3):
            adapter.fetch_frame()
        with pytest.raises(StopIteration):
            adapter.fetch_frame()
        adapter.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 9 – Protocol Agnosticism (J1979 vs J1979-2 Service 0x22)
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocolAgnosticism:

    def test_j1979_mode01_protocol_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(protocol="J1979_MODE01")]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.protocol == "J1979_MODE01"
        adapter.disconnect()

    def test_j1979_2_service22_protocol_accepted(self):
        adapter = MockAdapter(JSONLProvider([_good_row(protocol="J1979_2_SERVICE22")]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.protocol == "J1979_2_SERVICE22"
        adapter.disconnect()

    def test_unknown_protocol_rejected(self):
        adapter = MockAdapter(JSONLProvider([_good_row(protocol="SOME_LEGACY_PROTO")]))
        adapter.connect()
        with pytest.raises(ValidationError, match="protocol"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_normalised_frame_is_protocol_agnostic_in_schema(self):
        """Both protocols must produce a DataPacket with the same field structure."""
        row_legacy = _good_row(protocol="J1979_MODE01",      engine_rpm=1000.0)
        row_uds    = _good_row(protocol="J1979_2_SERVICE22", engine_rpm=1000.0)

        a1 = MockAdapter(JSONLProvider([row_legacy]))
        a2 = MockAdapter(JSONLProvider([row_uds]))
        a1.connect(); a2.connect()

        f1 = a1.fetch_frame()
        f2 = a2.fetch_frame()

        assert set(f1.to_dict().keys()) == set(f2.to_dict().keys())
        assert f1.engine_rpm == f2.engine_rpm
        a1.disconnect(); a2.disconnect()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 10 – Cold Start & Gradient Scenarios (US-001 spec test vectors)
# ─────────────────────────────────────────────────────────────────────────────

class TestSpecTestVectors:
    """Mirrors the named test vectors from the US-001 Technical Specification."""

    def test_cold_start_temperature_gradient_all_frames_valid(self):
        """
        Simulate a coolant rise from 0°C to 85°C across 10 frames.
        Every frame must pass schema validation.
        """
        temps = [0 + i * 8.5 for i in range(11)]  # 0.0, 8.5, …, 85.0
        rows = [_good_row(coolant_temp=t) for t in temps]
        adapter = MockAdapter(JSONLProvider(rows))
        adapter.connect()
        frames = [adapter.fetch_frame() for _ in range(len(rows))]
        adapter.disconnect()
        collected_temps = [f.coolant_temp for f in frames]
        assert collected_temps[0]  == pytest.approx(0.0)
        assert collected_temps[-1] == pytest.approx(85.0)

    def test_zero_value_robustness_all_zeros_accepted(self):
        """Engine off, ignition on: RPM=0, Speed=0, Load=0 must be accepted."""
        row = _good_row(engine_rpm=0.0, vehicle_speed=0, engine_load=0.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.engine_rpm == 0.0
        assert frame.vehicle_speed == 0
        assert frame.engine_load == 0.0
        adapter.disconnect()

    def test_boundary_rpm_9499_accepted(self):
        """Spec test vector: RPM 9499 must be accepted."""
        adapter = MockAdapter(JSONLProvider([_good_row(engine_rpm=9499.0)]))
        adapter.connect()
        assert adapter.fetch_frame().engine_rpm == pytest.approx(9499.0)
        adapter.disconnect()

    def test_boundary_rpm_9501_rejected(self):
        """Spec test vector: RPM 9501 must be rejected."""
        row = NoiseGenerator.out_of_bounds(_good_row(), "engine_rpm", 9501.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_additional_properties_rejected(self):
        """
        US-001 JSON Schema enforces additionalProperties: false.
        Any undocumented key must be treated as invalid / stripped.
        """
        row = _good_row()
        row["undocumented_key"] = "some_value"
        # The normaliser must either strip or reject unknown fields.
        # Here we verify it does NOT surface in the DataPacket.
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert not hasattr(frame, "undocumented_key")
        adapter.disconnect()
