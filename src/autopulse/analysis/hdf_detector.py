from autopulse.analysis.utils import (
    HDF_DELTA_T_THRESHOLD_K,
    HDF_RPM_THRESHOLD,
    PROB_CRITICAL,
    MAX_COOLANT_RATE_PER_SECOND,
    sigmoid,
)


class HDFDetector:
    """
    Heat Dissipation Failure (HDF) Detection Logic.
    Based on AI4I 2020 dataset and US-003 specification.
    """

    @staticmethod
    def detect_thermal_rate_anomaly(
        prev_temp: float, curr_temp: float, elapsed_seconds: float
    ) -> bool:
        """True if ΔT/Δt exceeds the physics-derived guard rail (5 °C/s)."""
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
        Return HDF failure_probability.
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
