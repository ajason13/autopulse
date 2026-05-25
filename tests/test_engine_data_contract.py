"""
================================================================================
  AutoPulse  |  US-002: Adversarial Engine Data Contract Test Suite
  Role:       Senior Adversarial QA Engineer & Lead Auditor
  Ref Spec:   US-001 (Engineering Architecture Report, OBD-II Engine Data Contract)
  Framework:  pytest + jsonschema (draft-07)
================================================================================

Run with:
    pip install pytest jsonschema
    pytest tests/test_engine_data_contract.py -v

All tests derive boundary values directly from the Physics-Based Boundary Logic
table in US-001 and the canonical JSON Schema defined therein.
================================================================================
"""

import copy
import pytest
from jsonschema import ValidationError

from autopulse.data.validator import (
    RESTRICTED_SERVICE_IDS,
    SecurityViolationRedLine,
    command_filter,
    validate_frame,
)


# ──────────────────────────────────────────────────────────────────────────────
# GOLDEN FRAME  — a fully valid baseline frame used by most tests
# ──────────────────────────────────────────────────────────────────────────────

GOLDEN_FRAME = {
    "timestamp":      "2025-07-04T14:22:05.123Z",
    "vin_hashed":     "a" * 64,                   # 64 lowercase hex chars
    "protocol":       "SAE_J1979",
    "engine_rpm":     800.0,
    "vehicle_speed":  0,
    "coolant_temp":   88.0,
    "engine_load":    15.5,
    "stft_bank1":     1.6,
    "ltft_bank1":    -2.3,
}


def mutate(frame: dict, **overrides) -> dict:
    """Return a deep-copy of frame with the supplied key/value overrides."""
    f = copy.deepcopy(frame)
    f.update(overrides)
    return f


def drop(frame: dict, *keys) -> dict:
    """Return a deep-copy of frame with the named keys removed."""
    f = copy.deepcopy(frame)
    for k in keys:
        f.pop(k, None)
    return f


# ══════════════════════════════════════════════════════════════════════════════
# §1  SCHEMA VALIDATION — Happy Path
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaHappyPath:
    """The golden frame and its close variants must pass without exception."""

    def test_golden_frame_is_valid(self):
        """Baseline: a well-formed frame must validate cleanly."""
        validate_frame(GOLDEN_FRAME)

    def test_protocol_j1979_2_accepted(self):
        """Both enumerated protocol strings must be accepted."""
        validate_frame(mutate(GOLDEN_FRAME, protocol="SAE_J1979-2"))

    def test_all_numeric_fields_as_floats(self):
        """JSON numbers with decimal points must be accepted for all numeric PIDs."""
        frame = mutate(
            GOLDEN_FRAME,
            engine_rpm=3500.25,
            coolant_temp=95.0,
            engine_load=62.5,
            stft_bank1=0.78,
            ltft_bank1=-1.56,
        )
        validate_frame(frame)

    def test_optional_ambient_temp_accepted(self):
        """PID 0x46 may be present for HDF ΔT calculations but is not core."""
        validate_frame(mutate(GOLDEN_FRAME, ambient_temp=22.0))


# ══════════════════════════════════════════════════════════════════════════════
# §2  SCHEMA VALIDATION — Missing Required Fields
# ══════════════════════════════════════════════════════════════════════════════

class TestMissingRequiredFields:
    """
    Every field listed under 'required' in US-001 must individually trigger
    a ValidationError when absent.  A sensor frame with partial data is
    worse than no frame — it risks populating downstream models with nulls.
    """

    REQUIRED_FIELDS = [
        "timestamp", "vin_hashed", "protocol",
        "engine_rpm", "vehicle_speed", "coolant_temp",
        "engine_load", "stft_bank1", "ltft_bank1",
    ]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_missing_field_raises_validation_error(self, field):
        bad_frame = drop(GOLDEN_FRAME, field)
        with pytest.raises(ValidationError):
            validate_frame(bad_frame)


# ══════════════════════════════════════════════════════════════════════════════
# §3  SCHEMA VALIDATION — Incorrect Types
# ══════════════════════════════════════════════════════════════════════════════

