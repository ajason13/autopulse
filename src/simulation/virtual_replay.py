"""US-002 virtual replay harness for offline OBD-II frame simulation."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Protocol

from jsonschema import ValidationError

from src.data.validator import command_filter, validate_frame


US001_REQUIRED_FIELDS = frozenset(
    {
        "timestamp",
        "vin_hashed",
        "protocol",
        "engine_rpm",
        "vehicle_speed",
        "coolant_temp",
        "engine_load",
        "stft_bank1",
        "ltft_bank1",
    }
)

NUMERIC_FIELDS = frozenset(
    {
        "engine_rpm",
        "vehicle_speed",
        "coolant_temp",
        "engine_load",
        "stft_bank1",
        "ltft_bank1",
    }
)

US001_BOUNDS: dict[str, tuple[float, float]] = {
    "engine_rpm": (0.0, 9500.0),
    "vehicle_speed": (0.0, 255.0),
    "coolant_temp": (-40.0, 140.0),
    "engine_load": (0.0, 100.0),
    "stft_bank1": (-50.0, 50.0),
    "ltft_bank1": (-50.0, 50.0),
}

PROTOCOL_ALIASES = {
    "SAE_J1979": "SAE_J1979",
    "SAE_J1979_2": "SAE_J1979_2",
    "J1979_MODE01": "SAE_J1979",
    "J1979_2_SERVICE22": "SAE_J1979_2",
}

REPLAY_PROTOCOLS = frozenset({"J1979_MODE01", "J1979_2_SERVICE22"})
SLEEP_GUARD_SECONDS = 0.002


class SecurityViolationError(Exception):
    """Raised when a restricted diagnostic service appears in replay input."""


class RowParser(Protocol):
    """Protocol for dataset parsers that normalize one source row."""

    def parse(self, row: dict[str, Any]) -> dict[str, Any]:
        """Return a row shaped for US-001 normalization."""


class OBDAdapter(ABC):
    """Minimal read-only OBD adapter interface used by replay drivers."""

    @abstractmethod
    def fetch_frame(self) -> "DataPacket":
        """Fetch the next normalized engine data frame."""


@dataclass(frozen=True)
class DataPacket:
    """Normalized US-001 engine frame returned by a replay adapter."""

    timestamp: str
    vin_hashed: str
    protocol: str
    engine_rpm: float
    vehicle_speed: int
    coolant_temp: float
    engine_load: float
    stft_bank1: float
    ltft_bank1: float
    _raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Freeze the raw source snapshot used for audit trails."""
        object.__setattr__(self, "_raw", MappingProxyType(dict(self._raw)))

    def to_dict(self) -> dict[str, Any]:
        """Return the replay-facing frame payload."""
        return {
            "timestamp": self.timestamp,
            "vin_hashed": self.vin_hashed,
            "protocol": self.protocol,
            "engine_rpm": self.engine_rpm,
            "vehicle_speed": self.vehicle_speed,
            "coolant_temp": self.coolant_temp,
            "engine_load": self.engine_load,
            "stft_bank1": self.stft_bank1,
            "ltft_bank1": self.ltft_bank1,
        }

    def to_schema_dict(self) -> dict[str, Any]:
        """Return the canonical US-001 schema payload."""
        payload = self.to_dict()
        payload["protocol"] = PROTOCOL_ALIASES.get(
            self.protocol,
            self.protocol,
        )
        return payload


class LogProvider(ABC):
    """Stateful source of raw replay rows."""

    @abstractmethod
    def get_next_row(self) -> dict[str, Any]:
        """Return the next source row or raise StopIteration."""

    @abstractmethod
    def reset(self) -> None:
        """Reset the provider to the beginning of the source."""


class JSONLProvider(LogProvider):
    """Provider backed by a JSONL file path or in-memory dictionaries.

    This provider eagerly loads source rows so replay can reset and loop with a
    stable in-memory pointer. Production-scale CAN logs should use a future
    streaming provider with bounded buffering.
    """

    def __init__(
        self,
        source: str | Path | Iterable[dict[str, Any]],
        parser: RowParser | None = None,
    ) -> None:
        self._data = self._load(source)
        self._parser = parser
        self._idx = 0

    def get_next_row(self) -> dict[str, Any]:
        if self._idx >= len(self._data):
            raise StopIteration
        row = dict(self._data[self._idx])
        self._idx += 1
        if self._parser is not None:
            row = self._parser.parse(row)
        return row

    def reset(self) -> None:
        self._idx = 0

    @staticmethod
    def _load(
        source: str | Path | Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if isinstance(source, (str, Path)):
            rows: list[dict[str, Any]] = []
            with Path(source).open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        parsed = json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Malformed JSONL row {line_number}: {exc.msg}"
                        ) from exc
                    if not isinstance(parsed, dict):
                        raise ValueError(
                            "Malformed JSONL row "
                            f"{line_number}: expected object"
                        )
                    rows.append(parsed)
            return rows
        return [dict(row) for row in source]


