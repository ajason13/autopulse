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
  - Edge cases: empty datasets, malformed rows, bounded provider indexing

Run with:
    pytest test_us002_virtual_replay_harness.py -v --tb=short
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

import autopulse.virtual_replay as replay_module
from autopulse.virtual_replay import (
    CSVProvider,
    CandidParser,
    DataPacket,
    JSONLProvider,
    LogReplayer,
    MockAdapter,
    NoiseGenerator,
    SecurityViolationError,
)


# Independent expected values for the replay-facing US-001 contract.
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

VALID_PROTOCOLS = ["J1979_MODE01", "J1979_2_SERVICE22"]

US001_REQUIRED_FIELDS = {
    "timestamp", "vin_hashed", "protocol",
    "engine_rpm", "vehicle_speed", "coolant_temp",
    "engine_load", "stft_bank1", "ltft_bank1",
}

RESTRICTED_SERVICES = {
    "0x08",   # J1979 Mode 08 – component control
    "0x31",   # UDS RoutineControl
    "0x04",   # J1979 Mode 04 – clear DTCs
    "0x14",   # UDS ClearDiagnosticInformation
    "0x2E",   # UDS WriteDataByIdentifier
    "0x10",   # UDS DiagnosticSessionControl (programming)
}


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

class DeterministicClock:
    """Thread-safe virtual time for cadence assertions, independent of CI load."""

    def __init__(self) -> None:
        self._value = 0.0
        self._lock = threading.Lock()

    def now(self) -> float:
        with self._lock:
            return self._value

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep duration must be non-negative")
        with self._lock:
            self._value += seconds


@pytest.fixture()
def replay_clock(monkeypatch):
    """Replace only production replay's time dependency, not its scheduler.

    Patching the module binding avoids replacing the process-wide time.sleep
    used by pytest and other threads. The real worker thread still runs.
    """
    clock = DeterministicClock()
    monkeypatch.setattr(
        replay_module,
        "time",
        SimpleNamespace(perf_counter=clock.now, sleep=clock.sleep),
    )
    return clock


