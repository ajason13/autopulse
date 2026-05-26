"""Debugging support tests for sanitized logs and CLI output."""

from __future__ import annotations

import json
import logging

import pytest

from autopulse.debug import main as debug_main
from autopulse.debugging import REDACTED, log_event, sanitize_debug_value
from autopulse.data.validator import command_filter


RAW_VIN = "1HGCM82633A004352"
VIN_HASHED = "a" * 64


def test_sanitize_debug_value_redacts_raw_vin_and_sensitive_keys() -> None:
    value = {
        "raw_vin": RAW_VIN,
        "vin_hashed": VIN_HASHED,
        "nested": {
            "payload_bytes": "2E F4 B2 00",
            "message": f"blocked raw VIN {RAW_VIN}",
        },
    }

    sanitized = sanitize_debug_value(value)

    assert sanitized["raw_vin"] == REDACTED
    assert sanitized["vin_hashed"] == VIN_HASHED
    assert sanitized["nested"]["payload_bytes"] == REDACTED
    assert sanitized["nested"]["message"] == f"blocked raw VIN {REDACTED}"
    assert RAW_VIN not in json.dumps(sanitized)
    assert "2E F4 B2 00" not in json.dumps(sanitized)


def test_log_event_emits_json_without_raw_vin_or_payload_bytes(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging"):
        log_event(
            logger,
            logging.DEBUG,
            "debug_test",
            raw_vin=RAW_VIN,
            vin_hashed=VIN_HASHED,
            payload_bytes="2E F4 B2 00",
            service_id="0x2E",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["event"] == "debug_test"
    assert payload["raw_vin"] == REDACTED
    assert payload["vin_hashed"] == VIN_HASHED
    assert payload["payload_bytes"] == REDACTED
    assert payload["service_id"] == "0x2E"
    assert RAW_VIN not in caplog.text
    assert "2E F4 B2 00" not in caplog.text


def test_security_block_logging_omits_raw_payload_bytes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="autopulse.data.validator"):
        with pytest.raises(Exception):
            command_filter(0x2E)

    assert "security_service_blocked" in caplog.text
    assert "0x2E" in caplog.text
    assert RAW_VIN not in caplog.text
    assert "payload_bytes" not in caplog.text


def test_debug_cli_validate_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979-3",
        "powertrain_type": "EV",
        "payload": {
            "battery_soh": 95.0,
            "battery_soce": 80.0,
            "battery_temp_avg": 35.0,
            "payload_bytes": "2E F4 B2 00",
        },
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "EV",
            "--json",
            json.dumps(frame),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValidationError"
    assert RAW_VIN not in captured.out
    assert "2E F4 B2 00" not in captured.out
