from __future__ import annotations

from datetime import datetime
import re
import statistics
import time
from dataclasses import dataclass
from typing import Any, Literal

from src.analysis.circular_buffer import CircularBuffer
from src.analysis.hdf_detector import HDFDetector
from src.analysis.osf_detector import OSFDetector
from src.analysis.utils import (
    compute_iqr_bounds,
    compute_z_score,
    PROB_ANOMALY_LO,
    PROB_ANOMALY_HI,
    VehicleClass,
)

FailureType = Literal[
    "HDF",
    "OSF",
    "OSF_ANOMALY",
    "STATISTICAL_ANOMALY",
    "NONE",
    "SENSOR_ERROR",
]
WindowStatValue = float | bool
WindowSummary = dict[str, dict[str, WindowStatValue]]

_VIN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STATISTICAL_Z_THRESHOLD = 3.0
_PID_ENGINE_RPM = int("0C", 16)
_PID_COOLANT_TEMP = int("05", 16)
_PID_ENGINE_LOAD = int("04", 16)
_PID_BY_SUMMARY_KEY = {
    "engine_rpm": _PID_ENGINE_RPM,
    "coolant_temp": _PID_COOLANT_TEMP,
    "engine_load": _PID_ENGINE_LOAD,
}
_RPM_LOAD_ALPHA = 0.3
_COOLANT_ALPHA = 0.1
_MEDIAN_WINDOW = 3


@dataclass
class PdMAlert:
    """Output schema as defined in US-003 §Output Specification."""
    timestamp: int
    vin_hashed: str
    failure_probability: float
    failure_type: FailureType
    is_anomaly: bool
    primary_pid: int | None = None
    window_summary: WindowSummary | None = None
    obd_frame: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _validate_vin_hash(self.vin_hashed)