class CSVProvider(LogProvider):
    """Provider backed by a CSV file path or in-memory CSV-style rows.

    This provider eagerly loads source rows so replay can reset and loop with a
    stable in-memory pointer. Production-scale CAN logs should use a future
    streaming provider with bounded buffering.
    """

    def __init__(
        self,
        source: str | Path | Iterable[dict[str, Any]],
        parser: RowParser | None = None,
    ) -> None:
        self._rows = self._load(source)
        self._parser = parser
        self._idx = 0

    def get_next_row(self) -> dict[str, Any]:
        if self._idx >= len(self._rows):
            raise StopIteration
        source_row = self._rows[self._idx]
        row = {
            key: self._coerce(key, value)
            for key, value in source_row.items()
        }
        self._idx += 1
        if self._parser is not None:
            row = self._parser.parse(row)
        return row

    def reset(self) -> None:
        self._idx = 0

    @staticmethod
    def _load(
        source: str | Path | Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if isinstance(source, (str, Path)):
            with Path(source).open(newline="", encoding="utf-8") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        return [dict(row) for row in source]

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if key == "vehicle_speed":
            return int(value)
        if key in NUMERIC_FIELDS:
            return float(value)
        return value


class CandidParser:
    """Decode simple CANdid-style OBD-II PID rows into normalized fields.

    Fuel-trim PIDs 0x06 and 0x07 use the OBD-II formula
    ``(A / 128 - 1) * 100``. Raw byte extremes can decode outside the
    AutoPulse US-001 ``[-50, 50]`` physical contract; those frames are left
    unclamped so the schema gate rejects them as dirty replay input.
    """

    def parse(self, row: dict[str, Any]) -> dict[str, Any]:
        parsed = dict(row)
        pid = self._pid(parsed)
        data = self._data_bytes(parsed)
        if pid is None:
            return parsed
        if pid == 0x0C and len(data) >= 2:
            parsed["engine_rpm"] = ((data[0] * 256) + data[1]) / 4.0
        elif pid == 0x0D and data:
            parsed["vehicle_speed"] = data[0]
        elif pid == 0x05 and data:
            parsed["coolant_temp"] = float(data[0] - 40)
        elif pid == 0x04 and data:
            parsed["engine_load"] = data[0] * 100.0 / 255.0
        elif pid == 0x06 and data:
            parsed["stft_bank1"] = data[0] * 100.0 / 128.0 - 100.0
        elif pid == 0x07 and data:
            parsed["ltft_bank1"] = data[0] * 100.0 / 128.0 - 100.0
        return parsed

    @staticmethod
    def _pid(row: dict[str, Any]) -> int | None:
        raw_pid = row.get("pid", row.get("PID"))
        if raw_pid is None:
            return None
        if isinstance(raw_pid, str):
            if raw_pid.lower().startswith("0x"):
                return int(raw_pid, 16)
            return int(raw_pid)
        return int(raw_pid)

    @staticmethod
    def _data_bytes(row: dict[str, Any]) -> list[int]:
        raw_data = row.get("data", row.get("bytes", row.get("payload", [])))
        if isinstance(raw_data, str):
            tokens = raw_data.replace(",", " ").split()
            return [int(token, 16) for token in tokens]
        if isinstance(raw_data, Iterable):
            return [int(item) for item in raw_data]
        return []


class AI4IParser:
    """Map AI4I industrial telemetry columns to normalized OBD-II fields."""

    def parse(self, row: dict[str, Any]) -> dict[str, Any]:
        parsed = dict(row)
        self._copy_number(parsed, "Rotational speed [rpm]", "engine_rpm")
        self._copy_number(parsed, "Torque [Nm]", "engine_load")
        self._copy_number(parsed, "Process temperature [K]", "coolant_temp")
        self._copy_number(parsed, "Process temperature [C]", "coolant_temp")
        if "Process temperature [K]" in row:
            parsed["coolant_temp"] = (
                float(row["Process temperature [K]"]) - 273.15
            )
        if "Torque [Nm]" in row:
            parsed["engine_load"] = max(
                0.0,
                min(100.0, float(row["Torque [Nm]"])),
            )
        parsed.setdefault("vehicle_speed", 0)
        parsed.setdefault("stft_bank1", 0.0)
        parsed.setdefault("ltft_bank1", 0.0)
        return parsed

    @staticmethod
    def _copy_number(
        row: dict[str, Any],
        source_key: str,
        target_key: str,
    ) -> None:
        if source_key in row:
            row[target_key] = float(row[source_key])


class NoiseGenerator:
    """Adversarial mutations for dirty replay scenarios."""

    @staticmethod
    def pid_drop(
        row: dict[str, Any],
        field_name: str | None = None,
    ) -> dict[str, Any]:
        mutated = dict(row)
        target = field_name or random.choice(sorted(NUMERIC_FIELDS))
        mutated[target] = None
        return mutated

    @staticmethod
    def out_of_bounds(
        row: dict[str, Any],
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        mutated = dict(row)
        mutated[field_name] = value
        return mutated

    @staticmethod
    def inject_restricted_service(
        row: dict[str, Any],
        service_id: str | int,
    ) -> dict[str, Any]:
        mutated = dict(row)
        mutated["__service_id__"] = service_id
        return mutated


class MockAdapter(OBDAdapter):
    """Stateful replay adapter that replaces a physical ELM327 adapter."""

    _DEFAULT_VIN = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    _DEFAULT_PROTOCOL = "J1979_MODE01"

    def __init__(self, provider: LogProvider, loop: bool = False) -> None:
        self._provider = provider
        self._loop = loop
        self._connected = False
        self._security_violations: list[str] = []

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def security_violations(self) -> list[str]:
        return list(self._security_violations)

    def fetch_frame(self) -> DataPacket:
        if not self._connected:
            raise RuntimeError("Adapter not connected. Call connect() first.")
        raw = self._next_row()
        self._enforce_security(raw)
        return self._normalize(raw)

    def _next_row(self) -> dict[str, Any]:
        try:
            return self._provider.get_next_row()
        except StopIteration:
            if not self._loop:
                raise
            self._provider.reset()
            return self._provider.get_next_row()

    def _enforce_security(self, row: dict[str, Any]) -> None:
        service_id = row.get("__service_id__")
        if service_id is None:
            return
        service_value = self._parse_service_id(service_id)
        try:
            command_filter(service_value)
        except Exception as exc:
            formatted = f"0x{service_value:02X}"
            self._security_violations.append(formatted)
            raise SecurityViolationError(
                "SECURITY_VIOLATION_RED_LINE: restricted service "
                f"{formatted}"
            ) from exc

    def _normalize(self, raw: dict[str, Any]) -> DataPacket:
        row = dict(raw)
        row["timestamp"] = row.get("timestamp") or self._timestamp()
        row["vin_hashed"] = row.get("vin_hashed") or self._DEFAULT_VIN
        row["protocol"] = row.get("protocol") or self._DEFAULT_PROTOCOL

        missing = sorted(
            field for field in NUMERIC_FIELDS if row.get(field) is None
        )
        if missing:
            raise ValidationError(
                f"Required field '{missing[0]}' is null/missing."
            )

        packet = DataPacket(
            timestamp=str(row["timestamp"]),
            vin_hashed=str(row["vin_hashed"]),
            protocol=self._normalize_protocol(
                row["protocol"],
                replay_facing=True,
            ),
            engine_rpm=self._float_field(row, "engine_rpm"),
            vehicle_speed=self._int_field(row, "vehicle_speed"),
            coolant_temp=self._float_field(row, "coolant_temp"),
            engine_load=self._float_field(row, "engine_load"),
            stft_bank1=self._float_field(row, "stft_bank1"),
            ltft_bank1=self._float_field(row, "ltft_bank1"),
            _raw=raw,
        )
        self._validate_packet(packet)
        return packet

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    @staticmethod
    def _parse_service_id(service_id: str | int) -> int:
        if isinstance(service_id, str):
            if service_id.lower().startswith("0x"):
                return int(service_id, 16)
            return int(service_id)
        return int(service_id)

    @staticmethod
    def _normalize_protocol(value: Any, replay_facing: bool = False) -> str:
        protocol = str(value)
        if protocol not in PROTOCOL_ALIASES:
            raise ValidationError(f"protocol '{protocol}' is not allowed.")
        if replay_facing and protocol in {"SAE_J1979", "SAE_J1979_2"}:
            if protocol == "SAE_J1979":
                return "J1979_MODE01"
            return "J1979_2_SERVICE22"
        return protocol

    @staticmethod
    def _float_field(row: dict[str, Any], field_name: str) -> float:
        value = row[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"Field '{field_name}' has invalid type.")
        numeric = float(value)
        lower, upper = US001_BOUNDS[field_name]
        if not lower <= numeric <= upper:
            raise ValidationError(
                f"Field '{field_name}' value {numeric} out of bounds "
                f"[{lower}, {upper}]."
            )
        return numeric

    @staticmethod
    def _int_field(row: dict[str, Any], field_name: str) -> int:
        value = row[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"Field '{field_name}' has invalid type.")
        numeric = float(value)
        lower, upper = US001_BOUNDS[field_name]
        if not lower <= numeric <= upper:
            raise ValidationError(
                f"Field '{field_name}' value {numeric} out of bounds "
                f"[{lower}, {upper}]."
            )
        if isinstance(value, float) and not value.is_integer():
            raise ValidationError(f"Field '{field_name}' has invalid type.")
        return int(value)

    @staticmethod
    def _validate_packet(packet: DataPacket) -> None:
        validate_frame(packet.to_schema_dict())


class LogReplayer:
    """Drive an OBD adapter at a deterministic replay cadence."""

    def __init__(
        self,
        adapter: MockAdapter,
        frequency_hz: int = 1,
        drift: float = 0.0,
    ) -> None:
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive.")
        if drift < 0:
            raise ValueError("drift must be non-negative.")
        self._validate_drift_budget(frequency_hz, drift)
        self._adapter = adapter
        self._frequency_hz = frequency_hz
        self._drift = drift
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._frames: list[DataPacket] = []
        self._errors: list[Exception] = []
        self._dispatch_timestamps: list[float] = []

    @property
    def frames(self) -> list[DataPacket]:
        """Return a stable snapshot of collected frames."""
        with self._lock:
            return list(self._frames)

    @property
    def errors(self) -> list[Exception]:
        """Return a stable snapshot of collected replay errors."""
        with self._lock:
            return list(self._errors)

    def set_speed(self, multiplier: float) -> None:
        if multiplier <= 0:
            raise ValueError("Speed multiplier must be positive.")
        self._frequency_hz = round(self._frequency_hz * multiplier)
        if self._frequency_hz <= 0:
            raise ValueError("Speed multiplier produced zero frequency.")
        self._validate_drift_budget(self._frequency_hz, self._drift)

    def start(self, max_frames: Optional[int] = None) -> None:
        self._running = True
        self._adapter.connect()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(max_frames,),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._adapter.disconnect()

    def join(self, timeout: float = 10.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    @property
    def inter_frame_intervals(self) -> list[float]:
        with self._lock:
            timestamps = list(self._dispatch_timestamps)
        return [
            timestamps[index + 1] - timestamps[index]
            for index in range(len(timestamps) - 1)
        ]

    @staticmethod
    def _validate_drift_budget(frequency_hz: int, drift: float) -> None:
        if drift >= 1.0 / frequency_hz:
            raise ValueError("drift must be less than the frame interval.")

    def _run_loop(self, max_frames: Optional[int]) -> None:
        interval = 1.0 / self._frequency_hz
        count = 0
        next_dispatch = time.perf_counter()
        while self._running:
            if max_frames is not None and count >= max_frames:
                self._running = False
                break
            started_at = time.perf_counter()
            with self._lock:
                self._dispatch_timestamps.append(started_at)
            try:
                if self._drift:
                    time.sleep(self._drift)
                frame = self._adapter.fetch_frame()
                with self._lock:
                    self._frames.append(frame)
            except StopIteration:
                self._running = False
                break
            except Exception as exc:
                with self._lock:
                    self._errors.append(exc)
            next_dispatch += interval
            sleep_for = (
                next_dispatch - time.perf_counter() - SLEEP_GUARD_SECONDS
            )
            if sleep_for > 0:
                time.sleep(sleep_for)
            count += 1
