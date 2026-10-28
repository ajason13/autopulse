"""Finite-horizon experimental low-RPM/high-load exposure, not failure risk."""

from collections import deque
import math

from autopulse.analysis.utils import (
    LUGGING_RPM_CEILING,
    LUGGING_LOAD_FLOOR,
    OSF_WINDOW_SECONDS,
    VehicleClass,
)


class OSFDetector:
    """Integrate the previous sample's indicator over the last 60 seconds.

    ``vehicle_class`` is retained for compatibility; L/M/H share one policy.
    ``s_idx`` now means recent exposure seconds, not lifetime workload stress.
    See docs/specs/ice-scoring-policy.md for units and intentional API changes.
    """

    def __init__(self, vehicle_class: VehicleClass = "L"):
        if vehicle_class not in ("L", "M", "H"):
            raise KeyError(vehicle_class)
        self.vehicle_class = vehicle_class
        self.reset()

    @property
    def s_idx(self) -> float:
        """Recent exposure duration in seconds (read-only, in [0, 60])."""
        return min(OSF_WINDOW_SECONDS, math.fsum(end - start for start, end in self._intervals))

    def update(self, load_pct: float, rpm: float, elapsed_seconds: float) -> None:
        """Hold the previous indicator over elapsed time, then seed this sample.

        First samples accrue no exposure. RPM zero resets this branch; processor
        callers also gate on raw RPM before supplying smoothed inputs. Session
        gap resets belong to the processor. Invalid inputs reject before mutation.
        """
        if not all(math.isfinite(value) for value in (load_pct, rpm, elapsed_seconds)):
            raise ValueError("OSF inputs must be finite.")
        if elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be non-negative.")
        if rpm == 0:
            self.reset()
            return

        start = self._time
        self._time += elapsed_seconds if self._held_exposure is not None else 0.0
        if self._held_exposure and self._time > start:
            if self._intervals and self._intervals[-1][1] == start:
                self._intervals[-1] = (self._intervals[-1][0], self._time)
            else:
                self._intervals.append((start, self._time))
        cutoff = self._time - OSF_WINDOW_SECONDS
        while self._intervals and self._intervals[0][1] <= cutoff:
            self._intervals.popleft()
        if self._intervals and self._intervals[0][0] < cutoff:
            self._intervals[0] = (cutoff, self._intervals[0][1])
        self._held_exposure = 0 < rpm < LUGGING_RPM_CEILING and load_pct > LUGGING_LOAD_FLOOR

    def classify(self) -> str:
        """Legacy labels identify exposure branches, not confirmed faults."""
        score = self.compute_probability()
        if score == 1.0:
            return "OSF"
        if score > 0.5:
            return "OSF_ANOMALY"
        return "NONE"

    def compute_probability(self, k: float = 0.001) -> float:
        """Experimental exposure fraction; legacy sigmoid argument k is ignored."""
        return self.s_idx / OSF_WINDOW_SECONDS

    def reset(self) -> None:
        """Discard all exposure intervals, held sample and relative time."""
        self._intervals: deque[tuple[float, float]] = deque()
        self._time = 0.0
        self._held_exposure: bool | None = None