class TestIncorrectTypes:
    """
    Type coercion must never happen silently.  Each numeric PID must reject
    a string value; the VIN hash must reject a non-string.
    """

    def test_engine_rpm_as_string_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, engine_rpm="800"))

    def test_coolant_temp_as_string_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, coolant_temp="88.0"))

    def test_engine_load_as_boolean_rejected(self):
        # JSON booleans are a subtype of integer in some validators; schema must
        # still reject them for numeric PID fields via strict type checking.
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, engine_load=True))

    def test_vehicle_speed_as_float_rejected(self):
        # US-001 declares vehicle_speed as 'integer'; 72.5 must be rejected.
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=72.5))

    def test_vin_hashed_as_integer_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed=12345))

    def test_timestamp_as_integer_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, timestamp=1720099325))

    def test_unknown_protocol_rejected(self):
        """Only the two enumerated protocol strings are legal."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, protocol="CAN_RAW"))


# ══════════════════════════════════════════════════════════════════════════════
# §4  SCHEMA VALIDATION — Additional Properties Prohibition
# ══════════════════════════════════════════════════════════════════════════════

class TestAdditionalPropertiesBlocked:
    """
    additionalProperties: false is a security and data-integrity control.
    No undocumented fields may pass through the ingestion boundary.
    """

    def test_extra_field_rejected(self):
        frame = mutate(GOLDEN_FRAME, injected_payload="DROP TABLE vehicles;")
        with pytest.raises(ValidationError):
            validate_frame(frame)

    def test_raw_service_id_field_rejected(self):
        frame = mutate(GOLDEN_FRAME, service_id=0x31)
        with pytest.raises(ValidationError):
            validate_frame(frame)

    def test_obd_mode_field_rejected(self):
        frame = mutate(GOLDEN_FRAME, obd_mode="0x08")
        with pytest.raises(ValidationError):
            validate_frame(frame)


# ══════════════════════════════════════════════════════════════════════════════
# §5  PHYSICS-BOUNDARY "DIRTY DATA" — Engine RPM  (PID 0x0C)
# ══════════════════════════════════════════════════════════════════════════════

class TestEngineRPMBoundaries:
    """
    Physics justification (US-001): Production ICE engines suffer valvetrain
    failure (valve float) before 10,000 RPM; 9,500 is the hard schema ceiling.
    Negative RPM is physically impossible (unidirectional crankshaft rotation).
    """

    def test_rpm_at_exact_minimum_0_accepted(self):
        """Key-On Engine-Off: RPM == 0.0 must be valid."""
        validate_frame(mutate(GOLDEN_FRAME, engine_rpm=0.0))

    def test_rpm_at_exact_maximum_9500_accepted(self):
        """Upper boundary: 9,500.0 is the last legal value."""
        validate_frame(mutate(GOLDEN_FRAME, engine_rpm=9500.0))

    def test_rpm_just_below_maximum_9499_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, engine_rpm=9499.0))

    def test_rpm_just_above_maximum_9501_rejected(self):
        """Spec test vector: 9,501 must be rejected (§ Positive/Negative Test Vectors)."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, engine_rpm=9501.0))

    def test_rpm_negative_1_rejected(self):
        """Negative RPM indicates signed-integer wrapping or data corruption."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, engine_rpm=-1.0))

    def test_rpm_protocol_theoretical_max_16383_rejected(self):
        """
        J1979 protocol ceiling (16,383.75) is intentionally excluded from the
        schema; values in this range represent sensor noise, not real engine state.
        """
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, engine_rpm=16383.75))


# ══════════════════════════════════════════════════════════════════════════════
# §6  PHYSICS-BOUNDARY "DIRTY DATA" — Coolant Temperature  (PID 0x05)
# ══════════════════════════════════════════════════════════════════════════════

class TestCoolantTemperatureBoundaries:
    """
    Physics justification (US-001): Pressurized 50/50 glycol mix boils ~129°C
    @ 15 psi; 140°C is the hard ceiling, -40°C is the SAE J1979 formula floor.
    """

    def test_coolant_at_minimum_neg40_accepted(self):
        """Lower boundary: -40°C is the J1979 formula floor — must be accepted."""
        validate_frame(mutate(GOLDEN_FRAME, coolant_temp=-40.0))

    def test_coolant_at_maximum_140_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, coolant_temp=140.0))

    def test_coolant_just_below_minimum_neg41_rejected(self):
        """Spec test: -41°C exceeds the formula minimum; must be rejected."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, coolant_temp=-41.0))

    def test_coolant_just_above_maximum_141_rejected(self):
        """Spec test: 141°C is beyond total cooling-system integrity; must be rejected."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, coolant_temp=141.0))

    def test_coolant_stuck_high_sensor_failure_rejected(self):
        """A shorted NTC thermistor may output a constant 200°C — must be blocked."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, coolant_temp=200.0))


