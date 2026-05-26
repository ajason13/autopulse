"""Safe debugging helpers for AutoPulse telemetry workflows."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Mapping


RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = frozenset(
    {
        "raw_vin",
        "vin",
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


def sanitize_debug_value(value: Any) -> Any:
    """Return a debug-safe copy of a value.

    Raw VIN-like strings and sensitive key names are redacted. ``vin_hashed`` is
    preserved because it is the public vehicle identifier required by AutoPulse
    audit trails.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = sanitize_debug_value(item)
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(item)
        return sanitized

    if isinstance(value, list):
        return [sanitize_debug_value(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_debug_value(item) for item in value]

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

    payload = {"event": event, **sanitize_debug_value(fields)}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))


__all__ = [
    "RAW_VIN_PATTERN",
    "REDACTED",
    "get_logger",
    "log_event",
    "sanitize_debug_value",
]
