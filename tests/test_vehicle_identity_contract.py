"""Exact vehicle identity constraints across schemas and ingestion paths."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker, ValidationError

from autopulse.data.validator import validate_ev_frame, validate_frame
from autopulse.virtual_replay import EVMockAdapter, JSONLProvider, MockAdapter


ROOT = Path(__file__).resolve().parents[1]
VALID_HASH = "0123456789abcdef" * 4
INVALID_HASHES = [
    "",
    "a" * 63,
    "a" * 65,
    VALID_HASH + "\n",
    VALID_HASH + "\r\n",
    VALID_HASH.upper(),
    "g" * 64,
    " " + "a" * 63,
]


@pytest.fixture(params=["ICE", "EV"])
def frame(request):
    common = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": VALID_HASH,
    }
    if request.param == "EV":
        return {
            **common,
            "protocol": "SAE_J1979-3",
            "powertrain_type": "EV",
            "payload": {
                "battery_soh": 95.0,
                "battery_soce": 80.0,
                "battery_temp_avg": 35.0,
            },
        }
    return {
        **common,
        "protocol": "SAE_J1979",
        "engine_rpm": 800.0,
        "vehicle_speed": 0,
        "coolant_temp": 88.0,
        "engine_load": 15.0,
        "stft_bank1": 0.0,
        "ltft_bank1": 0.0,
    }


@pytest.mark.parametrize("source", ["schemas", "src/autopulse/schemas"])
def test_canonical_and_packaged_identity_constraints(frame, source):
    filename = (
        "ev_obd_frame.schema.json"
        if frame.get("powertrain_type") == "EV"
        else "engine_obd_frame.schema.json"
    )
    schema = json.loads((ROOT / source / filename).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    validator.validate(frame)
    for invalid_hash in INVALID_HASHES:
        with pytest.raises(ValidationError):
            validator.validate({**frame, "vin_hashed": invalid_hash})


def test_production_validator_enforces_exact_identity(frame):
    validate = validate_ev_frame if frame.get("powertrain_type") == "EV" else validate_frame
    validate(frame)
    for invalid_hash in INVALID_HASHES:
        with pytest.raises(ValidationError):
            validate({**frame, "vin_hashed": invalid_hash})


def test_replay_rejects_invalid_identity_and_preserves_valid_identity(frame):
    adapter_type = EVMockAdapter if frame.get("powertrain_type") == "EV" else MockAdapter
    # Missing/empty identity is intentionally defaulted by replay normalization.
    rows = [{**frame, "vin_hashed": value} for value in INVALID_HASHES if value]
    adapter = adapter_type(JSONLProvider([*rows, frame]))
    adapter.connect()
    try:
        for _ in rows:
            with pytest.raises(ValidationError):
                adapter.fetch_frame()
        assert adapter.fetch_frame().vin_hashed == VALID_HASH
    finally:
        adapter.disconnect()