_VIN = "a" * 64

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

    @pytest.mark.parametrize("ambient", [-40.0, 0, 22.5, 80.0])
    @pytest.mark.parametrize("provider_type", [JSONLProvider, CSVProvider])
    @pytest.mark.parametrize("protocol,canonical", [
        ("J1979_MODE01", "SAE_J1979"),
        ("J1979_2_SERVICE22", "SAE_J1979-2"),
    ])
    def test_optional_ambient_round_trip(self, ambient, provider_type, protocol, canonical):
        from autopulse.data.validator import validate_frame

        row = _good_row(protocol=protocol, ambient_temp=ambient)
        source = {key: str(value) for key, value in row.items()} if provider_type is CSVProvider else row
        adapter = MockAdapter(provider_type([source]))
        adapter.connect()
        try:
            packet = adapter.fetch_frame()
        finally:
            adapter.disconnect()
        assert packet.ambient_temp == ambient
        assert isinstance(packet.ambient_temp, float)
        assert packet.to_dict() == row
        canonical_row = dict(row, protocol=canonical)
        assert packet.to_schema_dict() == canonical_row
        validate_frame(canonical_row)
        assert json.loads(json.dumps(packet.to_schema_dict(), allow_nan=False)) == canonical_row

    @pytest.mark.parametrize("provider_type", [JSONLProvider, CSVProvider])
    def test_absent_ambient_is_omitted(self, provider_type):
        row = _good_row()
        adapter = MockAdapter(provider_type([row]))
        adapter.connect()
        try:
            packet = adapter.fetch_frame()
        finally:
            adapter.disconnect()
        assert packet.ambient_temp is None
        assert packet.to_dict() == row
        assert "ambient_temp" not in packet.to_schema_dict()

    @pytest.mark.parametrize("ambient", [
        None, True, False, "22.5", "bad", [], {}, -40.001, 80.001,
        float("nan"), float("inf"), float("-inf"),
    ])
    def test_invalid_supplied_ambient_is_rejected(self, ambient):
        adapter = MockAdapter(JSONLProvider([_good_row(ambient_temp=ambient)]))
        adapter.connect()
        try:
            with pytest.raises(ValidationError):
                adapter.fetch_frame()
        finally:
            adapter.disconnect()

    @pytest.mark.parametrize("ambient", ["", "bad", "nan", "inf", "-inf", "-40.001", "80.001"])
    def test_invalid_csv_ambient_is_rejected(self, ambient):
        adapter = MockAdapter(CSVProvider([_good_row(ambient_temp=ambient)]))
        adapter.connect()
        try:
            with pytest.raises((ValueError, ValidationError)):
                adapter.fetch_frame()
        finally:
            adapter.disconnect()

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

    def test_vehicle_speed_float_oob_names_bounds_in_production(self):
        row = NoiseGenerator.out_of_bounds(_good_row(), "vehicle_speed", 256.5)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        with pytest.raises(ValidationError, match="out of bounds"):
            adapter.fetch_frame()
        adapter.disconnect()

    def test_vehicle_speed_integral_float_is_normalized_in_production(self):
        row = _good_row(vehicle_speed=60.0)
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert frame.vehicle_speed == 60
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

    @pytest.mark.parametrize("service_id", [8, 0x31, 49])
    def test_integer_restricted_service_raises_security_violation(
        self,
        service_id,
    ):
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
    def replayer_1hz(self, replay_clock):
        rows = [_good_row(engine_rpm=float(i * 100)) for i in range(8)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider)
        replayer = LogReplayer(
            adapter,
            frequency_hz=1,
        )
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
        assert len(intervals) == 7
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
    def replayer_10hz(self, replay_clock):
        rows = [_good_row(engine_rpm=float(i * 50)) for i in range(30)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider)
        replayer = LogReplayer(
            adapter,
            frequency_hz=10,
        )
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
        assert len(intervals) == 29
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

    def test_production_replay_modules_import_from_source_only_copy(self, tmp_path):
        source_package = Path(__file__).resolve().parents[1] / "src" / "autopulse"
        shutil.copytree(source_package, tmp_path / "autopulse")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import autopulse.replayer, autopulse.noise, autopulse.providers",
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(tmp_path)},
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

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

    def test_set_speed_rounding_to_zero_raises_value_error(self):
        rows = [_good_row()]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=1)
        with pytest.raises(ValueError):
            replayer.set_speed(0.4)

    def test_production_replayer_preserves_frequency_when_drift_rejects_speed(self):
        adapter = MockAdapter(JSONLProvider([]))
        replayer = LogReplayer(adapter, frequency_hz=1, drift=0.75)

        with pytest.raises(ValueError, match="frame interval"):
            replayer.set_speed(2)

        assert replayer._frequency_hz == 1
        replayer.set_speed(1)
        assert replayer._frequency_hz == 1

    def test_drift_equal_to_interval_raises_value_error(self):
        rows = [_good_row()]
        adapter = MockAdapter(JSONLProvider(rows))
        with pytest.raises(ValueError, match="frame interval"):
            LogReplayer(adapter, frequency_hz=10, drift=0.1)

    def test_drift_under_interval_is_allowed_in_production(self):
        rows = [_good_row()]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=10, drift=0.05)
        assert replayer._drift == 0.05

    @pytest.mark.parametrize(
        ("frame_count", "expected_interval_count"),
        [(1, 0), (3, 2)],
    )
    def test_production_replayer_records_intervals_only_between_frames(
        self,
        frame_count,
        expected_interval_count,
    ):
        rows = [_good_row() for _ in range(frame_count)]
        adapter = MockAdapter(JSONLProvider(rows))
        replayer = LogReplayer(adapter, frequency_hz=100)
        replayer.start()
        replayer.join(timeout=1.0)
        replayer.stop()

        assert len(replayer.frames) == frame_count
        assert len(replayer.inter_frame_intervals) == expected_interval_count

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
# GROUP 8 – Replay Looping & Provider Storage
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

    def test_looping_keeps_provider_index_and_dataset_bounded(self):
        """Reset reuses provider storage; this does not measure process memory."""
        rows = [_good_row() for _ in range(5)]
        provider = JSONLProvider(rows)
        adapter = MockAdapter(provider, loop=True)
        adapter.connect()

        for _ in range(50):
            adapter.fetch_frame()

        # Provider internal index should wrap, not accumulate
        assert provider._idx <= len(rows)
        assert len(provider._data) == len(rows)
        adapter.disconnect()

    def test_jsonl_provider_loads_10000_rows(self, tmp_path):
        path = tmp_path / "large_replay.jsonl"
        rows = [
            json.dumps(_good_row(engine_rpm=float(index % 9500)))
            for index in range(10000)
        ]
        path.write_text("\n".join(rows), encoding="utf-8")

        provider = JSONLProvider(path)

        assert len(provider._data) == 10000

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

    def test_unknown_source_metadata_is_not_emitted(self):
        """Replay projects source metadata out of its emitted schema payload."""
        row = _good_row(undocumented_key="some_value")
        adapter = MockAdapter(JSONLProvider([row]))
        adapter.connect()
        frame = adapter.fetch_frame()
        assert "undocumented_key" not in frame.to_dict()
        assert "undocumented_key" not in frame.to_schema_dict()
        adapter.disconnect()

    def test_production_packet_raw_snapshot_is_immutable(self):
        packet = DataPacket(
            timestamp="2025-01-15T10:00:00.000+00:00",
            vin_hashed="a" * 64,
            protocol="J1979_MODE01",
            engine_rpm=800.0,
            vehicle_speed=0,
            coolant_temp=85.0,
            engine_load=20.0,
            stft_bank1=1.5,
            ltft_bank1=-2.0,
            _raw={"engine_rpm": 800.0},
        )

        with pytest.raises(TypeError):
            packet._raw["engine_rpm"] = 99999.0

    def test_production_to_schema_dict_does_not_key_error(self):
        packet = DataPacket(
            timestamp="2025-01-15T10:00:00.000+00:00",
            vin_hashed="a" * 64,
            protocol="UNKNOWN_PROTOCOL",
            engine_rpm=800.0,
            vehicle_speed=0,
            coolant_temp=85.0,
            engine_load=20.0,
            stft_bank1=1.5,
            ltft_bank1=-2.0,
        )

        assert packet.to_schema_dict()["protocol"] == "UNKNOWN_PROTOCOL"