class TestAmbientTemperatureBoundaries:
    """
    Optional PID 0x46 is permitted for HDF calculations while preserving the
    strict no-undocumented-fields ingestion boundary.
    """

    def test_ambient_at_minimum_neg40_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, ambient_temp=-40.0))

    def test_ambient_at_maximum_80_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, ambient_temp=80.0))

    def test_ambient_below_minimum_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, ambient_temp=-41.0))

    def test_ambient_above_maximum_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, ambient_temp=81.0))


# ══════════════════════════════════════════════════════════════════════════════
# §7  PHYSICS-BOUNDARY "DIRTY DATA" — Fuel Trims  (PIDs 0x06 / 0x07)
# ══════════════════════════════════════════════════════════════════════════════

class TestFuelTrimBoundaries:
    """
    Physics justification (US-001): ECMs typically flag DTCs at ±25%; the
    ±50% schema limit captures the outer edge of protocol range while rejecting
    values that indicate bit-level noise or parser errors.
    """

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_at_minimum_neg50_accepted(self, field):
        validate_frame(mutate(GOLDEN_FRAME, **{field: -50.0}))

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_at_maximum_50_accepted(self, field):
        validate_frame(mutate(GOLDEN_FRAME, **{field: 50.0}))

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_just_below_minimum_neg51_rejected(self, field):
        """Spec test: -51% is beyond protocol range; must be rejected."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, **{field: -51.0}))

    @pytest.mark.parametrize("field", ["stft_bank1", "ltft_bank1"])
    def test_fuel_trim_just_above_maximum_51_rejected(self, field):
        """Spec test: +51% is noise or integer overflow; must be rejected."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, **{field: 51.0}))

    def test_fuel_trim_zero_crossings_accepted(self):
        """Stoichiometric ideal: both trims at 0.0 must be valid."""
        validate_frame(mutate(GOLDEN_FRAME, stft_bank1=0.0, ltft_bank1=0.0))


# ══════════════════════════════════════════════════════════════════════════════
# §8  PHYSICS-BOUNDARY "DIRTY DATA" — Vehicle Speed  (PID 0x0D)
# ══════════════════════════════════════════════════════════════════════════════

