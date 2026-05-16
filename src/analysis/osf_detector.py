import math
from src.analysis.utils import (
    OSF_LIMITS,
    LUGGING_RPM_CEILING,
    LUGGING_LOAD_FLOOR,
    PROB_CRITICAL,
    VehicleClass,
    sigmoid,
)


class OSFDetector:
    """
    Overstrain Failure (OSF) Detection Logic.
    Based on cumulative stress index and AI4I 2020 dataset.
    """

    def __init__(self, vehicle_class: VehicleClass = "L"):
        self.vehicle_class = vehicle_class
        self.limit = OSF_LIMITS[vehicle_class]
        self.s_idx = 0.0

    def compute_stress_increment(
        self,
        load_pct: float,
        rpm: float,
        elapsed_seconds: float,
        lugging_k: float = 0.3,
    ) -> float:
        """
        Cumulative stress index S_idx = ∫ (Wf · γ) dt.
        γ (lugging penalty) is exponential when RPM < 1500 and load > 80 %.
        """
        if elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be non-negative.")

        wf = load_pct * rpm
        is_lugging = rpm < LUGGING_RPM_CEILING and load_pct > LUGGING_LOAD_FLOOR
        gamma = math.exp(lugging_k) if is_lugging else 1.0
        return wf * gamma * elapsed_seconds

    def update_stress_index(self, increment: float) -> None:
        """Update the cumulative stress index."""
        self.s_idx += increment

    def classify(self) -> str:
        """Map S_idx to 'NONE', 'OSF_ANOMALY', or 'OSF'."""
        if self.s_idx >= self.limit:
            return "OSF"
        if self.s_idx >= 0.8 * self.limit:
            return "OSF_ANOMALY"
        return "NONE"

    def compute_probability(self, k: float = 0.001) -> float:
        """Sigmoid probability anchored at the anomaly lower bound."""
        anomaly_lo = 0.8 * self.limit
        if self.s_idx >= self.limit:
            return PROB_CRITICAL
        return max(0.0, sigmoid(self.s_idx, anomaly_lo, k))

    def reset(self) -> None:
        """Reset the stress index."""
        self.s_idx = 0.0
