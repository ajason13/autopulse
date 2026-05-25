"""US-006 EV JSON-LD alert serialization tests."""

from __future__ import annotations

import json
import math

import pytest

from autopulse.alert_exporter import EVTelemetryAlert, serialize_ev_alert


VIN_A = "a" * 64
VIN_B = "b" * 64
RAW_VIN = "1HGCM82633A004352"


def ev_alert(**overrides):
    kwargs = {
        "vin_hashed": VIN_A,
        "event_type": "EV_SCHEMA_REJECTION",
        "evidence": {
            "battery_temp_avg": 81.0,
            "powertrain_type": "EV",
        },
    }
    kwargs.update(overrides)
    return EVTelemetryAlert(**kwargs)


def assert_json_safe(payload):
    dumped = json.dumps(payload, allow_nan=False)
    assert "NaN" not in dumped
    assert "Infinity" not in dumped


def test_als_001_schema_rejection_alert_uses_hashed_vin_only():
    result = serialize_ev_alert(ev_alert())
    assert result["vin_hashed"] == VIN_A
    assert RAW_VIN not in json.dumps(result)


def test_als_002_battery_temperature_value_is_finite():
    result = serialize_ev_alert(ev_alert())
    assert result["evidence"]["battery_temp_avg"] == 81.0
    assert_json_safe(result)


def test_als_003_security_violation_does_not_leak_payload_bytes():
    result = serialize_ev_alert(
        ev_alert(
            event_type="SECURITY_VIOLATION_RED_LINE",
            evidence={"service_id": "0x31", "payload_bytes": "DE AD BE EF"},
        )
    )
    assert result["event_type"] == "SECURITY_VIOLATION_RED_LINE"
    assert "payload_bytes" not in result["evidence"]


def test_als_004_valid_ev_informational_alert_is_json_safe():
    result = serialize_ev_alert(ev_alert(event_type="EV_VALIDATION_EVENT"))
    assert_json_safe(result)
    assert result["@type"] == "sosa:Observation"


def test_als_005_rejected_error_message_cannot_contain_raw_vin():
    with pytest.raises(ValueError):
        serialize_ev_alert(ev_alert(evidence={"message": RAW_VIN}))


def test_als_006_batch_alerts_do_not_cross_leak_vin_hashes():
    alerts = [
        serialize_ev_alert(ev_alert(vin_hashed=VIN_A)),
        serialize_ev_alert(ev_alert(vin_hashed=VIN_B)),
    ]
    assert alerts[0]["vin_hashed"] == VIN_A
    assert alerts[1]["vin_hashed"] == VIN_B


def test_als_007_powertrain_spoofing_alert_records_claimed_and_detected():
    result = serialize_ev_alert(
        ev_alert(
            event_type="POWERTRAIN_ROUTING_MISMATCH",
            evidence={"claimed": "ICE", "detected": "EV"},
        )
    )
    assert result["evidence"] == {"claimed": "ICE", "detected": "EV"}


@pytest.mark.parametrize("speed", [-20000, 0, 20000])
def test_als_008_motor_speed_boundary_serializes_as_integer(speed):
    result = serialize_ev_alert(ev_alert(evidence={"traction_motor_speed": speed}))
    assert result["evidence"]["traction_motor_speed"] == speed
    assert isinstance(result["evidence"]["traction_motor_speed"], int)


def test_als_009_ev_alert_carries_powertrain_type():
    result = serialize_ev_alert(ev_alert())
    assert result["powertrain_type"] == "EV"


def test_als_010_ev_context_terms_are_defined():
    result = serialize_ev_alert(ev_alert())
    ctx = result["@context"]
    for term in ["battery_soh", "battery_soce", "battery_temp_avg", "traction_motor_speed"]:
        assert term in ctx


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_ev_alert_rejects_non_finite_numbers(bad_value):
    with pytest.raises(ValueError):
        serialize_ev_alert(ev_alert(evidence={"battery_soce": bad_value}))
