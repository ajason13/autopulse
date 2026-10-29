from autopulse.analysis.utils import (
    HDF_DELTA_T_THRESHOLD_K,
    HDF_RPM_THRESHOLD,
    PROB_CRITICAL,
    MAX_COOLANT_RATE_PER_SECOND,
    sigmoid,
)


class HDFDetector:
    """
    Armed synthetic HDF experiment, not a calibrated vehicle failure model.

    Use update() for eligibility-aware scoring. compute_probability() retains
    the legacy pure equation for already-eligible synthetic inputs only.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.armed = False
        self.score = 0.0

    def update(
        self, *, raw_rpm: float, raw_delta_t: float | None,
        smoothed_delta_t: float | None, smoothed_rpm: float,
    ) -> float:
        """Score one accepted frame, then arm only for the following frame.

        Processor sensor/time guards must pass before calling. Raw engine-off
        and missing ambient disarm immediately; warm-up requires both raw and
        smoothed deltas >=15 K. This is a fixture rule, not physical warmth.
        Direct callers must reset at session boundaries.
        """
        self.score = 0.0
        if raw_rpm == 0 or raw_delta_t is None or smoothed_delta_t is None:
            self.armed = False
        elif self.armed:
            self.score = self.compute_probability(smoothed_delta_t, smoothed_rpm)
        else:
            self.armed = raw_delta_t >= 15.0 and smoothed_delta_t >= 15.0
        return self.score

    @staticmethod
    def detect_thermal_rate_anomaly(
        prev_temp: float, curr_temp: float, elapsed_seconds: float
    ) -> bool:
        """True if ΔT/Δt exceeds the existing software guard (5 °C/s)."""
        if elapsed_seconds <= 0:
            raise ValueError("elapsed_seconds must be positive.")
        rate = abs(curr_temp - prev_temp) / elapsed_seconds
        return rate > MAX_COOLANT_RATE_PER_SECOND

    @staticmethod
    def compute_probability(
        delta_t: float,
        rpm: float,
        k_dt: float = 0.8,
        k_rpm: float = 0.003,
    ) -> float:
        """
        Return an uncalibrated synthetic score for eligible inputs.
        Critical path (AI4I trigger): ΔT < 8.6 K AND RPM < 1380 → 1.0
        Anomaly path: sigmoid applied to distance from threshold.
        """
        if delta_t < HDF_DELTA_T_THRESHOLD_K and rpm < HDF_RPM_THRESHOLD:
            return PROB_CRITICAL

        # Anomaly threshold: start warning when delta_t is below 15.0 K
        # As delta_t drops, (15.0 - delta_t) increases, rising p_dt
        p_dt = sigmoid(15.0 - delta_t, 0.0, k_dt)
        p_rpm = sigmoid(HDF_RPM_THRESHOLD - rpm, 0.0, k_rpm)

        # Combined probability (capped at 0.99 for non-critical)
        return max(0.0, min(0.99, p_dt * p_rpm))
