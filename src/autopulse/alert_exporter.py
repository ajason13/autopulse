from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4


_VIN_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_VALID_FAILURE_TYPES = frozenset({"HDF", "OSF"})
_VALID_EV_EVENT_TYPES = frozenset(
    {
        "EV_SCHEMA_REJECTION",
        "EV_VALIDATION_EVENT",
        "SECURITY_VIOLATION_RED_LINE",
        "SECURITY_VIOLATION_HIGH",
        "POWERTRAIN_ROUTING_MISMATCH",
    }
)


def _service_key(prefix: str, service_id: str) -> str:
    return f"{prefix}_0x{service_id}"


_RESTRICTED_KEYS = frozenset(
    {
        _service_key("mode", "08"),
        _service_key("service", "31"),
        _service_key("service", "2e"),
        _service_key("service", "14"),
        _service_key("service", "10"),
        "routine_control",
        "write_data_by_identifier",
        "clear_dtc",
    }
)

_CONTEXT: Mapping[str, str] = MappingProxyType(
    {
        "autopulse": "https://autopulse.io/schema/",
        "sosa": "http://www.w3.org/ns/sosa/",
        "schema": "https://schema.org/",
        "vss": "https://vss.covesa.org/",
        "vin_hashed": "sosa:hasFeatureOfInterest",
        "failure_probability": "schema:probability",
        "failure_type": "autopulse:failureMode",
        "window_summary": "sosa:hasResult",
        "powertrain_type": "autopulse:powertrainType",
        "event_type": "autopulse:eventType",
        "evidence": "sosa:hasResult",
        "battery_soh": "autopulse:batteryStateOfHealth",
        "battery_soce": "autopulse:stateOfCertifiedEnergy",
        "battery_temp_avg": "autopulse:averageBatteryTemperature",
        "traction_motor_speed": "vss:Vehicle.Powertrain.ElectricMotor.Speed",
        "battery_throughput": "autopulse:batteryThroughput",
        "grid_energy_in": "autopulse:gridEnergyInput",
    }
)


@dataclass
class PdMAlert:
    vin_hashed: str
    failure_probability: float
    failure_type: str
    window_summary: dict[str, Any] | None


@dataclass
class EVTelemetryAlert:
    vin_hashed: str
    event_type: str
    evidence: dict[str, Any]
    powertrain_type: str = "EV"


def serialize_alert(alert: PdMAlert) -> dict[str, Any]:
    """Serialize an internal PdM alert into a JSON-LD observation payload."""
    _validate_alert(alert)

    return {
        "@context": dict(_CONTEXT),
        "@type": "sosa:Observation",
        "@id": f"urn:uuid:{uuid4()}",
        "vin_hashed": alert.vin_hashed,
        "failure_probability": float(alert.failure_probability),
        "failure_type": alert.failure_type,
        "window_summary": _sanitize_window_summary(alert.window_summary),
    }


def serialize_ev_alert(alert: EVTelemetryAlert) -> dict[str, Any]:
    """Serialize a US-006 EV validation/security event into JSON-LD."""
    _validate_ev_alert(alert)
    return {
        "@context": dict(_CONTEXT),
        "@type": "sosa:Observation",
        "@id": f"urn:uuid:{uuid4()}",
        "vin_hashed": alert.vin_hashed,
        "powertrain_type": alert.powertrain_type,
        "event_type": alert.event_type,
        "evidence": _sanitize_window_summary(alert.evidence),
    }


def _validate_alert(alert: PdMAlert) -> None:
    if not isinstance(alert, PdMAlert):
        raise TypeError("alert must be a PdMAlert instance.")

    _validate_vin_hash(alert.vin_hashed)
    _validate_failure_probability(alert.failure_probability)

    if alert.failure_type not in _VALID_FAILURE_TYPES:
        raise ValueError("failure_type must be exactly 'HDF' or 'OSF'.")


def _validate_ev_alert(alert: EVTelemetryAlert) -> None:
    if not isinstance(alert, EVTelemetryAlert):
        raise TypeError("alert must be an EVTelemetryAlert instance.")
    _validate_vin_hash(alert.vin_hashed)
    if alert.powertrain_type != "EV":
        raise ValueError("powertrain_type must be exactly 'EV'.")
    if alert.event_type not in _VALID_EV_EVENT_TYPES:
        raise ValueError("event_type is not valid for US-006 EV alerts.")
    if not isinstance(alert.evidence, dict):
        raise TypeError("evidence must be a dict.")


def _validate_vin_hash(vin_hashed: str) -> None:
    if not isinstance(vin_hashed, str):
        raise TypeError("vin_hashed must be a string.")

    if _RAW_VIN_PATTERN.fullmatch(vin_hashed):
        raise ValueError("vin_hashed must not contain a raw VIN.")

    if not _VIN_HASH_PATTERN.fullmatch(vin_hashed):
        raise ValueError(
            "vin_hashed must be a lowercase 64-character SHA-256 hex digest."
        )


def _validate_failure_probability(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("failure_probability must be numeric.")

    if not math.isfinite(float(value)):
        raise ValueError("failure_probability must be finite.")

    if not 0.0 <= float(value) <= 1.0:
        raise ValueError("failure_probability must be within [0.0, 1.0].")


def _sanitize_window_summary(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if summary is None:
        return None

    if not isinstance(summary, dict):
        raise TypeError("window_summary must be a dict or None.")

    sanitized = _sanitize_value(summary)
    if not isinstance(sanitized, dict):
        raise TypeError("window_summary must sanitize to a dict.")

    _validate_iqr_bounds(sanitized)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("window_summary keys must be strings.")

            key_lower = key.lower()
            if key == "@context" or key_lower in _RESTRICTED_KEYS:
                continue
            if key_lower in {"raw_vin", "vin"}:
                raise ValueError("window_summary must not contain a raw VIN.")
            if "payload_bytes" in key_lower:
                continue

            sanitized[key] = _sanitize_value(item)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]

    if isinstance(value, bool) or value is None:
        return value

    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("window_summary contains a non-finite numeric value.")
        return value

    if isinstance(value, str):
        if _RAW_VIN_PATTERN.fullmatch(value):
            raise ValueError("window_summary must not contain a raw VIN.")
        return value

    raise TypeError(
        f"window_summary contains unsupported value type: {type(value).__name__}."
    )


def _validate_iqr_bounds(summary: Mapping[str, Any]) -> None:
    bounds = summary.get("iqr_bounds")
    if bounds is None:
        return

    if not isinstance(bounds, Mapping):
        raise TypeError("iqr_bounds must be a mapping when provided.")

    lower = bounds.get("lower")
    upper = bounds.get("upper")
    if lower is None or upper is None:
        return

    if isinstance(lower, bool) or isinstance(upper, bool):
        raise TypeError("iqr_bounds lower and upper must be numeric.")

    if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
        raise TypeError("iqr_bounds lower and upper must be numeric.")

    if lower > upper:
        raise ValueError("iqr_bounds lower value must not exceed upper value.")


__all__ = [
    "EVTelemetryAlert",
    "PdMAlert",
    "serialize_alert",
    "serialize_ev_alert",
]
