"""US-006 EV telemetry schema validation tests."""

from __future__ import annotations

import copy
import json
import math

import pytest
from jsonschema import ValidationError

from autopulse.data.validator import (
    EV_OBD_FRAME_SCHEMA,
    load_ev_obd_frame_schema,
    validate_ev_frame,
)


VIN_HASH = "b" * 64


def valid_ev_frame(**overrides):
    frame = {
        "timestamp": "2026-05-24T12:00:00.123Z",
        "vin_hashed": VIN_HASH,
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


def with_payload(**overrides):
    frame = valid_ev_frame()
    payload = copy.deepcopy(frame["payload"])
    payload.update(overrides)
    frame["payload"] = payload
    return frame


def assert_valid(frame):
    validate_ev_frame(frame)
    json.dumps(frame, allow_nan=False)


class TestUS006PositiveCases:
    def test_pos_001_minimal_valid_ev_frame(self):
        assert_valid(valid_ev_frame())

    def test_pos_002_all_optional_fields_present(self):
        assert_valid(
            with_payload(
                traction_motor_speed=12000,
                battery_throughput=1000.0,
                grid_energy_in=2500.0,
            )
        )

    def test_pos_003_zero_motor_speed(self):
        assert_valid(with_payload(traction_motor_speed=0))

    def test_pos_004_negative_motor_speed_schema_allowed(self):
        assert_valid(with_payload(traction_motor_speed=-5000))

    def test_pos_005_depleted_soce_new_pack_soh(self):
        assert_valid(with_payload(battery_soce=0.0, battery_soh=100.0))

    def test_pos_006_full_soce_new_pack_soh(self):
        assert_valid(with_payload(battery_soce=100.0, battery_soh=100.0))

    def test_pos_007_zev_on_uds_protocol(self):
        assert_valid(valid_ev_frame(protocol="SAE_J1979-3"))

    def test_pos_008_doip_protocol(self):
        assert_valid(valid_ev_frame(protocol="ISO_13400_DoIP"))

    def test_pos_009_lowercase_sha256_vin_hash(self):
        assert_valid(valid_ev_frame(vin_hashed="a" * 64))

    def test_pos_010_millisecond_timestamp(self):
        assert_valid(valid_ev_frame(timestamp="2026-05-24T12:00:00.999Z"))

    def test_pos_011_zero_battery_throughput(self):
        assert_valid(with_payload(battery_throughput=0.0))

    def test_pos_012_schema_is_json_serializable(self):
        assert json.dumps(load_ev_obd_frame_schema())


NEGATIVE_CASES = [
    ("NEG-001", with_payload(battery_soh=-0.1)),
    ("NEG-002", with_payload(battery_soh=100.1)),
    ("NEG-003", with_payload(battery_soce=math.nan)),
    ("NEG-004", with_payload(battery_soce=math.inf)),
    ("NEG-005", with_payload(battery_temp_avg=80.001)),
    ("NEG-006", with_payload(battery_temp_avg=-40.001)),
    (
        "NEG-007",
        (lambda: (lambda f: (f["payload"].pop("battery_soh"), f)[1])(valid_ev_frame()))(),
    ),
    ("NEG-008", (lambda f: (f.pop("timestamp"), f)[1])(valid_ev_frame())),
    ("NEG-009", valid_ev_frame(vin_hashed="A" * 64)),
    ("NEG-010", valid_ev_frame(vin_hashed="1HGCM82633A004352")),
    ("NEG-011", with_payload(coolant_temp=88.0)),
    ("NEG-012", with_payload(stft_bank1=0.0, ltft_bank1=0.0)),
    ("NEG-013", with_payload(engine_rpm=3000.0)),
    ("NEG-014", valid_ev_frame(protocol="PROPRIETARY_OEM_X")),
    ("NEG-015", valid_ev_frame(powertrain_type="ICE")),
    ("NEG-016", with_payload(coolant_temp=88.0)),
    ("NEG-017", with_payload(battery_throughput=500000.001)),
    ("NEG-018", with_payload(grid_energy_in=-1.0)),
    ("NEG-019", with_payload(traction_motor_speed=20001)),
    ("NEG-020", with_payload(traction_motor_speed=-20001)),
    ("NEG-021", with_payload(mystery_param=42)),
    ("NEG-022", with_payload(battery_soh="high")),
    ("NEG-023", {}),
]


@pytest.mark.parametrize("case_id,frame", NEGATIVE_CASES, ids=[case[0] for case in NEGATIVE_CASES])
def test_negative_ev_schema_cases(case_id, frame):
    with pytest.raises((ValidationError, ValueError)):
        validate_ev_frame(frame)


BOUNDARY_CASES = [
    ("battery_soh", -0.001, False),
    ("battery_soh", 0.0, True),
    ("battery_soh", 0.001, True),
    ("battery_soh", 50.0, True),
    ("battery_soh", 99.999, True),
    ("battery_soh", 100.0, True),
    ("battery_soh", 100.001, False),
    ("battery_soce", -0.001, False),
    ("battery_soce", 0.0, True),
    ("battery_soce", 50.0, True),
    ("battery_soce", 100.0, True),
    ("battery_soce", 100.001, False),
    ("battery_temp_avg", -40.001, False),
    ("battery_temp_avg", -40.0, True),
    ("battery_temp_avg", -39.999, True),
    ("battery_temp_avg", 35.0, True),
    ("battery_temp_avg", 79.999, True),
    ("battery_temp_avg", 80.0, True),
    ("battery_temp_avg", 80.001, False),
    ("traction_motor_speed", -20001, False),
    ("traction_motor_speed", -20000, True),
    ("traction_motor_speed", -1, True),
    ("traction_motor_speed", 0, True),
    ("traction_motor_speed", 1, True),
    ("traction_motor_speed", 20000, True),
    ("traction_motor_speed", 20001, False),
    ("traction_motor_speed", 15000.5, False),
    ("battery_throughput", -0.001, False),
    ("battery_throughput", 0.0, True),
    ("battery_throughput", 500000.0, True),
    ("battery_throughput", 500000.001, False),
    ("battery_throughput", math.nan, False),
    ("battery_throughput", math.inf, False),
    ("grid_energy_in", -0.001, False),
    ("grid_energy_in", 0.0, True),
    ("grid_energy_in", 500000.0, True),
    ("grid_energy_in", 1000000.0, True),
    ("grid_energy_in", 1000000.001, False),
    ("grid_energy_in", math.nan, False),
]


@pytest.mark.parametrize(
    "field_name,value,expected_valid",
    BOUNDARY_CASES,
    ids=[f"{field}:{value}" for field, value, _ in BOUNDARY_CASES],
)
def test_boundary_matrix(field_name, value, expected_valid):
    frame = with_payload(**{field_name: value})
    if expected_valid:
        validate_ev_frame(frame)
    else:
        with pytest.raises((ValidationError, ValueError)):
            validate_ev_frame(frame)


def test_schema_describes_soce_and_throughput_semantics():
    payload_props = EV_OBD_FRAME_SCHEMA["properties"]["payload"]["properties"]
    assert "not driver-facing State of Charge" in payload_props["battery_soce"]["description"]
    assert "Negative values are not permitted" in payload_props["battery_throughput"]["description"]
