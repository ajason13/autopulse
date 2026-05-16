import math
from typing import Literal

VehicleClass = Literal["L", "M", "H"]

OSF_LIMITS: dict[VehicleClass, float] = {
    "L": 11_000.0,
    "M": 12_000.0,
    "H": 13_000.0,
}

# HDF trigger thresholds (AI4I 2020 → OBD-II mapping)
HDF_DELTA_T_THRESHOLD_K: float = 8.6   # ΔT below which critical HDF fires
HDF_RPM_THRESHOLD: float = 1_380.0     # RPM below which critical HDF fires

# Lugging penalty activation conditions (US-003 §OSF)
LUGGING_RPM_CEILING: float = 1_500.0
LUGGING_LOAD_FLOOR: float = 80.0       # percent

# Rate-of-change guard
MAX_COOLANT_RATE_PER_SECOND: float = 5.0  # °C/s

# Probability Thresholds
PROB_ANOMALY_LO: float = 0.5
PROB_ANOMALY_HI: float = 0.85
PROB_CRITICAL: float = 1.0


def sigmoid(x: float, x0: float, k: float) -> float:
    """Logistic sigmoid as specified in US-003 §Probability Modeling."""
    try:
        val = 1.0 / (1.0 + math.exp(-k * (x - x0)))
        return max(1e-15, min(1.0 - 1e-15, val))
    except OverflowError:
        return 1.0 - 1e-15 if k * (x - x0) > 0 else 1e-15


def compute_z_score(value: float, mean: float, std_dev: float) -> float:
    """Compute the Z-score of a value given mean and standard deviation."""
    if std_dev == 0:
        return 0.0
    return (value - mean) / std_dev


def compute_iqr_bounds(data: list[float]) -> tuple[float, float]:
    """Compute the lower and upper bounds for IQR-based outlier detection."""
    if not data:
        return 0.0, 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)

    def get_quantile(q: float) -> float:
        idx = q * (n - 1)
        low = math.floor(idx)
        high = math.ceil(idx)
        if low == high:
            return sorted_data[int(idx)]
        return sorted_data[low] * (high - idx) + sorted_data[high] * (idx - low)

    q1 = get_quantile(0.25)
    q3 = get_quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr
