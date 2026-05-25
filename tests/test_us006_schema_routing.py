"""US-006 cross-schema isolation and routing tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError

from autopulse.data.validator import (
    EV_PROTOCOLS,
    ICE_PROTOCOLS,
    RoutingError,
    load_engine_obd_frame_schema,
    load_ev_obd_frame_schema,
    route_and_validate,
    validate_ev_frame,
    validate_frame,
)


ROOT = Path(__file__).resolve().parents[1]


def ice_payload(**overrides):
    frame = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": "c" * 64,
        "protocol": "SAE_J1979",
        "engine_rpm": 800.0,
        "vehicle_speed": 0,
        "coolant_temp": 88.0,
        "engine_load": 15.0,
        "stft_bank1": 0.0,
        "ltft_bank1": 0.0,
    }
    frame.update(overrides)
    return frame


def ev_frame(**overrides):
    frame = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": "d" * 64,
        "protocol": "SAE_J1979-3",
        "powertrain_type": "EV",
        "payload": {
            "battery_soh": 95.0,
            "battery_soce": 80.0,
            "battery_temp_avg": 35.0,
        },
    }
    frame.update(overrides)
    return frame


def routed_ice_frame(**overrides):
    frame = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": "c" * 64,
        "protocol": "SAE_J1979",
        "powertrain_type": "ICE",
        "payload": ice_payload(),
    }
    frame.update(overrides)
    return frame


def test_iso_001_us001_required_fields_unchanged():
    schema = load_engine_obd_frame_schema()
    assert set(schema["required"]) == {
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


def test_iso_002_ev_schema_does_not_ref_us001_schema():
    schema_text = (ROOT / "schemas" / "ev_obd_frame.schema.json").read_text()
    assert "engine_obd_frame.schema.json" not in schema_text
    assert "$ref" not in json.loads(schema_text)


def test_iso_003_ice_frame_rejected_by_ev_validator():
    with pytest.raises(ValidationError):
        validate_ev_frame(ice_payload())


def test_iso_004_ev_payload_rejected_by_ice_validator():
    with pytest.raises(ValidationError):
        validate_frame(ev_frame()["payload"])


def test_iso_005_ice_routes_only_to_ice_validator():
    assert route_and_validate(routed_ice_frame()) == "ICE"


def test_iso_006_ev_routes_only_to_ev_validator():
    assert route_and_validate(ev_frame()) == "EV"


def test_iso_007_hybrid_is_unsupported():
    with pytest.raises(RoutingError):
        route_and_validate(ev_frame(powertrain_type="HYBRID"))


def test_iso_008_absent_powertrain_type_rejected():
    frame = ev_frame()
    frame.pop("powertrain_type")
    with pytest.raises(RoutingError):
        route_and_validate(frame)


def test_iso_009_ev_schema_has_no_ice_required_field_overlap():
    ev_payload_props = set(
        load_ev_obd_frame_schema()["properties"]["payload"]["properties"]
    )
    ice_required = set(load_engine_obd_frame_schema()["required"])
    assert ev_payload_props.isdisjoint(ice_required)


def test_iso_010_existing_ice_validation_still_accepts_valid_frame():
    validate_frame(ice_payload(protocol="SAE_J1979-2"))


def test_iso_011_ice_and_ev_protocol_enums_are_disjoint():
    assert ICE_PROTOCOLS.isdisjoint(EV_PROTOCOLS)


def test_iso_012_protocol_powertrain_mismatch_rejected_at_envelope():
    with pytest.raises(RoutingError):
        route_and_validate(routed_ice_frame(protocol="SAE_J1979-3"))
