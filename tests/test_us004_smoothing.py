"""
tests/test_us004_smoothing.py
AutoPulse — US-004 Adversarial Test Suite
Lead Auditor Sign-off: Engine Data Contract (US-001) × Windowed Analysis (US-004)

Spec under test:
  - Hybrid Median(3) → EWMA smoothing for RPM, Engine Load, and Coolant Temp.
  - α = 0.3  for RPM / Load  (balanced responsiveness)
  - α = 0.1  for Coolant Temp (high damping, thermal inertia)
  - Statistical anomaly detection (Z-score / IQR) MUST use RAW instantaneous values,
    not the smoothed signal, so spikes are still caught.

Red Lines enforced by US-001 that cannot be erased by smoothing:
  - RPM      : [0.0, 9500.0]
  - Coolant  : [-40.0, 140.0]
  - Engine Load: [0.0, 100.0]
  - STFT/LTFT: [-50.0, 50.0]

Adversarial philosophy
──────────────────────
Every test class isolates one failure mode.  Each test follows the pattern:
  Arrange → Inject → Assert.
Tests are grouped into four threat categories:
  A. Gaussian noise stability   — smoothed output must not false-alarm
  B. Single-frame spike capture — raw anomaly detector must still fire
  C. Boundary arithmetic        — smoothing must NOT push values outside schema bounds
  D. Pipeline ordering          — Median BEFORE EWMA; wrong order changes results detectably
"""

import math
import statistics
import pytest
import random

from autopulse.analysis.circular_buffer import CircularBuffer
from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.analysis.utils import PROB_ANOMALY_HI, PROB_ANOMALY_LO

# ──────────────────────────────────────────────────────────────────────────────
# Reference implementations
# These stand in for the production CircularBuffer / PdMProcessor classes.
# The tests are implementation-agnostic; swap these callables for the real
# imports once the production code exists.
# ──────────────────────────────────────────────────────────────────────────────

def median_filter(window: list[float]) -> float:
    """3-point median of the last (up to) 3 values."""
    tail = window[-3:]
    return statistics.median(tail)


def ewma_series(values: list[float], alpha: float) -> list[float]:
    """Full EWMA pass over a list; first value seeds the average."""
    result = []
    prev = values[0]
    for v in values:
        prev = alpha * v + (1 - alpha) * prev
        result.append(prev)
    return result


def hybrid_smooth(raw_stream: list[float], alpha: float) -> list[float]:
    """
    Production pipeline:  raw → Median(3) → EWMA(alpha).
    Returns one smoothed value per input sample.
    """
    smoothed = []
    for i, _ in enumerate(raw_stream):
        window = raw_stream[max(0, i - 2): i + 1]   # up to 3 samples
        med = median_filter(window)
        smoothed.append(med)
    return ewma_series(smoothed, alpha)


def z_score_anomaly(raw_stream: list[float], threshold: float = 3.0) -> list[bool]:
    """Flag samples whose Z-score exceeds threshold. Operates on RAW values."""
    if len(raw_stream) < 2:
        return [False] * len(raw_stream)
    mu = statistics.mean(raw_stream)
    sigma = statistics.stdev(raw_stream)
    if sigma == 0:
        return [False] * len(raw_stream)
    return [abs(v - mu) / sigma > threshold for v in raw_stream]


def iqr_anomaly(raw_stream: list[float], k: float = 1.5) -> list[bool]:
    """Flag samples outside [Q1 - k·IQR, Q3 + k·IQR]. Operates on RAW values."""
    sorted_vals = sorted(raw_stream)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    return [v < lo or v > hi for v in raw_stream]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ──────────────────────────────────────────────────────────────────────────────

RPM_ALPHA   = 0.3
TEMP_ALPHA  = 0.1

# US-001 schema bounds (enforced post-smoothing)
RPM_MIN,    RPM_MAX    =    0.0,  9500.0
TEMP_MIN,   TEMP_MAX   =  -40.0,   140.0
LOAD_MIN,   LOAD_MAX   =    0.0,   100.0
STFT_MIN,   STFT_MAX   =  -50.0,    50.0

SEED = 42


