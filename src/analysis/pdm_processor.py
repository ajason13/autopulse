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
    VehicleClass,
)

FailureType = Literal["HDF", "OSF", "OSF_ANOMALY", "NONE", "SENSOR_ERROR"]
WindowStatValue = float | bool
WindowSummary = dict[str, dict[str, WindowStatValue]]

_VIN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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
        ambient = float(frame["ambient_temp"])
        delta_t = coolant - ambient

        # Temporal delta
        elapsed = 1.0  # Default to 1Hz
        if self.last_timestamp is not None:
            elapsed = max(0.001, curr_time - self.last_timestamp)

        # Step 2: Update temporal state
        self.rpm_buffer.push(rpm)
        self.coolant_buffer.push(coolant)
        self.load_buffer.push(load)

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
                        primary_pid=0x05,
                        obd_frame=frame
                    )
            except ValueError:
                pass

        # Step 3 & 4: Evaluate branches.
        # OSF includes the current frame's stress increment.
        p_hdf = self.hdf_detector.compute_probability(delta_t, rpm)
        stress_inc = self.osf_detector.compute_stress_increment(load, rpm, elapsed)
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

        # Generate window summary
        summary = self._generate_summary()

        # Update last state
        self.last_timestamp = curr_time
        self.last_coolant_temp = coolant

        return PdMAlert(
            timestamp=timestamp_ms,
            vin_hashed=self.vin_hashed,
            failure_probability=primary_prob,
            failure_type=failure_type if primary_prob > PROB_ANOMALY_LO else "NONE",
            is_anomaly=primary_prob > PROB_ANOMALY_LO,
            window_summary=summary,
            obd_frame=frame
        )

    def _check_mandatory_pids(self, frame: dict[str, Any]) -> int | None:
        """Check if mandatory PIDs exist. Returns the first missing PID hex."""
        if "engine_rpm" not in frame:
            return 0x0C
        if "engine_load" not in frame:
            return 0x04
        if "coolant_temp" not in frame:
            return 0x05
        if "ambient_temp" not in frame:
            return 0x46
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


def _validate_vin_hash(vin_hashed: str) -> None:
    """Require the US-001 lowercase SHA-256 VIN hash, never a raw VIN."""
    if not isinstance(vin_hashed, str) or not _VIN_HASH_PATTERN.fullmatch(vin_hashed):
        raise ValueError(
            "vin_hashed must be a lowercase 64-character SHA-256 hex digest."
        )
