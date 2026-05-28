"""Debugging support tests for sanitized logs and CLI output."""

from __future__ import annotations

import json
import logging
import math

import pytest

from autopulse import debug as debug_module
from autopulse.debug import main as debug_main
from autopulse.debugging import (
    REDACTED,
    log_event,
    sanitize_debug_value,
)
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


def test_sanitize_debug_value_redacts_nested_raw_vins() -> None:
    value = {"outer": {"inner": {"msg": f"VIN is {RAW_VIN}"}}}

    sanitized = sanitize_debug_value(value)

    assert RAW_VIN not in json.dumps(sanitized)
    assert sanitized["outer"]["inner"]["msg"] == f"VIN is {REDACTED}"


def test_sanitize_debug_value_preserves_non_sensitive_vin_substrings() -> None:
    sanitized = sanitize_debug_value(
        {
            "conviction_score": 0.9,
            "provisioning_step": "validate",
            "raw_vin": RAW_VIN,
        }
    )

    assert sanitized["conviction_score"] == 0.9
    assert sanitized["provisioning_step"] == "validate"
    assert sanitized["raw_vin"] == REDACTED


def test_sanitize_debug_value_redacts_raw_vin_in_lists() -> None:
    sanitized = sanitize_debug_value(["normal", RAW_VIN, f"seen {RAW_VIN}"])

    assert sanitized == ["normal", REDACTED, f"seen {REDACTED}"]


def test_sanitize_debug_value_can_redact_malformed_vin_hashed() -> None:
    sanitized = sanitize_debug_value(
        {"vin_hashed": "not-a-sha256-hash"},
        validate_vin_shape=True,
    )

    assert sanitized["vin_hashed"] == REDACTED


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


def test_log_event_redacts_malformed_vin_hashed(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging.vin_hash")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.vin_hash"):
        log_event(
            logger,
            logging.DEBUG,
            "debug_test",
            vin_hashed="not-a-sha256-hash",
        )

    payload = json.loads(caplog.records[0].message)
    assert payload["vin_hashed"] == REDACTED


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_log_event_rejects_non_finite_numbers(
    value: float,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.debugging.non_finite")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.non_finite"):
        with pytest.raises(ValueError, match="non-finite"):
            log_event(logger, logging.DEBUG, "debug_test", score=value)

    assert len(caplog.records) == 0


def test_log_event_redacts_secret_and_token(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.debugging.secrets")

    with caplog.at_level(logging.DEBUG, logger="tests.debugging.secrets"):
        log_event(
            logger,
            logging.DEBUG,
            "auth_attempt",
            secret="sk-abc123",
            token="Bearer xyz",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["secret"] == REDACTED
    assert payload["token"] == REDACTED
    assert "sk-abc123" not in caplog.text
    assert "Bearer xyz" not in caplog.text


def test_log_event_emits_nothing_when_level_disabled(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.level_guard")
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        with caplog.at_level(logging.WARNING, logger="tests.level_guard"):
            log_event(logger, logging.DEBUG, "should_not_emit", secret="sk-abc")
    finally:
        logger.setLevel(original_level)

    assert len(caplog.records) == 0
    assert "sk-abc" not in caplog.text


def test_security_block_logging_omits_raw_payload_bytes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="autopulse.data.validator"):
        with pytest.raises(Exception):
            command_filter(0x2E)

    assert "security_service_blocked" in caplog.text
    assert "0x2E" in caplog.text
    assert RAW_VIN not in caplog.text
    assert "payload_bytes" not in caplog.text


def test_debug_cli_validate_ev_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
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


def test_debug_cli_validate_ice_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979",
        "engine_rpm": 900.0,
        "vehicle_speed": 40,
        "coolant_temp": 90.0,
        "engine_load": 32.0,
        "stft_bank1": 1.0,
        "ltft_bank1": -1.0,
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "ICE",
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


def test_debug_cli_validate_routed_frame_sanitizes_schema_errors(capsys: pytest.CaptureFixture[str]) -> None:
    frame = {
        "timestamp": "2026-05-25T00:00:00Z",
        "vin_hashed": RAW_VIN,
        "protocol": "SAE_J1979-3",
        "powertrain_type": "EV",
        "payload": {
            "battery_soh": 95.0,
            "battery_soce": 80.0,
            "battery_temp_avg": 35.0,
        },
    }

    exit_code = debug_main(
        [
            "validate-frame",
            "--powertrain",
            "ROUTED",
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


def test_debug_cli_verbose_logging_is_scoped_to_autopulse_logger() -> None:
    root_logger = logging.getLogger()
    autopulse_logger = logging.getLogger("autopulse")
    original_root_level = root_logger.level
    original_autopulse_level = autopulse_logger.level
    original_handlers = list(autopulse_logger.handlers)

    try:
        debug_module._configure_logging(True)

        assert root_logger.level == original_root_level
        assert autopulse_logger.level == logging.DEBUG
        assert any(
            getattr(handler, "_autopulse_debug_cli", False)
            for handler in autopulse_logger.handlers
        )
    finally:
        autopulse_logger.handlers = original_handlers
        autopulse_logger.setLevel(original_autopulse_level)
        root_logger.setLevel(original_root_level)