class TestProductionCandidParser:
    """Production parser tests for known CANdid decode boundary behavior."""

    @pytest.mark.parametrize("pid", ["0C", "0x0C", 12])
    def test_engine_rpm_pid_accepts_bare_hex_prefixed_hex_and_integer(self, pid):
        parsed = CandidParser().parse({"pid": pid, "data": "0C 80"})

        assert parsed["engine_rpm"] == 800.0

    def test_invalid_pid_token_raises_value_error(self):
        with pytest.raises(ValueError):
            CandidParser().parse({"pid": "not-a-pid", "data": "0C 80"})

    @pytest.mark.parametrize(
        "pid,field_name",
        [
            ("0x06", "stft_bank1"),
            ("0x07", "ltft_bank1"),
        ],
    )
    @pytest.mark.parametrize("raw_byte", ["00", "FF"])
    def test_fuel_trim_byte_extremes_rejected_by_us001(
        self,
        pid,
        field_name,
        raw_byte,
    ):
        row = _good_row(pid=pid, data=raw_byte)
        provider = JSONLProvider([row], parser=CandidParser())
        adapter = MockAdapter(provider)
        adapter.connect()

        with pytest.raises(ValidationError) as exc_info:
            adapter.fetch_frame()

        message = str(exc_info.value)
        assert field_name in message
        assert "out of bounds" in message
        adapter.disconnect()