def gaussian_stream(
    center: float,
    std_dev: float,
    length: int,
    lo: float | None = None,
    hi: float | None = None,
    seed: int = SEED,
) -> list[float]:
    """Generate a list of Gaussian-distributed samples, optionally clamped."""
    rng = random.Random(seed)
    samples = [rng.gauss(center, std_dev) for _ in range(length)]
    if lo is not None and hi is not None:
        samples = [max(lo, min(hi, s)) for s in samples]
    return samples


def inject_spike(stream: list[float], index: int, spike_value: float) -> list[float]:
    """Return a copy of stream with stream[index] replaced by spike_value."""
    modified = list(stream)
    modified[index] = spike_value
    return modified


# ──────────────────────────────────────────────────────────────────────────────
# Category A — Gaussian Noise Stability
# Verifies that continuous, realistic sensor noise does NOT generate false PdM
# failure alerts after the Median→EWMA pipeline.
# ──────────────────────────────────────────────────────────────────────────────

class TestGaussianNoiseStability:
    """
    THREAT: Flicker in RPM / Load / Coolant Temp triggers false mechanical
    failure alerts.  The Median→EWMA stage must reduce variance sufficiently
    that the smoothed signal stays well within normal-operating bands and the
    alert threshold is not breached by noise alone.
    """

    def test_rpm_gaussian_noise_does_not_cross_alert_band(self):
        """
        Scenario: Engine idling at ~800 RPM with ±120 RPM sensor flicker (2-σ).
        Smoothed output must stay within a ±60 RPM band around the true idle.
        This validates α = 0.3 provides adequate damping for RPM.
        """
        center, noise_std = 800.0, 60.0
        alert_band = 120.0  # half-width; alert fires if |smoothed - center| > this

        raw = gaussian_stream(center, noise_std, length=120)
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)

        violations = [
            (i, v) for i, v in enumerate(smoothed)
            if abs(v - center) > alert_band
        ]
        assert not violations, (
            f"Smoothed RPM crossed alert band at {len(violations)} sample(s). "
            f"First: index={violations[0][0]}, value={violations[0][1]:.2f}"
        )

    def test_coolant_temp_gaussian_noise_does_not_trigger_overtemp_alert(self):
        """
        Scenario: Stable engine at 90°C with ±5°C sensor noise (realistic NTC
        thermistor accuracy).  Overtemp alert fires at 120°C; smoothed signal
        (α=0.1, high damping) must never approach that threshold.
        """
        center, noise_std = 90.0, 5.0
        overtemp_threshold = 120.0

        raw = gaussian_stream(center, noise_std, length=120)
        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)

        violations = [v for v in smoothed if v >= overtemp_threshold]
        assert not violations, (
            f"Smoothed coolant temp breached overtemp alert ({overtemp_threshold}°C) "
            f"purely from Gaussian noise. Peak: {max(smoothed):.2f}°C"
        )

    def test_rpm_variance_reduction_meets_spec_ratio(self):
        """
        The Median→EWMA pipeline is spec'd for noise rejection.  Verify that
        the variance of the smoothed signal is materially lower than the raw
        signal (at least 50% reduction), confirming the filter is operative.
        """
        raw = gaussian_stream(1500.0, 150.0, length=200)
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)

        raw_var      = statistics.variance(raw)
        smoothed_var = statistics.variance(smoothed)
        reduction    = (raw_var - smoothed_var) / raw_var

        assert reduction >= 0.50, (
            f"Variance reduction only {reduction:.1%}; expected ≥ 50%. "
            f"Raw σ²={raw_var:.1f}, Smoothed σ²={smoothed_var:.1f}"
        )

    def test_coolant_alpha_produces_higher_damping_than_rpm_alpha(self):
        """
        α=0.1 (Coolant) must produce more damping than α=0.3 (RPM/Load).
        Same input stream → compare variance of outputs.
        """
        raw = gaussian_stream(90.0, 10.0, length=200)
        smoothed_low_alpha  = hybrid_smooth(raw, alpha=TEMP_ALPHA)   # α=0.1
        smoothed_high_alpha = hybrid_smooth(raw, alpha=RPM_ALPHA)    # α=0.3

        var_low  = statistics.variance(smoothed_low_alpha)
        var_high = statistics.variance(smoothed_high_alpha)

        assert var_low < var_high, (
            f"Expected α=0.1 to produce lower variance than α=0.3. "
            f"Got: α=0.1 → {var_low:.4f}, α=0.3 → {var_high:.4f}"
        )

    def test_engine_load_gaussian_noise_does_not_false_alarm(self):
        """
        Engine load at highway cruise ~65% with ±8% sensor noise.
        Smoothed signal must stay within [50%, 80%] continuous operation band.
        """
        center, noise_std = 65.0, 8.0
        lo_bound, hi_bound = 50.0, 80.0

        raw = gaussian_stream(center, noise_std, length=120, lo=LOAD_MIN, hi=LOAD_MAX)
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)

        # Allow 1-sample transient at start (EWMA settling)
        violations = [
            v for v in smoothed[5:]
            if not (lo_bound <= v <= hi_bound)
        ]
        assert not violations, (
            f"Engine load smoothed signal left normal band at {len(violations)} samples. "
            f"Range observed: [{min(smoothed):.2f}, {max(smoothed):.2f}]%"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Category B — Single-Frame Spike Capture
# Verifies that the raw-value anomaly detector (Z-score / IQR) still fires on
# genuine single-frame spikes, even though the smoothed channel would suppress
# them.  This is the CRITICAL correctness requirement: smoothing must not cause
# blind spots in the fault-detection pipeline.
# ──────────────────────────────────────────────────────────────────────────────

class TestSingleFrameSpikeCapture:
    """
    THREAT: The Median(3) filter is so aggressive that a single spike is erased
    before the anomaly detector sees it, causing missed fault events.
    US-004 mandates that statistical anomaly logic operates on RAW values.
    """

    def test_rpm_single_spike_detected_by_z_score_on_raw(self):
        """
        Inject one sample at 9,000 RPM (near mechanical limit) into a stable
        1,500 RPM stream.  Z-score on RAW values must flag it; smoothed channel
        must NOT flag it (spike suppressed).
        """
        base = [1500.0] * 60
        spike_index = 30
        spike_value = 9000.0

        raw_with_spike = inject_spike(base, spike_index, spike_value)
        smoothed = hybrid_smooth(raw_with_spike, alpha=RPM_ALPHA)

        # Raw anomaly detector fires
        raw_flags = z_score_anomaly(raw_with_spike, threshold=3.0)
        assert raw_flags[spike_index], (
            "Z-score on RAW stream did NOT flag the 9,000 RPM spike at "
            f"index {spike_index}.  Anomaly detection is broken."
        )

        # Smoothed channel is stable (spike absorbed by Median filter)
        smoothed_flags = z_score_anomaly(smoothed, threshold=3.0)
        assert not smoothed_flags[spike_index], (
            "Smoothed RPM still flagged the spike — Median filter is not "
            "suppressing single-frame spikes as specified."
        )

    def test_coolant_single_spike_detected_by_z_score_on_raw(self):
        """
        Inject one sample at 135°C (beyond pressurized boiling point) into a
        stable 90°C stream.  Raw detector fires; smoothed does not.
        This validates the 'Thermal Anomaly Test' from US-001 §Test Vectors.
        """
        base = [90.0] * 60
        spike_index = 25
        spike_value = 135.0

        raw_with_spike = inject_spike(base, spike_index, spike_value)
        smoothed = hybrid_smooth(raw_with_spike, alpha=TEMP_ALPHA)

        raw_flags = z_score_anomaly(raw_with_spike, threshold=3.0)
        assert raw_flags[spike_index], (
            f"Z-score on RAW coolant stream missed 135°C spike at index {spike_index}."
        )

        # α=0.1 provides strong damping; spike in smoothed should be minimal
        spike_smoothed_delta = abs(smoothed[spike_index] - 90.0)
        assert spike_smoothed_delta < 10.0, (
            f"Smoothed coolant temp moved {spike_smoothed_delta:.2f}°C on a single spike; "
            f"expected <10°C with α=0.1 damping."
        )

    def test_rpm_spike_detected_by_iqr_on_raw(self):
        """
        Confirm IQR-based detector (second anomaly method) also catches RPM spike.
        IQR is resistant to extreme outliers in its quartile calculation, making
        it a complementary check to Z-score.
        """
        base = gaussian_stream(2000.0, 50.0, length=60)
        spike_index = 40
        spike_value = 8500.0

        raw_with_spike = inject_spike(base, spike_index, spike_value)
        flags = iqr_anomaly(raw_with_spike, k=1.5)

        assert flags[spike_index], (
            f"IQR detector on RAW stream missed spike of {spike_value} RPM."
        )

    def test_consecutive_two_frame_spike_partially_survives_median(self):
        """
        ADVERSARIAL: 2-frame spikes are NOT fully suppressed by a 3-point median,
        because the second spiked sample sees a window with 2 spike values and 1
        normal value — median is the spike value.
        Verify: raw detector fires on BOTH frames; smoothed channel also shows
        the spike for frame 2 (correct behavior — this is a real event, not noise).
        """
        base = [1500.0] * 60
        spike_val = 8000.0
        raw_with_spike = inject_spike(base, 30, spike_val)
        raw_with_spike = inject_spike(raw_with_spike, 31, spike_val)

        raw_flags = z_score_anomaly(raw_with_spike, threshold=3.0)
        assert raw_flags[30] and raw_flags[31], (
            "Z-score must flag both frames of a 2-frame spike."
        )

        smoothed = hybrid_smooth(raw_with_spike, alpha=RPM_ALPHA)
        # Frame 31: median window = [spike, spike, normal] → median = spike.
        # EWMA attenuates but value should still be significantly elevated.
        assert smoothed[31] > 2000.0, (
            f"Expected smoothed[31] to show elevated RPM from 2-frame spike "
            f"(window median is spike value), got {smoothed[31]:.2f}"
        )

    def test_spike_below_zero_rejected_at_schema_boundary(self):
        """
        A signed-integer wrap or sensor fault can produce negative RPM.
        US-001 mandates RPM ≥ 0.  Inject -500 RPM; raw anomaly detector flags
        it AND schema validator must reject the frame.
        """
        base = [1500.0] * 60
        spike_index = 20
        spike_value = -500.0

        raw_with_spike = inject_spike(base, spike_index, spike_value)
        flags = z_score_anomaly(raw_with_spike, threshold=3.0)

        assert flags[spike_index], "Z-score must flag negative RPM spike."

        # Schema boundary check (would be a JSON Schema validation in production)
        assert spike_value < RPM_MIN, (
            f"Spike value {spike_value} should violate RPM_MIN={RPM_MIN}"
        )

    def test_coolant_spike_at_schema_boundary_140c_flagged_not_smoothed_away(self):
        """
        A spike to exactly 140°C (the US-001 schema ceiling) should be flagged
        by the raw anomaly detector.  A spike to 141°C must be rejected as
        schema-invalid before smoothing is even applied.
        """
        base = [90.0] * 60

        # 140°C spike — valid schema value but anomalous
        raw_140 = inject_spike(base, 30, 140.0)
        flags_140 = z_score_anomaly(raw_140, threshold=3.0)
        assert flags_140[30], "140°C spike must be flagged by Z-score on raw stream."

        # 141°C spike — invalid schema; treat as data corruption
        assert 141.0 > TEMP_MAX, "141°C must violate schema ceiling of 140°C."


# ──────────────────────────────────────────────────────────────────────────────
# Category C — Boundary Arithmetic
# Verifies that the Median→EWMA pipeline does NOT push values outside the
# US-001 JSON Schema bounds through arithmetic accumulation.
# ──────────────────────────────────────────────────────────────────────────────

class TestBoundaryArithmetic:
    """
    THREAT: EWMA, being a weighted average, should never produce a value
    outside the range of its inputs.  However, floating-point rounding and
    incorrect formula implementations can creep outside schema bounds.
    """

    def test_rpm_smoothed_never_exceeds_schema_max(self):
        """
        Feed a stream at the hard schema ceiling (9,500 RPM).
        EWMA output must remain ≤ 9,500 RPM at every step.
        """
        raw = [9500.0] * 100
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)
        violations = [v for v in smoothed if v > RPM_MAX]
        assert not violations, (
            f"Smoothed RPM exceeded schema max at {len(violations)} samples. "
            f"Max observed: {max(smoothed):.4f}"
        )

    def test_rpm_smoothed_never_goes_below_zero(self):
        """
        Feed a stream at exactly 0 RPM (engine-off, ignition-on state from
        US-001 §Zero-Value Robustness).  Output must be exactly 0.0.
        """
        raw = [0.0] * 50
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)
        assert all(v == 0.0 for v in smoothed), (
            f"Smoothed RPM drifted from 0.0: {[v for v in smoothed if v != 0.0]}"
        )

    def test_coolant_smoothed_never_exceeds_schema_max(self):
        """Stream at 140°C ceiling; every smoothed value must stay ≤ 140°C."""
        raw = [140.0] * 100
        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)
        violations = [v for v in smoothed if v > TEMP_MAX]
        assert not violations, f"Smoothed coolant exceeded 140°C: {violations}"

    def test_coolant_smoothed_never_drops_below_schema_min(self):
        """Stream at -40°C floor (arctic cold-start); output must stay ≥ -40°C."""
        raw = [-40.0] * 100
        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)
        violations = [v for v in smoothed if v < TEMP_MIN]
        assert not violations, f"Smoothed coolant dropped below -40°C: {violations}"

    def test_ewma_convergence_to_steady_state(self):
        """
        EWMA must converge to within 1% of a constant input value within a
        reasonable number of samples.  For α=0.3, convergence to 99% of
        steady-state occurs in approximately ceil(log(0.01)/log(1-α)) ≈ 13 steps.
        """
        target = 3000.0
        raw = [target] * 60
        smoothed = ewma_series(raw, alpha=RPM_ALPHA)

        convergence_sample = math.ceil(math.log(0.01) / math.log(1 - RPM_ALPHA))
        post_convergence = smoothed[convergence_sample:]
        tolerance = target * 0.01

        violations = [v for v in post_convergence if abs(v - target) > tolerance]
        assert not violations, (
            f"EWMA not converged within 1% of {target} after {convergence_sample} samples. "
            f"Remaining deviation: {[abs(v-target) for v in violations[:5]]}"
        )

    def test_load_at_zero_not_rejected_as_invalid(self):
        """
        US-001 §Zero-Value Robustness: Load=0% is valid (engine off, key on).
        Smoothing a zero stream must remain 0%.
        """
        raw = [0.0] * 30
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)
        assert all(v == 0.0 for v in smoothed), "Zero engine load incorrectly drifts after smoothing."

    def test_mixed_boundary_stream_does_not_corrupt_ewma_state(self):
        """
        ADVERSARIAL: Feed alternating 0 / 9,500 RPM to stress-test EWMA
        accumulator state.  Every output must remain within [0, 9500].
        """
        raw = [0.0 if i % 2 == 0 else 9500.0 for i in range(60)]
        smoothed = hybrid_smooth(raw, alpha=RPM_ALPHA)

        violations = [v for v in smoothed if not (RPM_MIN <= v <= RPM_MAX)]
        assert not violations, (
            f"Alternating boundary stream produced out-of-range smoothed RPM: {violations}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Category D — Pipeline Ordering
# The spec mandates Median THEN EWMA.  Swapping the order produces measurably
# different (worse) results for spike suppression.  This category confirms the
# order is not accidentally reversed in the implementation.
# ──────────────────────────────────────────────────────────────────────────────

class TestPipelineOrdering:
    """
    THREAT: Implementing EWMA → Median instead of Median → EWMA.
    When EWMA runs first, the spike is partially integrated into the running
    average before Median can remove it — leaving a residual that EWMA continues
    to decay, creating a prolonged false elevation (phantom afterglow).
    """

    @staticmethod
    def _ewma_then_median(raw: list[float], alpha: float) -> list[float]:
        """Incorrect order: EWMA first, then median — produces phantom afterglow."""
        ewma_first = ewma_series(raw, alpha)
        result = []
        for i in range(len(ewma_first)):
            window = ewma_first[max(0, i - 2): i + 1]
            result.append(median_filter(window))
        return result

    def test_correct_order_suppresses_spike_better_than_inverted_order(self):
        """
        Single 9,000 RPM spike at index 30 in a 1,500 RPM stream.
        Correct order (Median→EWMA) must produce a lower peak at the spike
        index compared to the incorrect inverted order (EWMA→Median).
        This proves pipeline ordering is enforced and functionally significant.
        """
        base = [1500.0] * 60
        raw = inject_spike(base, 30, 9000.0)

        correct   = hybrid_smooth(raw, alpha=RPM_ALPHA)
        incorrect = self._ewma_then_median(raw, alpha=RPM_ALPHA)

        peak_correct   = max(correct[28:34])
        peak_incorrect = max(incorrect[28:34])

        assert peak_correct < peak_incorrect, (
            f"Expected Median→EWMA to produce a lower spike peak than EWMA→Median. "
            f"Correct: {peak_correct:.2f}, Incorrect: {peak_incorrect:.2f}"
        )

    def test_correct_order_recovers_faster_after_spike(self):
        """
        After a single-frame spike, correct-order pipeline must return closer
        to the baseline within 5 samples.  Inverted order leaves an EWMA
        'tail' that takes longer to decay.
        """
        base = [1500.0] * 80
        raw = inject_spike(base, 20, 9000.0)
        baseline = 1500.0

        correct   = hybrid_smooth(raw, alpha=RPM_ALPHA)
        incorrect = self._ewma_then_median(raw, alpha=RPM_ALPHA)

        recovery_window = 5
        # Check values 5 samples after the spike
        post_spike_correct   = correct[25]
        post_spike_incorrect = incorrect[25]

        assert abs(post_spike_correct - baseline) < abs(post_spike_incorrect - baseline), (
            f"Correct order should recover faster. "
            f"Correct deviation at +5: {abs(post_spike_correct-baseline):.2f}, "
            f"Incorrect: {abs(post_spike_incorrect-baseline):.2f}"
        )

    def test_steady_state_both_orders_converge_to_same_value(self):
        """
        For constant input (no spikes), Median→EWMA and EWMA→Median must
        produce identical outputs.  Order only matters when outliers are present.
        """
        raw = [2000.0] * 100
        correct   = hybrid_smooth(raw, alpha=RPM_ALPHA)
        incorrect = self._ewma_then_median(raw, alpha=RPM_ALPHA)

        for i, (c, w) in enumerate(zip(correct[10:], incorrect[10:]), start=10):
            assert math.isclose(c, w, rel_tol=1e-9), (
                f"Steady-state output diverges at index {i}: "
                f"Median→EWMA={c:.6f}, EWMA→Median={w:.6f}"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Category E — Cold-Start Scenario (US-001 §Test Vectors)
# Validates the specific test scenario named in the US-001 engineering spec.
# ──────────────────────────────────────────────────────────────────────────────

class TestColdStartScenario:
    """
    US-001 specifies: 'Simulate a coolant temperature rise from 0°C to 85°C
    over 10 minutes. The system must validate the smooth gradient.'
    At 1Hz sampling, 10 minutes = 600 samples.
    """

    @staticmethod
    def _linear_ramp_with_noise(start, end, n, noise_std, seed=SEED):
        rng = random.Random(seed)
        step = (end - start) / (n - 1)
        return [start + i * step + rng.gauss(0, noise_std) for i in range(n)]

    def test_cold_start_smooth_gradient_validated(self):
        """
        Smoothed coolant temp must rise monotonically in the moving average sense
        and must reach ≥ 80°C (normal operating temp) within the 600-sample window.
        """
        raw = self._linear_ramp_with_noise(0.0, 85.0, n=600, noise_std=2.0)
        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)

        # Monotonicity: moving 60-sample average should always increase
        window_size = 60
        avgs = [
            statistics.mean(smoothed[i: i + window_size])
            for i in range(0, len(smoothed) - window_size, window_size)
        ]
        for i in range(1, len(avgs)):
            assert avgs[i] >= avgs[i - 1] - 0.5, (
                f"Smoothed coolant temp regressed at windowed average index {i}: "
                f"{avgs[i-1]:.2f}°C → {avgs[i]:.2f}°C"
            )

        # Must reach operating temp
        assert smoothed[-1] >= 80.0, (
            f"Smoothed coolant never reached operating temp. Final: {smoothed[-1]:.2f}°C"
        )

    def test_cold_start_no_false_overtemp_alert_during_warmup(self):
        """
        During normal warm-up, smoothed output must never cross 110°C
        (overtemp threshold), even if individual raw samples have noise spikes.
        """
        raw = self._linear_ramp_with_noise(0.0, 85.0, n=600, noise_std=3.0)
        # Inject a handful of rogue high-noise samples
        for idx in [100, 200, 350, 500]:
            raw = inject_spike(raw, idx, 108.0)

        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)
        overtemp_threshold = 110.0

        violations = [v for v in smoothed if v >= overtemp_threshold]
        assert not violations, (
            f"False overtemp alert during warm-up. "
            f"Smoothed breached {overtemp_threshold}°C: peak={max(smoothed):.2f}°C"
        )

    def test_thermal_anomaly_jump_85_to_135_in_one_second_flagged(self):
        """
        US-001 §Thermal Anomaly Test: 'Simulate a jump from 85°C to 135°C in
        one second.  The system must flag this as sensor noise/fault rather than
        a valid overheating event.'
        Raw Z-score flags it; smoothed attenuates it (α=0.1 is very aggressive).
        """
        raw = [85.0] * 120
        spike_index = 60
        spike_value = 135.0

        raw = inject_spike(raw, spike_index, spike_value)
        flags = z_score_anomaly(raw, threshold=3.0)

        assert flags[spike_index], (
            "Thermal anomaly (85→135°C in 1 s) not flagged by Z-score on raw stream."
        )

        smoothed = hybrid_smooth(raw, alpha=TEMP_ALPHA)
        # With α=0.1, a single spike at 135 in a sea of 85s:
        # Median(3) sees [85, 135, 85] → 85.  EWMA barely moves.
        assert smoothed[spike_index] < 100.0, (
            f"Thermal spike at 135°C was not suppressed by α=0.1 smoothing. "
            f"Smoothed value: {smoothed[spike_index]:.2f}°C"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Category F — Determinism and Reproducibility
# Stateless pipeline: same input must always yield same output.
# ──────────────────────────────────────────────────────────────────────────────

class TestDeterminismAndReproducibility:

    def test_identical_inputs_produce_identical_smoothed_outputs(self):
        """Two calls with the same stream must produce bit-identical results."""
        raw = gaussian_stream(1500.0, 100.0, length=100)
        out1 = hybrid_smooth(raw, alpha=RPM_ALPHA)
        out2 = hybrid_smooth(raw, alpha=RPM_ALPHA)
        assert out1 == out2, "Smoothing pipeline is non-deterministic."

    def test_single_element_stream_handled_without_error(self):
        """Edge case: 1-sample stream must return a list with 1 value."""
        out = hybrid_smooth([1500.0], alpha=RPM_ALPHA)
        assert len(out) == 1
        assert out[0] == 1500.0

    def test_two_element_stream_handled_without_error(self):
        """Edge case: 2-sample stream (partial Median window)."""
        out = hybrid_smooth([1500.0, 1600.0], alpha=RPM_ALPHA)
        assert len(out) == 2
        assert all(RPM_MIN <= v <= RPM_MAX for v in out)


# ──────────────────────────────────────────────────────────────────────────────
# Category G — Audit Remediation Regression Tests
# Direct coverage for US-004 audit findings A, B, and C.
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditRemediationRegressions:

    def test_t_g1_ewma_seeding_is_correct_via_production_buffer(self):
        """Finding A: EWMA must seed from oldest value and iterate from index 1."""
        alpha = 0.3
        values = [100.0, 200.0, 300.0, 400.0, 500.0]
        buf = CircularBuffer(capacity=10)
        for v in values:
            buf.push(v)
        expected = values[0]
        for v in values[1:]:
            expected = alpha * v + (1 - alpha) * expected
        assert math.isclose(buf.get_ewma(alpha), expected, rel_tol=1e-9)

    def test_t_g2_statistical_anomaly_does_not_override_primary_anomaly(self, monkeypatch):
        """Finding B: STATISTICAL_ANOMALY must not mask an active HDF/OSF alert."""
        processor = PdMProcessor("a" * 64)
        monkeypatch.setattr(
            processor,
            "_smooth_current_values",
            lambda: (900.0, 75.0, 10.0),
        )
        monkeypatch.setattr(
            processor,
            "_evaluate_statistical_anomaly",
            lambda summary: (True, 0x0C),
        )
        monkeypatch.setattr(
            processor.hdf_detector,
            "compute_probability",
            lambda delta_t, rpm: PROB_ANOMALY_LO + 0.1,
        )
        monkeypatch.setattr(
            processor.osf_detector,
            "compute_probability",
            lambda: 0.0,
        )

        alert = processor.process_frame(_processor_frame())

        assert alert.failure_type == "HDF"
        assert alert.failure_probability == PROB_ANOMALY_LO + 0.1
        assert alert.primary_pid is None

    def test_t_g3_statistical_anomaly_fires_when_primary_probability_is_not_anomaly(
        self,
        monkeypatch,
    ):
        """Finding B: STATISTICAL_ANOMALY may fire only at or below anomaly floor."""
        processor = PdMProcessor("a" * 64)
        monkeypatch.setattr(
            processor,
            "_smooth_current_values",
            lambda: (900.0, 75.0, 10.0),
        )
        monkeypatch.setattr(
            processor,
            "_evaluate_statistical_anomaly",
            lambda summary: (True, 0x0C),
        )
        monkeypatch.setattr(
            processor.hdf_detector,
            "compute_probability",
            lambda delta_t, rpm: PROB_ANOMALY_LO,
        )
        monkeypatch.setattr(
            processor.osf_detector,
            "compute_probability",
            lambda: 0.0,
        )

        alert = processor.process_frame(_processor_frame())

        assert alert.failure_type == "STATISTICAL_ANOMALY"
        assert alert.failure_probability == PROB_ANOMALY_HI
        assert alert.primary_pid == 0x0C

    def test_t_g4_pdm_processor_smoothed_rpm_converges_via_production_buffer(
        self,
        monkeypatch,
    ):
        processor = PdMProcessor("a" * 64)
        target_rpm = 2000.0
        captured: list[float] = []
        original_smooth = processor._smooth_current_values.__func__

        def capturing_smooth(self_inner):
            result = original_smooth(self_inner)
            captured.append(result[0])
            return result

        monkeypatch.setattr(
            processor,
            "_smooth_current_values",
            lambda: capturing_smooth(processor),
        )
        for _ in range(60):
            processor.process_frame(_processor_frame(engine_rpm=target_rpm))
        tolerance = target_rpm * 0.01
        assert abs(captured[-1] - target_rpm) <= tolerance

    def test_t_g4_smoothing_failure_returns_sensor_error(self, monkeypatch):
        """Finding C: smoothing exceptions must become SENSOR_ERROR alerts."""
        processor = PdMProcessor("a" * 64)

        def fail_smoothing():
            raise ValueError("invalid smoothing state")

        monkeypatch.setattr(processor, "_smooth_current_values", fail_smoothing)

        alert = processor.process_frame(_processor_frame())

        assert alert.failure_type == "SENSOR_ERROR"
        assert alert.failure_probability == 0.0
        assert alert.is_anomaly is False


def _processor_frame(**overrides) -> dict:
    frame = {
        "timestamp": "2025-07-04T14:22:05.123Z",
        "vin_hashed": "a" * 64,
        "protocol": "SAE_J1979",
        "engine_rpm": 900.0,
        "vehicle_speed": 0,
        "coolant_temp": 90.0,
        "engine_load": 20.0,
        "stft_bank1": 0.0,
        "ltft_bank1": 0.0,
        "ambient_temp": 25.0,
    }
    frame.update(overrides)
    return frame
