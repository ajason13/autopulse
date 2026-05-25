"""Frame validation and read-only diagnostic service filtering."""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any

from jsonschema import Draft7Validator, FormatChecker


SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "schemas"
    / "engine_obd_frame.schema.json"
)
EV_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "schemas"
    / "ev_obd_frame.schema.json"
)

ICE_PROTOCOLS = frozenset({"SAE_J1979", "SAE_J1979-2"})
EV_PROTOCOLS = frozenset(
    {"SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"}
)

RESTRICTED_SERVICE_IDS = frozenset(
    {
        int("08", 16),  # J1979: Request Control of On-Board System
        int("31", 16),  # UDS: RoutineControl
        int("04", 16),  # J1979: Clear / Reset Diagnostic Information
        int("14", 16),  # UDS: ClearDiagnosticInformation
        int("2E", 16),  # UDS: WriteDataByIdentifier
        int("10", 16),  # UDS: DiagnosticSessionControl
        int("27", 16),  # UDS: SecurityAccess
        int("2F", 16),  # UDS: InputOutputControlByIdentifier
    }
)

_RED_LINE_SERVICES = frozenset({0x2E, 0x31, 0x10, 0x27, 0x2F})
_HIGH_SEVERITY_SERVICES = frozenset({0x14})
_ALLOWED_DTC_SUBFUNCTIONS = frozenset({0x02, 0x06})
_DEFAULT_SESSION = 0x01
_TESTER_PRESENT_MIN_INTERVAL_SECONDS = 4.0


class SecurityViolationRedLine(Exception):
    """Raised when a blocked CAN service ID is intercepted."""

    def __init__(self, service_id: int):
        self.service_id = service_id
        super().__init__(
            "SECURITY_VIOLATION_RED_LINE: Restricted Service ID "
            f"0x{service_id:02X} was intercepted and blocked."
        )


class RoutingError(ValueError):
    """Raised when a shared-envelope frame cannot be safely routed."""


