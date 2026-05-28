"""Narrow live OBD-II adapter boundary for stationary smoke capture.

LIVE VEHICLE CODE: every outgoing request must pass the read-only guard before
an adapter library can transmit anything to the vehicle.
"""

from __future__ import annotations

from typing import Any

from autopulse.data.validator import command_filter


LIVE_ALLOWED_PIDS = frozenset({0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D})
J1979_CURRENT_DATA_SERVICE = 0x01


class LiveAdapterError(RuntimeError):
    """Raised for live adapter setup or query failures."""


class PIDNotAllowedError(ValueError):
    """Raised when a caller attempts to query a PID outside the allowlist."""


class LiveOBDAdapter:
    """Small wrapper around python-obd for read-only ICE Mode 01 queries."""

    _PID_COMMAND_NAMES = {
        0x04: "ENGINE_LOAD",
        0x05: "COOLANT_TEMP",
        0x06: "SHORT_FUEL_TRIM_1",
        0x07: "LONG_FUEL_TRIM_1",
        0x0C: "RPM",
        0x0D: "SPEED",
    }

    def __init__(self, port: str, *, obd_module: Any | None = None) -> None:
        self.port = port
        self._obd = obd_module
        self._connection: Any | None = None

    def connect(self) -> None:
        if self._obd is None:
            try:
                import obd as obd_module  # type: ignore[import-not-found]
            except ImportError as exc:
                raise LiveAdapterError(
                    "python-obd is required for live smoke capture."
                ) from exc
            self._obd = obd_module

        self._connection = self._obd.OBD(self.port, fast=False)
        if hasattr(self._connection, "is_connected") and not self._connection.is_connected():
            raise LiveAdapterError("adapter did not connect")

    def disconnect(self) -> None:
        if self._connection is not None and hasattr(self._connection, "close"):
            self._connection.close()
        self._connection = None

    def get_protocol_name(self) -> str:
        if self._connection is None:
            raise LiveAdapterError("adapter is not connected")
        protocol = getattr(self._connection, "protocol_name", None)
        if callable(protocol):
            return str(protocol())
        if protocol is not None:
            return str(protocol)
        return "SAE_J1979"

    def query_pid(self, pid: int) -> float | int:
        self.validate_outgoing_request(J1979_CURRENT_DATA_SERVICE, pid)
        if self._connection is None or self._obd is None:
            raise LiveAdapterError("adapter is not connected")

        command = self._command_for_pid(pid)
        response = self._connection.query(command)
        if getattr(response, "is_null", lambda: False)():
            raise LiveAdapterError("adapter returned no data")
        value = getattr(response, "value", None)
        if value is None:
            raise LiveAdapterError("adapter returned no value")
        magnitude = getattr(value, "magnitude", value)
        if not isinstance(magnitude, (int, float)) or isinstance(magnitude, bool):
            raise LiveAdapterError("adapter returned non-numeric value")
        return magnitude

    def validate_outgoing_request(self, service_id: int, pid: int | None = None) -> None:
        command_filter(service_id)
        if service_id != J1979_CURRENT_DATA_SERVICE:
            raise PIDNotAllowedError("only SAE J1979 Mode 01 current-data reads are allowed")
        if pid not in LIVE_ALLOWED_PIDS:
            raise PIDNotAllowedError("PID is not in the live smoke allowlist")

    def _command_for_pid(self, pid: int) -> Any:
        name = self._PID_COMMAND_NAMES[pid]
        commands = getattr(self._obd, "commands", None)
        command = getattr(commands, name, None)
        if command is None:
            raise LiveAdapterError("python-obd command is unavailable")
        return command


__all__ = [
    "J1979_CURRENT_DATA_SERVICE",
    "LIVE_ALLOWED_PIDS",
    "LiveAdapterError",
    "LiveOBDAdapter",
    "PIDNotAllowedError",
]