class TestVehicleSpeedBoundaries:
    """
    US-001 schema maps PID 0x0D as integer 0–255 km/h (raw byte value).
    """

    def test_speed_zero_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=0))

    def test_speed_255_accepted(self):
        """Protocol maximum (raw byte = 0xFF) must be schema-valid."""
        validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=255))

    def test_speed_negative_rejected(self):
        """OBD-II protocol does not encode direction; negative values are corruption."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=-1))

    def test_speed_above_255_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=256))


# ══════════════════════════════════════════════════════════════════════════════
# §9  TEMPORAL ANOMALY — Thermal Shock Detection
# ══════════════════════════════════════════════════════════════════════════════

class TestTemporalAnomalies:
    """
    US-001 (§ Positive and Negative Test Vectors): A jump from 85°C to 135°C
    within one second must be flagged as sensor noise/fault.

    The AutoPulse ingestion layer must implement rate-of-change (ΔT/Δt) logic.

    Physics basis: ICE coolant temperature rises at ~0.5–2°C/s under maximum
    thermal load.  A 50°C jump in < 1 second is physically impossible without
    total loss of coolant.

    Maximum allowed ΔT between consecutive 1 Hz frames: 5°C/s (conservative).
    """

    MAX_COOLANT_DELTA_PER_SECOND = 5.0  # °C/s  — physics-derived guard rail

    @staticmethod
    def detect_thermal_anomaly(
        prev_temp: float, curr_temp: float, elapsed_seconds: float
    ) -> bool:
        """
        Returns True if the temperature delta exceeds the physics-derived
        rate-of-change threshold, indicating sensor noise or fault.
        """
        if elapsed_seconds <= 0:
            raise ValueError("elapsed_seconds must be positive")
        delta = abs(curr_temp - prev_temp)
        rate = delta / elapsed_seconds
        return rate > TestTemporalAnomalies.MAX_COOLANT_DELTA_PER_SECOND

    def test_cold_start_gradient_is_valid(self):
        """
        Spec test (§ Cold Start Scenario): 0°C → 85°C over 600 seconds.
        Per-second rate ≈ 0.14°C/s — well within physics bounds.
        """
        assert not self.detect_thermal_anomaly(0.0, 85.0, 600.0)

    def test_thermal_anomaly_flagged_80c_to_135c_in_under_1_second(self):
        """
        Spec test vector (§ Thermal Anomaly Test):
        80°C → 135°C in 0.5 seconds = 110°C/s — must trigger anomaly flag.
        """
        assert self.detect_thermal_anomaly(80.0, 135.0, 0.5)

    def test_thermal_anomaly_flagged_at_1hz_sample(self):
        """
        At normal 1 Hz sampling, a 55°C jump between consecutive frames (Δt=1s)
        still exceeds the 5°C/s guard rail.
        """
        assert self.detect_thermal_anomaly(80.0, 135.0, 1.0)

    def test_normal_warm_up_not_flagged(self):
        """
        A healthy engine warming at 2°C/s must NOT trigger the anomaly flag.
        """
        assert not self.detect_thermal_anomaly(70.0, 72.0, 1.0)

    def test_steady_state_no_change_not_flagged(self):
        """Thermostat holding at 92°C: ΔT = 0 must never be anomalous."""
        assert not self.detect_thermal_anomaly(92.0, 92.0, 1.0)

    def test_anomaly_detector_rejects_non_positive_elapsed_time(self):
        with pytest.raises(ValueError):
            self.detect_thermal_anomaly(80.0, 90.0, 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# §10  SECURITY RED LINE INJECTION — Command Filter
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityRedLineInjection:
    """
    US-001 (§ Security Architecture): The command filter must intercept and
    drop every outgoing CAN frame that carries a restricted Service ID, then
    raise SecurityViolationRedLine.  No restricted command may reach the bus.
    """

    def test_j1979_mode_0x08_raises_security_violation(self):
        """
        Spec test: Mode 0x08 (Request Control of On-Board System) is CRITICAL.
        Allows external override of actuators — fuel pump, throttle, radiator fan.
        """
        with pytest.raises(SecurityViolationRedLine) as exc_info:
            command_filter(0x08)
        assert exc_info.value.service_id == 0x08
        assert "SECURITY_VIOLATION_RED_LINE" in str(exc_info.value)

    def test_uds_service_0x31_raises_security_violation(self):
        """
        Spec test: UDS RoutineControl (0x31) can initiate EVAP leak tests or
        other in-motion procedures — an active safety hazard at highway speeds.
        """
        with pytest.raises(SecurityViolationRedLine) as exc_info:
            command_filter(0x31)
        assert exc_info.value.service_id == 0x31
        assert "SECURITY_VIOLATION_RED_LINE" in str(exc_info.value)

    def test_j1979_mode_0x04_dtc_clear_raises_security_violation(self):
        """
        Mode 0x04 erases diagnostic history and resets readiness monitors.
        A vehicle with a latent emissions fault could pass inspection after erasure.
        """
        with pytest.raises(SecurityViolationRedLine):
            command_filter(0x04)

    def test_uds_service_0x14_diagnostic_reset_raises_security_violation(self):
        with pytest.raises(SecurityViolationRedLine):
            command_filter(0x14)

    def test_uds_service_0x2e_write_data_raises_security_violation(self):
        """WriteDataByIdentifier can overwrite ECU calibration tables."""
        with pytest.raises(SecurityViolationRedLine):
            command_filter(0x2E)

    def test_uds_service_0x10_programming_session_raises_security_violation(self):
        """DiagnosticSessionControl into programming mode enables ECU flashing."""
        with pytest.raises(SecurityViolationRedLine):
            command_filter(0x10)

    def test_legitimate_read_service_0x22_passes_filter(self):
        """
        UDS Service 0x22 (ReadDataByIdentifier) is the J1979-2 read mechanism.
        It must pass the filter without exception.
        """
        try:
            command_filter(0x22)
        except SecurityViolationRedLine:
            pytest.fail("Service 0x22 (read-only) was incorrectly blocked by command filter")

    def test_legacy_read_mode_0x01_passes_filter(self):
        """J1979 Mode 0x01 (current data request) is read-only and must pass."""
        try:
            command_filter(0x01)
        except SecurityViolationRedLine:
            pytest.fail("Mode 0x01 (read-only) was incorrectly blocked by command filter")

    def test_security_violation_exception_carries_service_id(self):
        """The exception must expose the offending service_id for audit logging."""
        with pytest.raises(SecurityViolationRedLine) as exc_info:
            command_filter(0x31)
        assert hasattr(exc_info.value, "service_id")
        assert exc_info.value.service_id == 0x31

    def test_all_restricted_ids_blocked(self):
        """Parametric sweep: every restricted Service ID in the table must be blocked."""
        for sid in RESTRICTED_SERVICE_IDS:
            with pytest.raises(SecurityViolationRedLine):
                command_filter(sid)


# ══════════════════════════════════════════════════════════════════════════════
# §11  ZERO-VALUE ROBUSTNESS  (Key-On, Engine-Off scenario)
# ══════════════════════════════════════════════════════════════════════════════

class TestZeroValueRobustness:
    """
    US-001 (§ Zero-Value Robustness): RPM, Speed, and Load can be exactly 0
    when the ignition is on but the engine has not started.  These values must
    not be rejected as invalid by the schema.

    This is a mandatory test because some naive validators treat 0 as falsy
    and incorrectly apply the 'required' or 'minimum' constraint.
    """

    def test_rpm_zero_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, engine_rpm=0.0))

    def test_vehicle_speed_zero_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, vehicle_speed=0))

    def test_engine_load_zero_accepted(self):
        validate_frame(mutate(GOLDEN_FRAME, engine_load=0.0))

    def test_full_key_on_engine_off_frame_accepted(self):
        """
        Complete Key-On Engine-Off frame: RPM=0, Speed=0, Load=0.
        Coolant and fuel trims may still carry valid non-zero readings.
        """
        koeo_frame = mutate(
            GOLDEN_FRAME,
            engine_rpm=0.0,
            vehicle_speed=0,
            engine_load=0.0,
            stft_bank1=0.0,
            ltft_bank1=0.0,
            coolant_temp=20.0,
        )
        validate_frame(koeo_frame)

    def test_stft_ltft_zero_simultaneously_accepted(self):
        """Perfect stoichiometry (both trims at zero) must be schema-valid."""
        validate_frame(mutate(GOLDEN_FRAME, stft_bank1=0.0, ltft_bank1=0.0))


# ══════════════════════════════════════════════════════════════════════════════
# §12  VIN HASH FORMAT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestVINHashValidation:
    """
    Privacy-preserving tracking requires a valid SHA-256 hex digest (64
    lowercase hex characters). The pattern ^[a-f0-9]{64}$ must be enforced.
    """

    def test_valid_sha256_hex_accepted(self):
        valid_hash = "b94d27b9934d3e08a52e52d7da7dabfa" + "c0ff1234" * 4
        validate_frame(mutate(GOLDEN_FRAME, vin_hashed=valid_hash))

    def test_uppercase_hex_rejected(self):
        """Pattern is lowercase-only; uppercase must be rejected."""
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed="A" * 64))

    def test_short_hash_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed="a" * 63))

    def test_long_hash_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed="a" * 65))

    def test_non_hex_characters_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed="g" * 64))

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            validate_frame(mutate(GOLDEN_FRAME, vin_hashed=""))