class CommandBlockedException(Exception):
    """Raised when an unsafe diagnostic service or sub-function is blocked."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def load_engine_obd_frame_schema() -> dict[str, Any]:
    """Load the strict US-001 engine OBD-II frame JSON schema from disk."""
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


def load_ev_obd_frame_schema() -> dict[str, Any]:
    """Load the strict US-006 EV telemetry frame JSON schema from disk."""
    with EV_SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


ENGINE_OBD_FRAME_SCHEMA = load_engine_obd_frame_schema()
ENGINE_OBD_FRAME_VALIDATOR = Draft7Validator(
    ENGINE_OBD_FRAME_SCHEMA,
    format_checker=FormatChecker(),
)
EV_OBD_FRAME_SCHEMA = load_ev_obd_frame_schema()
EV_OBD_FRAME_VALIDATOR = Draft7Validator(
    EV_OBD_FRAME_SCHEMA,
    format_checker=FormatChecker(),
)


def validate_frame(frame: dict[str, Any]) -> None:
    """Validate an engine OBD-II frame against the US-001 JSON schema."""
    _validate_finite_numbers(frame)
    ENGINE_OBD_FRAME_VALIDATOR.validate(frame)


def validate_ev_frame(frame: dict[str, Any]) -> None:
    """Validate an EV telemetry frame against the US-006 JSON schema."""
    _validate_finite_numbers(frame)
    EV_OBD_FRAME_VALIDATOR.validate(frame)


def route_and_validate(frame: dict[str, Any]) -> str:
    """Validate a shared-envelope frame and return the selected powertrain.

    EV frames are validated as full US-006 envelope objects. ICE frames predate
    the envelope model, so routing validates only the nested US-001 flat payload.
    Do not pass the full ICE envelope to ``validate_frame()``.
    """
    if not isinstance(frame, dict):
        raise TypeError("frame must be a dict.")

    powertrain_type = frame.get("powertrain_type")
    protocol = frame.get("protocol")

    if powertrain_type not in {"ICE", "EV"}:
        raise RoutingError("powertrain_type must be exactly 'ICE' or 'EV'.")

    if powertrain_type == "EV":
        if protocol not in EV_PROTOCOLS:
            raise RoutingError("EV frame protocol is not in the EV enum.")
        validate_ev_frame(frame)
        return "EV"

    if protocol not in ICE_PROTOCOLS:
        raise RoutingError("ICE frame protocol is not in the ICE enum.")

    payload = frame.get("payload")
    if not isinstance(payload, dict):
        raise RoutingError("ICE routed frames must contain a payload object.")

    validate_frame(payload)
    return "ICE"


def command_filter(service_id: int) -> None:
    """Block restricted write/control diagnostic services before CAN transmit."""
    if service_id in RESTRICTED_SERVICE_IDS:
        raise SecurityViolationRedLine(service_id)


class UDSCommandGuard:
    """Stateful read-only UDS policy gate for US-006 adapter behavior."""

    def __init__(self) -> None:
        self.current_session = _DEFAULT_SESSION
        self.last_tester_present_at: float | None = None
        self.observed_dtcs: set[str] = set()
        self.events: list[str] = []

    def validate(
        self,
        service_id: int | str,
        sub_function: int | str | None = None,
        *,
        dtc: str | None = None,
        now: float | None = None,
    ) -> None:
        """Validate a UDS command against AutoPulse read-only guardrails."""
        service = _parse_hex_or_int(service_id)
        subfn = None if sub_function is None else _parse_hex_or_int(sub_function)

        if service == 0x22:
            return

        if service == 0x19:
            self._validate_read_dtc(subfn, dtc)
            return

        if service == 0x3E:
            self._validate_tester_present(now)
            return

        if service == 0x10:
            self._validate_diagnostic_session(subfn)
            return

        if service in _RED_LINE_SERVICES:
            self._block("SECURITY_VIOLATION_RED_LINE", service, subfn)

        if service in _HIGH_SEVERITY_SERVICES:
            self._block("SECURITY_VIOLATION_HIGH", service, subfn)

        command_filter(service)

    def observe_dtcs(self, dtcs: list[str]) -> None:
        """Register DTCs learned through a passive 0x19/0x02 read."""
        self.observed_dtcs.update(str(dtc) for dtc in dtcs)

    def check_protocol_transition(
        self,
        active_protocol: str,
        next_protocol: str,
    ) -> None:
        """Abort when a live session attempts DoCAN/DoIP renegotiation."""
        if active_protocol != next_protocol and {
            active_protocol,
            next_protocol,
        } == {"ISO_15765_4_DoCAN", "ISO_13400_DoIP"}:
            self.events.append("PROTOCOL_TRANSITION_BLOCKED")
            raise CommandBlockedException(
                "PROTOCOL_TRANSITION_BLOCKED",
                "DoCAN/DoIP transitions require manual reconfiguration.",
            )

    def validate_motor_speed_sign_convention(
        self,
        motor_speed: int | None,
        *,
        sign_convention_documented: bool,
        reject_undocumented: bool = True,
    ) -> None:
        """Reject or flag negative motor speed without source documentation."""
        if motor_speed is None or motor_speed >= 0 or sign_convention_documented:
            return

        self.events.append("SIGN_CONVENTION_UNDOCUMENTED")
        if reject_undocumented:
            raise CommandBlockedException(
                "SIGN_CONVENTION_UNDOCUMENTED",
                "Negative traction_motor_speed requires source convention docs.",
            )

    def _validate_read_dtc(self, subfn: int | None, dtc: str | None) -> None:
        if subfn not in _ALLOWED_DTC_SUBFUNCTIONS:
            self._block("SECURITY_VIOLATION_HIGH", 0x19, subfn)

        if subfn == 0x06 and (dtc is None or str(dtc) not in self.observed_dtcs):
            self.events.append("SPECULATIVE_DTC_PROBE")
            raise CommandBlockedException(
                "SPECULATIVE_DTC_PROBE",
                "0x19/0x06 requires a previously observed DTC.",
            )

    def _validate_tester_present(self, now: float | None) -> None:
        if self.current_session != _DEFAULT_SESSION:
            self._block("SECURITY_VIOLATION_RED_LINE", 0x3E, None)

        current_time = time.monotonic() if now is None else float(now)
        if (
            self.last_tester_present_at is not None
            and current_time - self.last_tester_present_at
            < _TESTER_PRESENT_MIN_INTERVAL_SECONDS
        ):
            self.events.append("TESTER_PRESENT_RATE_LIMIT")
            raise CommandBlockedException(
                "TESTER_PRESENT_RATE_LIMIT",
                "TesterPresent is limited to once per 4 seconds.",
            )
        self.last_tester_present_at = current_time

    def _validate_diagnostic_session(self, subfn: int | None) -> None:
        if subfn == _DEFAULT_SESSION:
            self.current_session = _DEFAULT_SESSION
            return
        self._block("SECURITY_VIOLATION_RED_LINE", 0x10, subfn)

    def _block(self, code: str, service: int, subfn: int | None) -> None:
        event = code
        if subfn is not None:
            event = f"{code}:0x{service:02X}/0x{subfn:02X}"
        self.events.append(event)
        raise CommandBlockedException(
            code,
            f"blocked service 0x{service:02X}",
        )


def _validate_finite_numbers(value: Any) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("frames must not contain non-finite numeric values.")
        return
    if isinstance(value, dict):
        for item in value.values():
            _validate_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_finite_numbers(item)


def _parse_hex_or_int(value: int | str) -> int:
    if isinstance(value, str):
        if value.lower().startswith("0x"):
            return int(value, 16)
        return int(value)
    return int(value)


__all__ = [
    "CommandBlockedException",
    "ENGINE_OBD_FRAME_SCHEMA",
    "EV_OBD_FRAME_SCHEMA",
    "EV_PROTOCOLS",
    "ICE_PROTOCOLS",
    "RESTRICTED_SERVICE_IDS",
    "RoutingError",
    "SecurityViolationRedLine",
    "UDSCommandGuard",
    "command_filter",
    "load_engine_obd_frame_schema",
    "load_ev_obd_frame_schema",
    "route_and_validate",
    "validate_ev_frame",
    "validate_frame",
]
