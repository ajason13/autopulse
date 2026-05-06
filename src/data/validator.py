"""US-001 engine OBD-II frame validation and read-only service filtering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "engine_obd_frame.schema.json"
)

RESTRICTED_SERVICE_IDS = frozenset(
    {
        0x08,  # J1979: Request Control of On-Board System
        0x31,  # UDS: RoutineControl
        0x04,  # J1979: Clear / Reset Diagnostic Information
        0x14,  # UDS: ClearDiagnosticInformation
        0x2E,  # UDS: WriteDataByIdentifier
        0x10,  # UDS: DiagnosticSessionControl
    }
)


class SecurityViolationRedLine(Exception):
    """Raised when a blocked CAN service ID is intercepted."""

    def __init__(self, service_id: int):
        self.service_id = service_id
        super().__init__(
            "SECURITY_VIOLATION_RED_LINE: Restricted Service ID "
            f"0x{service_id:02X} was intercepted and blocked."
        )


def load_engine_obd_frame_schema() -> dict[str, Any]:
    """Load the strict US-001 engine OBD-II frame JSON schema from disk."""
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        return json.load(schema_file)


ENGINE_OBD_FRAME_SCHEMA = load_engine_obd_frame_schema()
ENGINE_OBD_FRAME_VALIDATOR = Draft7Validator(
    ENGINE_OBD_FRAME_SCHEMA,
    format_checker=FormatChecker(),
)


def validate_frame(frame: dict[str, Any]) -> None:
    """Validate an engine OBD-II frame against the US-001 JSON schema."""
    ENGINE_OBD_FRAME_VALIDATOR.validate(frame)


def command_filter(service_id: int) -> None:
    """Block restricted write/control diagnostic services before CAN transmit."""
    if service_id in RESTRICTED_SERVICE_IDS:
        raise SecurityViolationRedLine(service_id)
