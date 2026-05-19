from __future__ import annotations

from dataclasses import dataclass, field
import statistics


@dataclass
class CircularBuffer:
    """
    Fixed-size ring buffer for the 60-second rolling window.
    O(1) push; wraps automatically.
    """
    capacity: int
    _data: list[float] = field(default_factory=list, repr=False)
    _head: int = field(default=0, repr=False)
    _count: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        """Reject capacities that cannot produce a valid ring buffer."""
        if self.capacity <= 0:
            raise ValueError("capacity must be positive.")

    def push(self, value: float) -> None:
        """Add a value to the buffer, overwriting the oldest if at capacity."""
        if len(self._data) < self.capacity:
            self._data.append(value)
        else:
            self._data[self._head % self.capacity] = value
        self._head += 1
        self._count = min(self._count + 1, self.capacity)

    def to_list(self) -> list[float]:
        """Return elements in insertion order (oldest → newest)."""
        if len(self._data) < self.capacity:
            return list(self._data)
        tail = self._head % self.capacity
        return self._data[tail:] + self._data[:tail]

    def get_median(self, n: int) -> float | None:
        """Return the median of the last up to n elements."""
        if n <= 0:
            raise ValueError("n must be positive.")

        data = self.to_list()
        if not data:
            return None
        return float(statistics.median(data[-n:]))

    def get_ewma(self, alpha: float) -> float | None:
        """
        Return the exponentially weighted moving average over current contents.

        The oldest value seeds the accumulator, matching the US-004 smoothing
        definition for a deterministic windowed stream.
        """
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in the range (0.0, 1.0].")

        data = self.to_list()
        if not data:
            return None

        ewma = data[0]
        for value in data[1:]:
            ewma = alpha * value + (1.0 - alpha) * ewma
        return ewma

    @property
    def is_full(self) -> bool:
        """True if the buffer has reached its capacity."""
        return self._count == self.capacity

    def __len__(self) -> int:
        """Return the current number of elements in the buffer."""
        return self._count

    def clear(self) -> None:
        """Reset the buffer."""
        self._data.clear()
        self._head = 0
        self._count = 0