class TestProviderInputs:
    @pytest.mark.parametrize("provider_type", [JSONLProvider, CSVProvider])
    def test_empty_provider_stops_even_when_looping(self, provider_type):
        adapter = MockAdapter(provider_type([]), loop=True)
        adapter.connect()
        try:
            with pytest.raises(StopIteration):
                adapter.fetch_frame()
        finally:
            adapter.disconnect()

    @pytest.mark.parametrize("provider_type", [JSONLProvider, CSVProvider])
    def test_reset_replays_input_without_mutating_source(self, provider_type):
        row = _good_row()
        provider = provider_type([row])
        first = provider.get_next_row()
        first["engine_rpm"] = 99999.0
        with pytest.raises(StopIteration):
            provider.get_next_row()
        provider.reset()
        assert provider.get_next_row() == row
        assert row["engine_rpm"] == 800.0

    @pytest.mark.parametrize("content", ['{"engine_rpm":', '[]', 'null'])
    def test_malformed_jsonl_names_source_line(self, tmp_path, content):
        path = tmp_path / "malformed.jsonl"
        path.write_text("\n" + content + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed JSONL row 2"):
            JSONLProvider(path)

    @pytest.mark.parametrize("provider_type,suffix", [(JSONLProvider, "jsonl"), (CSVProvider, "csv")])
    def test_file_provider_emits_normalized_frame(self, tmp_path, provider_type, suffix):
        row = _good_row(engine_rpm=1200.0, vehicle_speed=60)
        path = tmp_path / f"replay.{suffix}"
        if suffix == "jsonl":
            path.write_text("\n" + json.dumps(row) + "\n\n", encoding="utf-8")
        else:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
        adapter = MockAdapter(provider_type(path))
        adapter.connect()
        try:
            assert adapter.fetch_frame().to_dict() == row
            with pytest.raises(StopIteration):
                adapter.fetch_frame()
        finally:
            adapter.disconnect()

    def test_malformed_csv_numeric_value_is_rejected(self, tmp_path):
        path = tmp_path / "malformed.csv"
        path.write_text("engine_rpm\ninvalid\n", encoding="utf-8")
        with pytest.raises(ValueError):
            CSVProvider(path).get_next_row()


def test_compatibility_exports_are_production_subjects():
    from autopulse import adapters, noise, providers, replayer
    from tests import simulation

    for module, names in (
        (adapters, ["MockAdapter", "DataPacket"]),
        (noise, ["NoiseGenerator"]),
        (providers, ["CSVProvider", "JSONLProvider", "CandidParser"]),
        (replayer, ["LogReplayer"]),
        (simulation, ["MockAdapter", "LogReplayer", "NoiseGenerator", "CSVProvider", "JSONLProvider"]),
    ):
        for name in names:
            assert getattr(module, name) is getattr(replay_module, name)


def test_packet_ambient_preserves_compatibility_constructor_and_serialization():
    from autopulse.adapters import DataPacket as CompatibilityPacket

    row = _good_row()
    raw = {"source": "synthetic"}
    # The historical tenth positional argument remains the raw snapshot.
    legacy = CompatibilityPacket(*row.values(), raw)
    assert legacy.to_dict() == row
    assert legacy._raw == raw
    packet = CompatibilityPacket(*row.values(), raw, ambient_temp=22.5)
    assert packet.to_dict() == dict(row, ambient_temp=22.5)
    assert packet.to_schema_dict() == dict(row, protocol="SAE_J1979", ambient_temp=22.5)
    assert packet._raw == raw


@pytest.mark.parametrize("provider_type", [JSONLProvider, CSVProvider])
@pytest.mark.parametrize("supplied", [False, True])
def test_replay_ambient_reaches_production_hdf(provider_type, supplied, replay_clock):
    from autopulse.analysis.pdm_processor import PdMProcessor

    rows = [_good_row(timestamp=f"2025-01-15T10:00:0{second}+00:00",
                      engine_rpm=850, engine_load=18, coolant_temp=88)
            for second in range(3)]
    if supplied:
        # Observe warmth, then a synthetic ambient change drives an eligible
        # HDF fault without a coolant rate jump. Omission disarms HDF instead.
        for row, ambient in zip(rows, [25, 80, None]):
            if ambient is not None:
                row["ambient_temp"] = ambient
    replay = LogReplayer(MockAdapter(provider_type(rows)))
    replay.start(max_frames=3)
    try:
        replay.join()
    finally:
        replay.stop()
    assert not replay.errors
    assert len(replay.frames) == 3
    processor = PdMProcessor(_VIN)
    alerts = []
    for index, packet in enumerate(replay.frames):
        alert = processor.process_frame(packet.to_schema_dict())
        alerts.append(alert)
        assert alert.failure_type != "SENSOR_ERROR"
        assert processor.hdf_detector.armed == (supplied and index < 2)
        if index == 1:
            assert processor.hdf_detector.score == (1 if supplied else 0)
            assert (alert.failure_type == "HDF") == supplied
    assert processor.hdf_detector.score == 0
    assert alerts[-1].failure_type != "HDF"


def test_replay_rejects_invalid_ambient_then_preserves_next_valid_frame(replay_clock):
    replay = LogReplayer(MockAdapter(JSONLProvider([
        _good_row(ambient_temp=None), _good_row(ambient_temp=22.5),
    ])))
    replay.start(max_frames=2)
    try:
        replay.join()
    finally:
        replay.stop()
    assert len(replay.errors) == 1
    assert isinstance(replay.errors[0], ValidationError)
    assert len(replay.frames) == 1
    assert replay.frames[0].to_schema_dict()["ambient_temp"] == 22.5
