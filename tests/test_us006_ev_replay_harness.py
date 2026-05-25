"""US-006 EV replay and dirty-data harness tests."""

from __future__ import annotations

import math

import pytest
from jsonschema import ValidationError

from tests.simulation.virtual_replay import (
    EVMockAdapter,
    JSONLProvider,
    NoiseGenerator,
    ReplayMode,
    SecurityViolationError,
    replay_ev_sequence,
)


def ev_row(**overrides):
    row = {
        "timestamp": "2026-05-24T12:00:00.000Z",
        "vin_hashed": "f" * 64,
        "protocol": "SAE_J1979-3",
        "battery_soh": 95.0,
        "battery_soce": 80.0,
        "battery_temp_avg": 35.0,
    }
    row.update(overrides)
    return row


def test_rpl_001_soh_oscillation_replays_as_range_valid_dirty_sequence():
    rows = NoiseGenerator.inject_soh_oscillation([ev_row(), ev_row(), ev_row()])
    frames = replay_ev_sequence(rows)
    assert [frame.payload["battery_soh"] for frame in frames] == [95.0, 5.0, 95.0]


def test_rpl_002_soce_cliff_individual_frames_remain_schema_valid():
    rows = NoiseGenerator.inject_soce_cliff([ev_row(), ev_row()])
    frames = replay_ev_sequence(rows)
    assert [frame.payload["battery_soce"] for frame in frames] == [80.0, 0.0]


def test_rpl_003_nan_temperature_rejected_mid_replay():
    adapter = EVMockAdapter(JSONLProvider([ev_row(), ev_row(battery_temp_avg=math.nan)]))
    adapter.connect()
    adapter.fetch_frame()
    with pytest.raises(ValueError, match="non-finite"):
        adapter.fetch_frame()
    adapter.disconnect()


def test_rpl_004_near_ceiling_temperature_is_accepted():
    frames = replay_ev_sequence([ev_row(battery_temp_avg=79.0)])
    assert frames[0].payload["battery_temp_avg"] == 79.0


def test_rpl_005_motor_speed_sign_flip_schema_valid_when_documented():
    frames = replay_ev_sequence(
        [
            ev_row(traction_motor_speed=15000),
            ev_row(traction_motor_speed=-15000),
        ]
    )
    assert [frame.payload["traction_motor_speed"] for frame in frames] == [15000, -15000]


def test_rpl_006_required_field_dropout_rejected_without_crash():
    adapter = EVMockAdapter(JSONLProvider([ev_row(), ev_row(battery_soce=None)]))
    adapter.connect()
    adapter.fetch_frame()
    with pytest.raises(ValidationError):
        adapter.fetch_frame()
    adapter.disconnect()


def test_rpl_007_old_protocol_max_throughput_rejected():
    with pytest.raises(ValidationError):
        replay_ev_sequence([ev_row(battery_throughput=2.1e9)])


def test_rpl_008_old_protocol_max_grid_energy_rejected():
    with pytest.raises(ValidationError):
        replay_ev_sequence([ev_row(grid_energy_in=429496729.5)])


def test_rpl_009_protocol_change_for_same_vehicle_rejected():
    adapter = EVMockAdapter(
        JSONLProvider([ev_row(protocol="SAE_J1979-3"), ev_row(protocol="ISO_13400_DoIP")])
    )
    adapter.connect()
    adapter.fetch_frame()
    with pytest.raises(Exception):
        adapter.fetch_frame()
    adapter.disconnect()


def test_rpl_010_burst_mode_blocked_outside_test_environment():
    with pytest.raises(SecurityViolationError, match="BURST_MODE_VIOLATION"):
        replay_ev_sequence([ev_row()], mode=ReplayMode.BURST, env="prod")


def test_rpl_011_ice_field_inserted_in_ev_sequence_rejected():
    adapter = EVMockAdapter(JSONLProvider([ev_row(), ev_row(engine_rpm=3000)]))
    adapter.connect()
    adapter.fetch_frame()
    with pytest.raises(ValidationError):
        adapter.fetch_frame()
    adapter.disconnect()


def test_rpl_012_signed_integer_wrap_artifact_rejected():
    with pytest.raises(ValidationError):
        replay_ev_sequence([ev_row(traction_motor_speed=-32768)])