class PdMProcessor:
    """
    Main Processor for AutoPulse Anomaly Detection.
    Orchestrates data validation, temporal state, and PdM logic branches.
    """

    def __init__(
        self,
        vin_hashed: str,
        vehicle_class: VehicleClass = "L",
        window_size: int = 60,
    ):
        _validate_vin_hash(vin_hashed)

        self.vin_hashed = vin_hashed
        self.vehicle_class = vehicle_class
        self.window_size = window_size

        # State
        self.rpm_buffer = CircularBuffer(window_size)
        self.coolant_buffer = CircularBuffer(window_size)
        self.load_buffer = CircularBuffer(window_size)
        self._rpm_median_buffer = CircularBuffer(window_size)
        self._coolant_median_buffer = CircularBuffer(window_size)
        self._load_median_buffer = CircularBuffer(window_size)

        self.hdf_detector = HDFDetector()
        self.osf_detector = OSFDetector(vehicle_class)

        self.last_timestamp: float | None = None
        self.last_coolant_temp: float | None = None

    def process_frame(self, frame: dict[str, Any]) -> PdMAlert:
        """
        Execute the 5-step processing sequence for a single OBD frame.
        """
        timestamp_ms = self._parse_timestamp(frame.get("timestamp"))
        curr_time = timestamp_ms / 1000.0

        # Step 1: Validate mandatory PIDs
        missing_pid = self._check_mandatory_pids(frame)
        if missing_pid:
            return PdMAlert(
                timestamp=timestamp_ms,
                vin_hashed=self.vin_hashed,
                failure_probability=0.0,
                failure_type="SENSOR_ERROR",
                is_anomaly=False,
                primary_pid=missing_pid,
                obd_frame=frame
            )

        # Extract values
        rpm = float(frame["engine_rpm"])
        load = float(frame["engine_load"])
        coolant = float(frame["coolant_temp"])
        ambient = frame.get("ambient_temp")
        delta_t = coolant - float(ambient) if ambient is not None else None

        # Temporal delta
        elapsed = 1.0  # Default to 1Hz
        if self.last_timestamp is not None:
            elapsed = max(0.001, curr_time - self.last_timestamp)

        # Rate guard
        if self.last_coolant_temp is not None:
            try:
                if self.hdf_detector.detect_thermal_rate_anomaly(
                    self.last_coolant_temp, coolant, elapsed
                ):
                    return PdMAlert(
                        timestamp=timestamp_ms,
                        vin_hashed=self.vin_hashed,
                        failure_probability=0.0,
                        failure_type="SENSOR_ERROR",
                        is_anomaly=False,
                        primary_pid=_PID_COOLANT_TEMP,
                        obd_frame=frame
                    )
            except ValueError:
                return PdMAlert(
                    timestamp=timestamp_ms,
                    vin_hashed=self.vin_hashed,
                    failure_probability=0.0,
                    failure_type="SENSOR_ERROR",
                    is_anomaly=False,
                    primary_pid=_PID_COOLANT_TEMP,
                    obd_frame=frame
                )

        # Step 2: Update temporal state only after sensor guards pass.
        self.rpm_buffer.push(rpm)
        self.coolant_buffer.push(coolant)
        self.load_buffer.push(load)
        smoothed_rpm, smoothed_coolant, smoothed_load = self._smooth_current_values()
        summary = self._generate_summary()
        stat_anomaly, stat_pid = self._evaluate_statistical_anomaly(summary)

        # Step 3 & 4: Evaluate branches.
        # OSF includes the current frame's stress increment.
        smoothed_delta_t = (
            smoothed_coolant - float(ambient) if ambient is not None else None
        )
        p_hdf = (
            self.hdf_detector.compute_probability(smoothed_delta_t, smoothed_rpm)
            if smoothed_delta_t is not None
            else 0.0
        )
        stress_inc = self.osf_detector.compute_stress_increment(
            smoothed_load, smoothed_rpm, elapsed
        )
        self.osf_detector.update_stress_index(stress_inc)
        p_osf = self.osf_detector.compute_probability()

        # Determine failure types
        hdf_type: FailureType = "HDF" if p_hdf > PROB_ANOMALY_LO else "NONE"
        osf_type = self.osf_detector.classify()

        # Step 5: Select highest probability
        if p_hdf >= p_osf:
            primary_prob = p_hdf
            failure_type = hdf_type
        else:
            primary_prob = p_osf
            failure_type = osf_type

        if stat_anomaly and primary_prob < PROB_ANOMALY_HI:
            primary_prob = PROB_ANOMALY_HI
            failure_type = "STATISTICAL_ANOMALY"

        # Update last state
        self.last_timestamp = curr_time
        self.last_coolant_temp = coolant

        return PdMAlert(
            timestamp=timestamp_ms,
            vin_hashed=self.vin_hashed,
            failure_probability=primary_prob,
            failure_type=failure_type if primary_prob > PROB_ANOMALY_LO else "NONE",
            is_anomaly=primary_prob > PROB_ANOMALY_LO,
            primary_pid=stat_pid if failure_type == "STATISTICAL_ANOMALY" else None,
            window_summary=summary,
            obd_frame=frame
        )

    def _check_mandatory_pids(self, frame: dict[str, Any]) -> int | None:
        """Check if mandatory PIDs exist. Returns the first missing PID hex."""
        if "engine_rpm" not in frame:
            return _PID_ENGINE_RPM
        if "engine_load" not in frame:
            return _PID_ENGINE_LOAD
        if "coolant_temp" not in frame:
            return _PID_COOLANT_TEMP
        return None

    def _parse_timestamp(self, ts: Any) -> int:
        """Parse ISO timestamp or use current time in ms."""
        if not ts:
            return int(time.time() * 1000)
        try:
            # Basic ISO parse if string
            if isinstance(ts, str):
                parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(parsed.timestamp() * 1000)
            return int(ts)
        except (TypeError, ValueError, OverflowError):
            return int(time.time() * 1000)

    def _generate_summary(self) -> WindowSummary:
        """Generate min/max/avg/z-score/iqr summary for the rolling window."""
        res: WindowSummary = {}
        for name, buf in [
            ("engine_rpm", self.rpm_buffer),
            ("coolant_temp", self.coolant_buffer),
            ("engine_load", self.load_buffer),
        ]:
            data = buf.to_list()
            if not data:
                continue

            mean = sum(data) / len(data)
            std_dev = statistics.stdev(data) if len(data) > 1 else 0.0
            iqr_low, iqr_high = compute_iqr_bounds(data)

            res[name] = {
                "min": min(data),
                "max": max(data),
                "avg": mean,
                "std_dev": std_dev,
                "z_score": compute_z_score(data[-1], mean, std_dev),
                "iqr_low": iqr_low,
                "iqr_high": iqr_high,
                "is_statistical_outlier": data[-1] < iqr_low or data[-1] > iqr_high,
            }
        return res

    def _smooth_current_values(self) -> tuple[float, float, float]:
        """
        Apply US-004 Median(3) -> EWMA smoothing for PdM probability branches.

        Raw buffers remain the source of truth for statistical anomaly gates.
        """
        rpm_median = self.rpm_buffer.get_median(_MEDIAN_WINDOW)
        coolant_median = self.coolant_buffer.get_median(_MEDIAN_WINDOW)
        load_median = self.load_buffer.get_median(_MEDIAN_WINDOW)
        if rpm_median is None or coolant_median is None or load_median is None:
            raise RuntimeError("raw buffers must contain current frame values.")

        self._rpm_median_buffer.push(rpm_median)
        self._coolant_median_buffer.push(coolant_median)
        self._load_median_buffer.push(load_median)

        smoothed_rpm = self._rpm_median_buffer.get_ewma(_RPM_LOAD_ALPHA)
        smoothed_coolant = self._coolant_median_buffer.get_ewma(_COOLANT_ALPHA)
        smoothed_load = self._load_median_buffer.get_ewma(_RPM_LOAD_ALPHA)
        if (
            smoothed_rpm is None
            or smoothed_coolant is None
            or smoothed_load is None
        ):
            raise RuntimeError("median buffers must contain current frame values.")

        return smoothed_rpm, smoothed_coolant, smoothed_load

    def _evaluate_statistical_anomaly(
        self,
        summary: WindowSummary,
    ) -> tuple[bool, int | None]:
        """Return whether any PID breaches Z-score or IQR anomaly gates."""
        for name, stats in summary.items():
            z_score = float(stats.get("z_score", 0.0))
            iqr_outlier = bool(stats.get("is_statistical_outlier", False))
            if abs(z_score) > _STATISTICAL_Z_THRESHOLD or iqr_outlier:
                return True, _PID_BY_SUMMARY_KEY.get(name)
        return False, None


def _validate_vin_hash(vin_hashed: str) -> None:
    """Require the US-001 lowercase SHA-256 VIN hash, never a raw VIN."""
    if not isinstance(vin_hashed, str) or not _VIN_HASH_PATTERN.fullmatch(vin_hashed):
        raise ValueError(
            "vin_hashed must be a lowercase 64-character SHA-256 hex digest."
        )
