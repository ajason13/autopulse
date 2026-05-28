"""Safe debugging helpers for AutoPulse telemetry workflows."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Mapping


RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
VIN_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = frozenset(
    {
        "raw_vin",
        "payload_bytes",
        "seed",
        "key",
        "token",
        "secret",
    }
)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger without configuring global handlers."""
    return logging.getLogger(name)


def sanitize_debug_value(value: Any, *, validate_vin_shape: bool = False) -> Any:
    """Return a debug-safe copy of a value.

    Raw VIN-like strings and sensitive key names are redacted. ``vin_hashed`` is
    preserved when it is a valid public vehicle identifier required by AutoPulse
    audit trails. Runtime logging callers can require SHA-256 shape validation
    so malformed ``vin_hashed`` values are redacted instead of preserved.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = _sanitize_vin_hash(
                    item,
                    validate_vin_shape=validate_vin_shape,
                )
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(
                item,
                validate_vin_shape=validate_vin_shape,
            )
        return sanitized

    if isinstance(value, list):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, str):
        return RAW_VIN_PATTERN.sub(REDACTED, value)

    return value


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured, sanitized debug event."""
    if not logger.isEnabledFor(level):
        return

    payload = {
        "event": event,
        **sanitize_debug_value(fields, validate_vin_shape=True),
    }
    _validate_finite_numbers(payload)
    logger.log(level, json.dumps(payload, allow_nan=False, sort_keys=True))


def _sanitize_vin_hash(value: Any, *, validate_vin_shape: bool) -> Any:
    sanitized = sanitize_debug_value(value, validate_vin_shape=validate_vin_shape)
    if not validate_vin_shape:
        return sanitized
    if isinstance(sanitized, str) and VIN_HASH_PATTERN.fullmatch(sanitized):
        return sanitized
    return REDACTED


def _validate_finite_numbers(value: Any) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("log_event fields must not contain non-finite numbers.")
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _validate_finite_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_finite_numbers(item)


__all__ = [
    "RAW_VIN_PATTERN",
    "REDACTED",
    "VIN_HASH_PATTERN",
    "get_logger",
    "log_event",
    "sanitize_debug_value",
]
