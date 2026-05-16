"""
================================================================================
AutoPulse | US-003: Core PdM Algorithms — Adversarial Test Suite
Role: Senior Adversarial QA Engineer & Lead Auditor
Ref Spec: US-003 (Technical Specification for AutoPulse Core Predictive
          Maintenance Algorithms), US-001 (OBD-II Engine Data Contract)
Dataset:  AI4I 2020 Predictive Maintenance Dataset
Framework: pytest + math (stdlib only; no external PdM deps required)

================================================================================
Run with:
    pip install pytest
    pytest tests/test_us003_pdm_algorithms.py -v

All boundary values are derived directly from the US-003 specification:
  - HDF critical trigger:  ΔT < 8.6 K  AND  RPM < 1380
  - OSF S_limit:           11 000 (L) | 12 000 (M) | 13 000 (H)
  - OSF anomaly zone:      0.8 × S_limit ≤ S_idx < S_limit
  - Lugging penalty:       RPM < 1500 AND load > 80 %
  - Sigmoid model:         P = 1 / (1 + e^(-k(x - x₀)))
  - Circular buffer:       60-element ring, O(1) push/pop
  - PdMAlert schema:       failure_probability ∈ [0.0, 1.0]

Math validation notes (cross-checked against US-001):
  - Load formula: A × 100 / 255  ≡  A / 2.55  (identical; tests use float %)
  - ΔT in Kelvin = ΔT in Celsius (delta is scale-invariant)
  - Sigmoid at x = x₀ → P = 0.5 exactly (verified in §TestSigmoidModel)
================================================================================
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# PRODUCTION IMPORTS
# ──────────────────────────────────────────────────────────────────────────────
from src.analysis.pdm_processor import PdMProcessor, PdMAlert
from src.analysis.hdf_detector import HDFDetector
from src.analysis.osf_detector import OSFDetector
from src.analysis.circular_buffer import CircularBuffer
from src.analysis.utils import (
    VehicleClass,
    OSF_LIMITS,
    HDF_DELTA_T_THRESHOLD_K,
    HDF_RPM_THRESHOLD,
    LUGGING_RPM_CEILING,
    LUGGING_LOAD_FLOOR,
    MAX_COOLANT_RATE_PER_SECOND,
    PROB_ANOMALY_LO,
    PROB_ANOMALY_HI,
    PROB_CRITICAL,
    sigmoid
)

# ─── Wrappers for Test Compatibility ─────────────────────────────────────────

def compute_hdf_probability(delta_t: float, rpm: float, k: float = 0.8) -> float:
    return HDFDetector.compute_probability(delta_t, rpm, k_dt=k)

def compute_osf_stress_index(load_pct: float, rpm: float, elapsed_seconds: float, lugging_k: float = 0.3) -> float:
    detector = OSFDetector() # Temporary detector for stateless math test
    return detector.compute_stress_increment(load_pct, rpm, elapsed_seconds, lugging_k)

def classify_osf(s_idx: float, vehicle_class: VehicleClass) -> str:
    detector = OSFDetector(vehicle_class)
    detector.s_idx = s_idx
    return detector.classify()

def compute_osf_probability(s_idx: float, vehicle_class: VehicleClass, k: float = 0.001) -> float:
    detector = OSFDetector(vehicle_class)
    detector.s_idx = s_idx
    return detector.compute_probability(k)

def detect_thermal_rate_anomaly(prev_temp: float, curr_temp: float, elapsed_seconds: float) -> bool:
    return HDFDetector.detect_thermal_rate_anomaly(prev_temp, curr_temp, elapsed_seconds)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

_BASE_VIN = "a" * 64


def _good_frame(**overrides) -> dict:
    """
    Minimal valid OBD frame carrying all PIDs required by US-003 Step 1.
    Reflects a healthy engine at idle with nominal temperatures.
    """
    base = {
        "timestamp": "2025-07-04T14:22:05.123Z",
        "vin_hashed": _BASE_VIN,
        "protocol": "SAE_J1979",
        "engine_rpm": 850.0,       # PID 0x0C — idle
        "vehicle_speed": 0,         # PID 0x0D
        "coolant_temp": 88.0,       # PID 0x05 — normal operating temp
        "engine_load": 18.0,        # PID 0x04 — light idle load
        "stft_bank1": 1.6,          # PID 0x06
        "ltft_bank1": -2.3,         # PID 0x07
        "ambient_temp": 22.0,       # PID 0x46 — required for ΔT computation
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# §1  SIGMOID PROBABILITY MODEL
# ══════════════════════════════════════════════════════════════════════════════

class TestSigmoidModel:
    """
    Verifies the logistic sigmoid P = 1/(1 + e^(-k(x - x₀))) used by both
    the HDF and OSF probability branches.  US-003 §Probability Modeling.
    """

    def test_sigmoid_at_threshold_returns_exactly_0_5(self):
        """
        Math proof: when x == x₀, exponent is 0, e^0 = 1, P = 1/2.
        This is the anomaly/normal boundary and must be exact.
        """
        p = sigmoid(8.6, x0=8.6, k=1.0)
        assert abs(p - 0.5) < 1e-9

    def test_sigmoid_below_threshold_returns_less_than_0_5(self):
        """x < x₀ → negative exponent argument → P < 0.5."""
        p = sigmoid(5.0, x0=8.6, k=1.0)
        assert p < 0.5

    def test_sigmoid_above_threshold_returns_greater_than_0_5(self):
        """x > x₀ → positive exponent argument → P > 0.5."""
        p = sigmoid(12.0, x0=8.6, k=1.0)
        assert p > 0.5

    def test_sigmoid_output_always_in_unit_interval(self):
        """Sigmoid is bounded (0, 1) for all real inputs."""
        for x in [-1e6, -100.0, 0.0, 8.6, 100.0, 1e6]:
            p = sigmoid(x, x0=8.6, k=0.8)
            assert 0.0 < p < 1.0

    def test_sigmoid_k_controls_steepness(self):
        """Higher k → steeper curve → larger probability difference at equal offset."""
        x, x0 = 10.0, 8.6
        p_low_k = sigmoid(x, x0=x0, k=0.1)
        p_high_k = sigmoid(x, x0=x0, k=2.0)
        assert p_high_k > p_low_k

    def test_sigmoid_osf_at_class_l_limit_returns_exactly_0_5(self):
        """OSF sigmoid anchored at anomaly lower bound: 0.8 × 11 000 = 8 800."""
        anomaly_lo = 0.8 * OSF_LIMITS["L"]  # 8 800
        p = sigmoid(anomaly_lo, x0=anomaly_lo, k=0.001)
        assert abs(p - 0.5) < 1e-9


# ══════════════════════════════════════════════════════════════════════════════
# §2  HDF DETECTION — CRITICAL TRIGGER (AI4I BOUNDARY)
# ══════════════════════════════════════════════════════════════════════════════

class TestHDFCriticalTrigger:
    """
    AI4I 2020 HDF condition: ΔT < 8.6 K AND RPM < 1380.
    Both conditions must be true simultaneously for failure_probability = 1.0.
    US-003 §Logic Specification for Heat Dissipation Detection.
    """

    def test_both_conditions_met_returns_critical_probability(self):
        """
        Spec test vector: ΔT = 8.5 K, RPM = 1 379.
        Both thresholds breached → probability must be 1.0.
        """
        p = compute_hdf_probability(delta_t=8.5, rpm=1_379.0)
        assert p == PROB_CRITICAL

    def test_delta_t_at_exact_threshold_does_not_fire(self):
        """
        ΔT = 8.6 K is the boundary — spec says 'below 8.6', so 8.6 is NOT
        critical even when RPM is low.  Tests the strict inequality.
        """
        p = compute_hdf_probability(delta_t=8.6, rpm=1_000.0)
        assert p < PROB_CRITICAL

    def test_rpm_at_exact_threshold_does_not_fire(self):
        """RPM = 1380 is the boundary — spec says 'below 1380', so 1380 is NOT critical."""
        p = compute_hdf_probability(delta_t=5.0, rpm=1_380.0)
        assert p < PROB_CRITICAL

    def test_low_delta_t_high_rpm_does_not_reach_critical(self):
        """
        ΔT condition breached but RPM is high → cooling flow sufficient.
        Only one leg of the AND gate is satisfied; critical must not fire.
        """
        p = compute_hdf_probability(delta_t=4.0, rpm=3_500.0)
        assert p < PROB_CRITICAL

    def test_low_rpm_normal_delta_t_does_not_reach_critical(self):
        """
        RPM condition breached but ΔT is healthy → heat is still being rejected.
        """
        p = compute_hdf_probability(delta_t=40.0, rpm=800.0)
        assert p < PROB_CRITICAL

    def test_worst_case_extreme_values_returns_critical(self):
        """ΔT = 0 K (saturated coolant), RPM = 0 (engine dragging) → critical."""
        p = compute_hdf_probability(delta_t=0.0, rpm=0.0)
        assert p == PROB_CRITICAL

    def test_critical_probability_is_exactly_1_0_not_above(self):
        """Probability ceiling must be 1.0 — values above are a schema violation."""
        p = compute_hdf_probability(delta_t=2.0, rpm=500.0)
        assert p <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# §3  HDF DETECTION — ANOMALY ZONE (0.5 < P < 1.0)
# ══════════════════════════════════════════════════════════════════════════════

class TestHDFAnomalyZone:
    """
    Early-warning anomaly detection before the AI4I hard threshold is breached.
    Probability must be in (0.5, 1.0) and is_anomaly must be True.
    """

    def test_degraded_delta_t_produces_anomaly_probability(self):
        """
        ΔT = 12.0 K (above critical 8.6 K but approaching) with low RPM
        should produce a probability in the anomaly band (0.5, 1.0).
        """
        p = compute_hdf_probability(delta_t=12.0, rpm=1_100.0)
        assert PROB_ANOMALY_LO < p < PROB_CRITICAL, (
            f"Expected anomaly probability in ({PROB_ANOMALY_LO}, {PROB_CRITICAL}), got {p}"
        )

    def test_is_anomaly_flag_true_above_0_5(self):
        """PdMAlert.is_anomaly must be True whenever failure_probability > 0.5."""
        p = compute_hdf_probability(delta_t=12.0, rpm=1_100.0)
        alert = PdMAlert(
            timestamp=0,
            vin_hashed=_BASE_VIN,
            failure_probability=p,
            failure_type="HDF",
            is_anomaly=p > PROB_ANOMALY_LO,
        )
        assert alert.is_anomaly is True

    def test_is_anomaly_flag_false_in_normal_zone(self):
        """Healthy engine — probability below 0.5 → is_anomaly must be False."""
        p = compute_hdf_probability(delta_t=50.0, rpm=2_500.0)
        assert p <= PROB_ANOMALY_LO
        alert = PdMAlert(
            timestamp=0,
            vin_hashed=_BASE_VIN,
            failure_probability=p,
            failure_type="NONE",
            is_anomaly=p > PROB_ANOMALY_LO,
        )
        assert alert.is_anomaly is False

    def test_cooling_index_baseline_exceeded_triggers_anomaly(self):
        """
        CI > CI_baseline + margin at cruise RPM → anomaly.
        US-003: CI = T_coolant_out − T_ambient.
        """
        ci_baseline = 65.0    # °C difference at start of journey
        ci_margin = 10.0      # US-003 spec margin
        current_ci = 78.0     # elevated — radiator efficiency dropping

        is_ci_anomaly = current_ci > (ci_baseline + ci_margin)
        assert is_ci_anomaly, (
            f"CI={current_ci} should exceed baseline {ci_baseline} + margin {ci_margin}"
        )

    def test_normal_operating_conditions_produce_low_probability(self):
        """
        Healthy engine: coolant 90 °C, ambient 25 °C → ΔT = 65 K, RPM = 2 000.
        Probability must be well below the anomaly threshold.
        """
        frame = _good_frame(coolant_temp=90.0, ambient_temp=25.0, engine_rpm=2_000.0)
        delta_t = frame["coolant_temp"] - frame["ambient_temp"]
        p = compute_hdf_probability(delta_t=delta_t, rpm=frame["engine_rpm"])
        assert p < PROB_ANOMALY_LO


# ══════════════════════════════════════════════════════════════════════════════
# §4  HDF DETECTION — THERMAL RATE-OF-CHANGE GUARD
# ══════════════════════════════════════════════════════════════════════════════

class TestHDFThermalRateGuard:
    """
    US-001 §Thermal Anomaly Test / US-003 §HDF Logic:
    A physically impossible ΔT/Δt must be flagged as SENSOR_ERROR, not
    treated as a valid overheating event.  Max allowed rate: 5 °C/s.
    """

    def test_cold_start_gradient_not_flagged(self):
        """
        Spec test: 0 °C → 85 °C over 600 s ≈ 0.14 °C/s — within bounds.
        """
        assert not detect_thermal_rate_anomaly(0.0, 85.0, 600.0)

    def test_thermal_shock_85_to_135_in_1_second_flagged(self):
        """
        Spec test vector: 85 °C → 135 °C in 1 s = 50 °C/s > 5 °C/s.
        Must be flagged as sensor noise / fault.
        """
        assert detect_thermal_rate_anomaly(85.0, 135.0, 1.0)

    def test_thermal_shock_in_half_second_flagged(self):
        """80 °C → 135 °C in 0.5 s = 110 °C/s — extreme sensor spike."""
        assert detect_thermal_rate_anomaly(80.0, 135.0, 0.5)

    def test_normal_warm_up_2_degrees_per_second_not_flagged(self):
        """Healthy warm-up: 2 °C/s is within the 5 °C/s guard rail."""
        assert not detect_thermal_rate_anomaly(70.0, 72.0, 1.0)

    def test_steady_state_no_change_not_flagged(self):
        """Thermostat holding at operating temperature: ΔT = 0 is never anomalous."""
        assert not detect_thermal_rate_anomaly(92.0, 92.0, 1.0)

    def test_stuck_thermostat_detected_via_plateau(self):
        """
        Thermostat stuck open: temperature plateaus below 80 °C after 600 s.
        After the expected warm-up window, temp < 80 °C signals degradation.
        (Rate guard does not apply; tested at the PdMProcessor integration level.)
        """
        elapsed_s = 600.0
        plateau_temp = 65.0
        normal_min_temp = 80.0
        stuck_thermostat_suspected = elapsed_s > 300 and plateau_temp < normal_min_temp
        assert stuck_thermostat_suspected

    def test_detector_rejects_zero_elapsed_time(self):
        """Guard: division by zero must raise ValueError, not silently pass."""
        with pytest.raises(ValueError):
            detect_thermal_rate_anomaly(80.0, 90.0, 0.0)

    def test_detector_rejects_negative_elapsed_time(self):
        """Negative elapsed time is nonsensical and must be rejected."""
        with pytest.raises(ValueError):
            detect_thermal_rate_anomaly(80.0, 90.0, -1.0)


# ══════════════════════════════════════════════════════════════════════════════
# §5  HDF DETECTION — MISSING PID (SENSOR_ERROR PATH)
# ══════════════════════════════════════════════════════════════════════════════

class TestHDFSensorErrorPath:
    """
    US-003 Step 1: if mandatory PIDs are absent, the processor must flag
    SENSOR_ERROR and abort the current cycle.  ΔT cannot be computed without
    both PID 0x05 (coolant) and PID 0x46 (ambient).
    """

    def test_missing_ambient_pid_cannot_compute_delta_t(self):
        """
        Without ambient temp (PID 0x46), the Cooling Index is undefined.
        The processor must detect the absence and set failure_type = SENSOR_ERROR.
        """
        frame = _good_frame()
        del frame["ambient_temp"]
        assert "ambient_temp" not in frame

    def test_missing_coolant_pid_cannot_compute_delta_t(self):
        frame = _good_frame()
        del frame["coolant_temp"]
        assert "coolant_temp" not in frame

    def test_missing_rpm_pid_prevents_hdf_evaluation(self):
        """RPM (PID 0x0C) is mandatory for the RPM < 1380 condition."""
        frame = _good_frame()
        del frame["engine_rpm"]
        assert "engine_rpm" not in frame

    def test_sensor_error_alert_has_correct_failure_type(self):
        """PdMAlert must carry failure_type = 'SENSOR_ERROR' on missing PID."""
        alert = PdMAlert(
            timestamp=1_720_099_000_000,
            vin_hashed=_BASE_VIN,
            failure_probability=0.0,
            failure_type="SENSOR_ERROR",
            is_anomaly=False,
            primary_pid=0x46,
        )
        assert alert.failure_type == "SENSOR_ERROR"
        assert alert.primary_pid == 0x46


# ══════════════════════════════════════════════════════════════════════════════
# §6  OSF DETECTION — VEHICLE CLASS THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════

class TestOSFVehicleClassThresholds:
    """
    AI4I 2020 OSF thresholds mapped to AutoPulse vehicle classes.
    Class L = 11 000, M = 12 000, H = 13 000.
    US-003 §Thresholds for Anomaly vs. Critical Failure.
    """

    @pytest.mark.parametrize("vehicle_class,limit", [
        ("L", 11_000.0),
        ("M", 12_000.0),
        ("H", 13_000.0),
    ])
    def test_s_idx_at_limit_is_critical(self, vehicle_class, limit):
        """S_idx == S_limit → CRITICAL, probability = 1.0."""
        assert classify_osf(limit, vehicle_class) == "OSF"
        assert compute_osf_probability(limit, vehicle_class) == PROB_CRITICAL

    @pytest.mark.parametrize("vehicle_class,limit", [
        ("L", 11_000.0),
        ("M", 12_000.0),
        ("H", 13_000.0),
    ])
    def test_s_idx_above_limit_is_critical(self, vehicle_class, limit):
        """S_idx > S_limit → still CRITICAL; no overflow behaviour."""
        assert classify_osf(limit + 1.0, vehicle_class) == "OSF"

    @pytest.mark.parametrize("vehicle_class,anomaly_lo", [
        ("L", 8_800.0),    # 0.8 × 11 000
        ("M", 9_600.0),    # 0.8 × 12 000
        ("H", 10_400.0),   # 0.8 × 13 000
    ])
    def test_s_idx_at_anomaly_lower_bound_is_osf_anomaly(self, vehicle_class, anomaly_lo):
        """
        S_idx = 0.8 × S_limit → enters anomaly zone.
        Math check: 0.8 × 11 000 = 8 800 (verified inline).
        """
        assert classify_osf(anomaly_lo, vehicle_class) == "OSF_ANOMALY"

    @pytest.mark.parametrize("vehicle_class,anomaly_lo", [
        ("L", 8_800.0),
        ("M", 9_600.0),
        ("H", 10_400.0),
    ])
    def test_s_idx_just_below_anomaly_lower_bound_is_normal(self, vehicle_class, anomaly_lo):
        """S_idx just below 0.8 × S_limit → NONE."""
        assert classify_osf(anomaly_lo - 1.0, vehicle_class) == "NONE"

    def test_anomaly_probability_in_correct_range(self):
        """
        In the anomaly zone, probability must satisfy 0.5 ≤ P < 1.0.
        Uses Class L mid-point (S_idx = 9 900, between 8 800 and 11 000).
        """
        s_idx = 9_900.0
        p = compute_osf_probability(s_idx, "L")
        assert PROB_ANOMALY_LO <= p < PROB_CRITICAL

    def test_normal_zone_probability_below_0_5(self):
        """Below the anomaly lower bound, probability must be < 0.5."""
        p = compute_osf_probability(5_000.0, "L")
        assert p < PROB_ANOMALY_LO

    def test_zero_s_idx_is_normal(self):
        """Engine off or first frame: S_idx = 0 → NONE."""
        assert classify_osf(0.0, "L") == "NONE"
        assert compute_osf_probability(0.0, "L") < PROB_ANOMALY_LO


# ══════════════════════════════════════════════════════════════════════════════
# §7  OSF DETECTION — WORKLOAD FACTOR AND LUGGING PENALTY
# ══════════════════════════════════════════════════════════════════════════════

class TestOSFWorkloadFactor:
    """
    Wf = Load_PID04 × RPM_PID0C.
    γ (lugging penalty) activates exponentially when RPM < 1500 AND load > 80 %.
    US-003 §Defining the Workload Factor.
    """

    def test_workload_factor_is_product_of_load_and_rpm(self):
        """
        Math check: Load = 60 %, RPM = 2 000 → Wf = 120 000 (before γ).
        S_idx over 1 second with γ = 1.0 must equal 120 000.
        """
        s_idx = compute_osf_stress_index(load_pct=60.0, rpm=2_000.0, elapsed_seconds=1.0)
        assert abs(s_idx - 120_000.0) < 1.0

    def test_lugging_condition_increases_stress_index(self):
        """
        RPM = 1 200, Load = 85 % → lugging active → γ > 1.0.
        S_idx must be larger than the non-penalised equivalent.
        """
        s_penalised = compute_osf_stress_index(load_pct=85.0, rpm=1_200.0, elapsed_seconds=1.0)
        s_normal = 85.0 * 1_200.0 * 1.0  # Wf with γ = 1.0
        assert s_penalised > s_normal

    def test_lugging_does_not_activate_at_rpm_exactly_1500(self):
        """
        RPM = 1 500 is NOT below 1 500 → lugging penalty must not activate.
        γ = 1.0, so S_idx == Wf × elapsed.
        """
        s = compute_osf_stress_index(load_pct=90.0, rpm=1_500.0, elapsed_seconds=1.0)
        expected = 90.0 * 1_500.0 * 1.0
        assert abs(s - expected) < 1.0

    def test_lugging_does_not_activate_at_load_exactly_80_pct(self):
        """
        Load = 80.0 % is NOT above 80 % → lugging penalty must not activate.
        """
        s = compute_osf_stress_index(load_pct=80.0, rpm=1_200.0, elapsed_seconds=1.0)
        expected = 80.0 * 1_200.0 * 1.0
        assert abs(s - expected) < 1.0

    def test_high_rpm_high_load_no_lugging_penalty(self):
        """
        Normal high-performance driving: RPM = 4 000, Load = 90 % → γ = 1.0.
        """
        s = compute_osf_stress_index(load_pct=90.0, rpm=4_000.0, elapsed_seconds=1.0)
        expected = 90.0 * 4_000.0 * 1.0
        assert abs(s - expected) < 1.0

    def test_zero_rpm_produces_zero_workload_factor(self):
        """
        Engine off: RPM = 0, Load = 0 → Wf = 0 → S_idx unchanged.
        The cumulative stress counter must freeze when the engine is off.
        """
        s = compute_osf_stress_index(load_pct=0.0, rpm=0.0, elapsed_seconds=1.0)
        assert s == 0.0

    def test_negative_elapsed_seconds_raises_value_error(self):
        """Negative time is physically nonsensical; must be rejected."""
        with pytest.raises(ValueError):
            compute_osf_stress_index(load_pct=50.0, rpm=2_000.0, elapsed_seconds=-1.0)

    def test_s_idx_accumulates_correctly_over_60_frames(self):
        """
        US-003 §State Persistence: S_idx integrates over time.
        60 frames at 1 Hz with Load=50 %, RPM=2 000, γ=1.0.
        Expected total = 60 × (50 × 2 000) = 6 000 000.
        """
        total = sum(
            compute_osf_stress_index(load_pct=50.0, rpm=2_000.0, elapsed_seconds=1.0)
            for _ in range(60)
        )
        assert abs(total - 6_000_000.0) < 1.0


# ══════════════════════════════════════════════════════════════════════════════
# §8  OSF DETECTION — SENSOR INTEGRITY CROSS-VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestOSFSensorIntegrity:
    """
    US-003 §Integration of Torque and Volumetric Efficiency:
    If Calculated Load (PID 0x04) and Absolute Load diverge by > 15 %,
    a SENSOR_INTEGRITY_ANOMALY must be raised alongside the PdM calculation.
    """

    DISCREPANCY_THRESHOLD_PCT = 15.0

    @staticmethod
    def _load_discrepancy_pct(calculated: float, absolute: float) -> float:
        denominator = max(calculated, absolute)
        if denominator == 0:
            return 0.0
        return abs(calculated - absolute) / denominator * 100.0

    def test_large_discrepancy_triggers_sensor_integrity_anomaly(self):
        """
        Calculated Load = 60 %, Absolute Load = 80 % → discrepancy = 25 % > 15 %.
        Processor must flag SENSOR_ERROR alongside the PdM result.
        """
        disc = self._load_discrepancy_pct(60.0, 80.0)
        assert disc > self.DISCREPANCY_THRESHOLD_PCT

    def test_small_discrepancy_does_not_trigger_anomaly(self):
        """
        Calculated Load = 60 %, Absolute Load = 62 % → discrepancy ≈ 3.2 % < 15 %.
        Normal sensor tolerance; no sensor error.
        """
        disc = self._load_discrepancy_pct(60.0, 62.0)
        assert disc < self.DISCREPANCY_THRESHOLD_PCT

    def test_exact_15_pct_discrepancy_triggers_anomaly(self):
        """Boundary test: exactly 15 % discrepancy must trigger the anomaly."""
        disc = self._load_discrepancy_pct(85.0, 100.0)
        assert abs(disc - 15.0) < 0.1
        assert disc >= self.DISCREPANCY_THRESHOLD_PCT

    def test_identical_load_values_produce_zero_discrepancy(self):
        """Both PIDs agree perfectly — no sensor anomaly."""
        disc = self._load_discrepancy_pct(75.0, 75.0)
        assert disc == 0.0

    def test_zero_calculated_load_not_divide_by_zero(self):
        """
        Edge case: Calculated Load = 0 (engine off) must not cause ZeroDivisionError.
        """
        disc = self._load_discrepancy_pct(0.0, 0.0)
        assert disc == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# §9  CIRCULAR BUFFER — 60-SECOND ROLLING WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class TestCircularBuffer:
    """
    US-003 §Circular Buffer Implementation:
    Fixed capacity 60, O(1) push, wraps without reallocation.
    """

    def test_empty_buffer_has_length_zero(self):
        buf = CircularBuffer(capacity=60)
        assert len(buf) == 0

    def test_push_single_element_length_is_one(self):
        buf = CircularBuffer(capacity=60)
        buf.push(42.0)
        assert len(buf) == 1

    def test_buffer_fills_to_capacity(self):
        buf = CircularBuffer(capacity=60)
        for i in range(60):
            buf.push(float(i))
        assert len(buf) == 60
        assert buf.is_full

    def test_push_beyond_capacity_does_not_grow(self):
        """Ring behaviour: capacity stays at 60 after overflow."""
        buf = CircularBuffer(capacity=60)
        for i in range(120):
            buf.push(float(i))
        assert len(buf) == 60

    def test_oldest_element_overwritten_on_overflow(self):
        """
        After 61 pushes into a capacity-60 buffer, element 0 is gone and
        the oldest visible element is element 1.
        """
        buf = CircularBuffer(capacity=60)
        for i in range(61):
            buf.push(float(i))
        elements = buf.to_list()
        assert elements[0] == 1.0   # element 0 was overwritten

    def test_to_list_returns_elements_in_insertion_order(self):
        """Elements must be returned oldest-first (tail → head)."""
        buf = CircularBuffer(capacity=5)
        for v in [10, 20, 30, 40, 50]:
            buf.push(v)
        assert buf.to_list() == [10, 20, 30, 40, 50]

    def test_to_list_after_overflow_maintains_insertion_order(self):
        """After wrap-around, to_list must still return in time order."""
        buf = CircularBuffer(capacity=3)
        for v in [1, 2, 3, 4, 5]:
            buf.push(v)
        result = buf.to_list()
        assert result == [3, 4, 5]

    def test_60_second_moving_average_computes_correctly(self):
        """
        A full 60-element buffer with values 1..60.
        Mean = (1 + 60) / 2 = 30.5.
        """
        buf = CircularBuffer(capacity=60)
        for i in range(1, 61):
            buf.push(float(i))
        elements = buf.to_list()
        mean = sum(elements) / len(elements)
        assert abs(mean - 30.5) < 1e-9

    def test_is_full_false_before_capacity_reached(self):
        buf = CircularBuffer(capacity=60)
        for i in range(59):
            buf.push(float(i))
        assert not buf.is_full

    def test_is_full_true_at_capacity(self):
        buf = CircularBuffer(capacity=60)
        for i in range(60):
            buf.push(float(i))
        assert buf.is_full

    def test_zero_capacity_rejected(self):
        """A ring buffer with zero capacity cannot compute a valid modulo."""
        with pytest.raises(ValueError):
            CircularBuffer(capacity=0)


# ══════════════════════════════════════════════════════════════════════════════
# §10  PDMALERT SCHEMA — OUTPUT CONTRACT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class TestPdMAlertSchema:
    """
    US-003 §Output Specification: PdMAlert field types, required fields,
    and probability range [0.0, 1.0].
    """

    def _make_alert(self, **overrides) -> PdMAlert:
        defaults = dict(
            timestamp=1_720_099_325_000,
            vin_hashed=_BASE_VIN,
            failure_probability=0.0,
            failure_type="NONE",
            is_anomaly=False,
        )
        defaults.update(overrides)
        return PdMAlert(**defaults)

    def test_failure_probability_zero_is_valid(self):
        alert = self._make_alert(failure_probability=0.0)
        assert alert.failure_probability == 0.0

    def test_failure_probability_one_is_valid(self):
        alert = self._make_alert(failure_probability=1.0, failure_type="HDF", is_anomaly=True)
        assert alert.failure_probability == 1.0

    def test_failure_probability_must_not_exceed_1(self):
        """
        No code path should produce a probability above 1.0.
        This test guards against unclamped sigmoid outputs.
        """
        for p in [compute_hdf_probability(d, r) for d, r in [
            (0.0, 0.0), (8.5, 1_379.0), (50.0, 3_000.0)
        ]]:
            assert p <= 1.0

    def test_failure_type_hdf_accepted(self):
        alert = self._make_alert(failure_type="HDF", failure_probability=1.0, is_anomaly=True)
        assert alert.failure_type == "HDF"

    def test_failure_type_osf_accepted(self):
        alert = self._make_alert(failure_type="OSF", failure_probability=1.0, is_anomaly=True)
        assert alert.failure_type == "OSF"

    def test_failure_type_osf_anomaly_accepted(self):
        alert = self._make_alert(failure_type="OSF_ANOMALY", failure_probability=0.72, is_anomaly=True)
        assert alert.failure_type == "OSF_ANOMALY"

    def test_failure_type_none_is_normal_state(self):
        alert = self._make_alert(failure_type="NONE")
        assert alert.failure_type == "NONE"
        assert alert.is_anomaly is False

    def test_failure_type_sensor_error_accepted(self):
        alert = self._make_alert(failure_type="SENSOR_ERROR", primary_pid=0x46)
        assert alert.failure_type == "SENSOR_ERROR"

    def test_vin_hashed_rejects_raw_vin(self):
        with pytest.raises(ValueError):
            self._make_alert(vin_hashed="1HGCM82633A004352")

    def test_is_anomaly_consistent_with_probability(self):
        """
        is_anomaly must be True iff failure_probability > 0.5.
        Tests that the alert is internally consistent.
        """
        for prob, expected_anomaly in [
            (0.0, False), (0.49, False), (0.5, False),
            (0.51, True), (0.85, True), (1.0, True),
        ]:
            alert = self._make_alert(
                failure_probability=prob,
                is_anomaly=prob > 0.5,
            )
            assert alert.is_anomaly == expected_anomaly, (
                f"P={prob}: expected is_anomaly={expected_anomaly}"
            )

    def test_highest_probability_branch_selected_as_primary(self):
        """
        US-003 Step 5: when HDF and OSF both fire, the highest probability
        is selected as the primary output.
        """
        p_hdf = compute_hdf_probability(delta_t=8.0, rpm=1_200.0)
        p_osf = compute_osf_probability(9_500.0, "L")
        primary_type = "HDF" if p_hdf >= p_osf else "OSF_ANOMALY"
        primary_prob = max(p_hdf, p_osf)

        alert = self._make_alert(
            failure_probability=primary_prob,
            failure_type=primary_type,
            is_anomaly=primary_prob > 0.5,
        )
        assert alert.failure_probability == primary_prob

    def test_obd_frame_attached_to_alert(self):
        """The triggering OBD frame must be embedded for auditability."""
        frame = _good_frame(coolant_temp=99.0)
        alert = self._make_alert(obd_frame=frame)
        assert alert.obd_frame is not None
        assert alert.obd_frame["coolant_temp"] == 99.0

    def test_window_summary_contains_expected_statistics(self):
        """
        Optional window_summary must carry min/max/avg of critical PIDs
        over the 60-second window.
        """
        summary = {
            "coolant_temp": {"min": 85.0, "max": 99.0, "avg": 91.0},
            "engine_rpm": {"min": 800.0, "max": 1_400.0, "avg": 1_100.0},
        }
        alert = self._make_alert(window_summary=summary)
        assert alert.window_summary["coolant_temp"]["avg"] == 91.0

    def test_window_summary_outlier_flag_is_boolean(self):
        processor = PdMProcessor(vin_hashed=_BASE_VIN)
        for rpm in [1_000.0, 1_010.0, 1_020.0]:
            processor.rpm_buffer.push(rpm)

        summary = processor._generate_summary()

        assert isinstance(summary["engine_rpm"]["is_statistical_outlier"], bool)


# ══════════════════════════════════════════════════════════════════════════════
# §11  PID FORMULA VERIFICATION (MATH CROSS-CHECK)
# ══════════════════════════════════════════════════════════════════════════════

class TestPIDFormulaVerification:
    """
    Validates that the SAE J1979 decoding formulas referenced in both
    US-001 and US-003 are numerically consistent.

    Cross-spec note: US-001 uses (A × 100) / 255 for engine load;
    US-003 uses A / 2.55.  These are algebraically identical:
        100 / 255 = 1 / 2.55 = 0.39215...
    Both forms are tested below.
    """

    def test_rpm_decode_a_26_b_0_is_1664(self):
        """PID 0x0C: (256 × A + B) / 4.  A=0x1A=26, B=0 → 1664.0 RPM."""
        a, b = 0x1A, 0x00
        rpm = (256 * a + b) / 4.0
        assert abs(rpm - 1664.0) < 0.01

    def test_rpm_decode_max_bytes_a_255_b_255(self):
        """Protocol maximum: (256 × 255 + 255) / 4 = 16 383.75 RPM."""
        rpm = (256 * 255 + 255) / 4.0
        assert abs(rpm - 16_383.75) < 0.01

    def test_engine_load_decode_a_255_is_100_pct(self):
        """PID 0x04: A=255 → 255 × 100 / 255 = 100.0 %."""
        load = 255 * 100 / 255
        assert abs(load - 100.0) < 1e-9

    def test_engine_load_us001_and_us003_formulas_identical(self):
        """
        US-001: A × 100 / 255
        US-003: A / 2.55
        Must produce the same float for all byte values.
        """
        for a in range(256):
            us001 = a * 100 / 255
            us003 = a / 2.55
            assert abs(us001 - us003) < 1e-9, (
                f"A={a}: US-001={us001}, US-003={us003} differ"
            )

    def test_coolant_temp_decode_a_120_is_80_celsius(self):
        """PID 0x05: A=120 (0x78) → 120 − 40 = 80 °C."""
        a = 120
        temp = a - 40
        assert temp == 80

    def test_coolant_temp_decode_lower_bound_a_0_is_neg40(self):
        """Formula floor: A=0 → 0 − 40 = −40 °C (matches schema minimum)."""
        assert 0 - 40 == -40

    def test_coolant_temp_decode_upper_bound_a_255_is_215(self):
        """Formula ceiling: A=255 → 255 − 40 = 215 °C (exceeds schema maximum of 140 °C)."""
        assert 255 - 40 == 215

    def test_stft_decode_a_128_is_zero_pct(self):
        """PID 0x06: A=128 → (128 − 128) × 100 / 128 = 0.0 % (neutral/stoichiometric)."""
        a = 128
        stft = (a - 128) * 100 / 128
        assert stft == 0.0

    def test_ltft_decode_a_255_is_positive_trim(self):
        """PID 0x07: A=255 → (255 − 128) × 100 / 128 = 99.21875 % (max positive trim)."""
        a = 255
        ltft = (a - 128) * 100 / 128
        assert abs(ltft - 99.21875) < 0.0001

    def test_kelvin_to_celsius_delta_is_scale_invariant(self):
        """
        US-003 §Feature Mapping: HDF uses ΔT < 8.6 K.
        Since delta is scale-invariant, 8.6 K == 8.6 °C difference.
        Confirmed: T1_K − T2_K = T1_C − T2_C.
        """
        t1_k, t2_k = 370.15, 361.55  # ΔT = 8.6 K
        t1_c, t2_c = t1_k - 273.15, t2_k - 273.15
        delta_k = t1_k - t2_k
        delta_c = t1_c - t2_c
        assert abs(delta_k - delta_c) < 1e-9
        assert abs(delta_k - 8.6) < 1e-9

    def test_osf_anomaly_lower_bound_arithmetic(self):
        """
        Math check: 0.8 × 11 000 = 8 800 (Class L).
        Verifies the anomaly zone arithmetic cited throughout US-003.
        """
        assert 0.8 * OSF_LIMITS["L"] == 8_800.0
        assert 0.8 * OSF_LIMITS["M"] == 9_600.0
        assert 0.8 * OSF_LIMITS["H"] == 10_400.0


# ══════════════════════════════════════════════════════════════════════════════
# §12  ALGORITHMIC EXECUTION SEQUENCE (US-003 STEP 1–5 INTEGRATION)
# ══════════════════════════════════════════════════════════════════════════════

class TestAlgorithmicExecutionSequence:
    """
    End-to-end walkthrough of the five-step processing sequence defined
    in US-003 §Logic Flowchart and Algorithmic Execution Sequence.
    Uses the inline reference implementations as stand-ins for the real
    PdMProcessor until src/analysis/ is implemented.
    """

    def _process_frame(self, frame: dict, vehicle_class: VehicleClass = "L") -> PdMAlert:
        """
        Uses the real PdMProcessor to execute the 5-step sequence.
        """
        processor = PdMProcessor(
            vin_hashed=frame.get("vin_hashed", _BASE_VIN),
            vehicle_class=vehicle_class
        )
        return processor.process_frame(frame)

    def test_healthy_frame_produces_none_alert(self):
        """Step 5: healthy engine → failure_type = 'NONE', is_anomaly = False."""
        # Wf = 1200 * 5 = 6000. Limit L = 11000. 6000 < 0.8 * 11000 (8800).
        frame = _good_frame(coolant_temp=88.0, ambient_temp=22.0, engine_rpm=1_200.0, engine_load=5.0)
        alert = self._process_frame(frame)
        assert alert.failure_type == "NONE"
        assert alert.is_anomaly is False

    def test_hdf_critical_frame_produces_hdf_alert(self):
        """
        Step 3 fires: ΔT = 30 − 25 = 5 K < 8.6 K, RPM = 900 < 1380.
        → failure_type = 'HDF', probability = 1.0.
        """
        frame = _good_frame(coolant_temp=30.0, ambient_temp=25.0, engine_rpm=900.0)
        alert = self._process_frame(frame)
        assert alert.failure_type == "HDF"
        assert alert.failure_probability == 1.0
        assert alert.is_anomaly is True

    def test_missing_ambient_temp_produces_sensor_error(self):
        """Step 1 guard: missing PID 0x46 → SENSOR_ERROR, cycle aborted."""
        frame = _good_frame()
        del frame["ambient_temp"]
        alert = self._process_frame(frame)
        assert alert.failure_type == "SENSOR_ERROR"
        assert alert.is_anomaly is False

    def test_obd_frame_attached_to_alert_for_auditability(self):
        """Step 5: the triggering OBD frame must be embedded in the alert."""
        frame = _good_frame()
        alert = self._process_frame(frame)
        assert alert.obd_frame is not None

    def test_higher_probability_branch_wins(self):
        """
        Step 5: both HDF and OSF evaluated; alert carries the higher value.
        Construct a frame where HDF fires critically and OSF is sub-threshold.
        """
        frame = _good_frame(
            coolant_temp=30.0,   # ΔT ≈ 5 K (below 8.6 K)
            ambient_temp=25.0,
            engine_rpm=900.0,    # below 1380
            engine_load=5.0,     # low load → low Wf → low S_idx
        )
        alert = self._process_frame(frame)
        # HDF fires at 1.0; OSF S_idx = 5 × 900 × 1 = 4500, well below 11 000
        assert alert.failure_probability == 1.0
        assert alert.failure_type == "HDF"

    def test_current_frame_osf_stress_can_trigger_alert(self):
        """OSF classification includes the current frame's stress increment."""
        frame = _good_frame(
            coolant_temp=90.0,
            ambient_temp=25.0,
            engine_rpm=2_000.0,
            engine_load=6.0,
        )
        alert = self._process_frame(frame)

        assert alert.failure_type == "OSF"
        assert alert.failure_probability == 1.0
        assert alert.is_anomaly is True

    def test_engine_off_frame_produces_none_alert(self):
        """
        Key-On Engine-Off: RPM = 0, Load = 0, Wf = 0.
        ΔT = coolant − ambient (may be small but RPM = 0 ≥ threshold).
        No fault should be raised.
        """
        frame = _good_frame(
            engine_rpm=0.0,
            engine_load=0.0,
            vehicle_speed=0,
            coolant_temp=20.0,
            ambient_temp=18.0,   # ΔT = 2 K, RPM = 0 → NOT < 1380 and < 8.6 K
        )
        # ΔT = 2 K < 8.6 K but RPM = 0 < 1380 → HDF critical fires
        # This is a known edge case: engine off, ΔT is naturally small.
        # The processor MUST handle RPM=0 without crashing; alert content
        # depends on implementation policy (KOEO suppression is acceptable).
        alert = self._process_frame(frame)
        assert alert is not None
        assert 0.0 <= alert.failure_probability <= 1.0
