"""Production-backed #119 / policy T1, T2 and R1 temporal regressions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
import time

import pytest

from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.data.validator import validate_frame


_BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def frame(seconds=0, **overrides):
    result = {
        "timestamp": (_BASE + timedelta(seconds=seconds)).isoformat(),
        "vin_hashed": "a" * 64,
        "protocol": "SAE_J1979",
        "engine_rpm": 850.0,
        "vehicle_speed": 0,
        "coolant_temp": 88.0,
        "engine_load": 18.0,
        "stft_bank1": 0.0,
        "ltft_bank1": 0.0,
        "ambient_temp": 22.0,
    }
    result.update(overrides)
    return result


def state(processor):
    """Snapshot every processor field, including buffer heads and detectors."""
    return deepcopy({
        key: vars(value) if hasattr(value, "__dict__") else value
        for key, value in vars(processor).items()
    })


@pytest.mark.parametrize("timestamp", [None, "", "bad", "nan", "inf", float("nan"),
    float("inf"), -float("inf"), True, False, [], {}, 10**400,
    "9999-12-31T23:59:59-01:00", "0001-01-01T00:00:00+01:00"])
@pytest.mark.parametrize("seeded", [False, True])
def test_invalid_time_rejected_before_any_mutation(timestamp, seeded):
    processor = PdMProcessor("a" * 64)
    if seeded:
        processor.process_frame(frame())
        processor.process_frame(frame(1))
    before = state(processor)
    invalid = frame(2, timestamp=timestamp)
    if timestamp is None:
        del invalid["timestamp"]
    with pytest.raises(ValueError, match="timestamp"):
        processor.process_frame(invalid)
    assert state(processor) == before


@pytest.mark.parametrize("seconds", [0, -1, 0.0001])
def test_non_increasing_time_and_submillisecond_duplicate_are_atomic(seconds):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    before = state(processor)
    with pytest.raises(ValueError, match="increase"):
        processor.process_frame(frame(seconds, coolant_temp=40))
    assert state(processor) == before
    processor.process_frame(frame(1))
    assert processor.osf_detector.s_idx == 0


@pytest.mark.parametrize("timestamp,expected", [
    (0, 0), (0.9, 0), (-1, -1),
    ("1970-01-01T00:00:00Z", 0),
    ("1970-01-01T01:00:00+01:00", 0),
    ("1970-01-01T00:00:00.123999", 123),
    ("1969-12-31T23:59:59.999Z", -1),
])
def test_timestamp_representations(timestamp, expected):
    alert = PdMProcessor("a" * 64).process_frame(frame(timestamp=timestamp))
    assert alert.timestamp == expected
    assert alert.failure_probability == 0


def test_naive_iso_is_utc_independent_of_host_timezone(monkeypatch):
    if not hasattr(time, "tzset"):
        pytest.skip("tzset unavailable; UTC conversion covered by representation tests")
    original = os.environ.get("TZ")
    try:
        for zone in ("UTC0", "EST5EDT"):
            monkeypatch.setenv("TZ", zone)
            time.tzset()
            alert = PdMProcessor("a" * 64).process_frame(frame(timestamp="1970-01-01T00:00:00"))
            assert alert.timestamp == 0
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


def test_first_frame_seeds_filters_with_zero_branch_contributions():
    processor = PdMProcessor("a" * 64)
    first = frame(coolant_temp=22)  # legacy HDF would return 1 here
    validate_frame(first)
    alert = processor.process_frame(first)
    assert alert.failure_probability == 0
    assert alert.failure_type == "NONE"
    assert processor.osf_detector.s_idx == 0
    assert processor.last_coolant_temp == 22
    assert processor.rpm_buffer.to_list() == [850]
    assert processor._rpm_median_buffer.to_list() == [850]


@pytest.mark.parametrize("gap", [60, 60.001, 3600])
def test_gap_boundary_and_no_stale_temperature_or_stress(gap):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    processor.process_frame(frame(1))
    next_frame = frame(1 + gap, coolant_temp=-40)
    validate_frame(next_frame)
    alert = processor.process_frame(next_frame)
    if gap == 60:
        assert len(processor.coolant_buffer) == 3
        assert processor.osf_detector.s_idx == 0
    else:
        fresh = PdMProcessor("a" * 64)
        assert alert == fresh.process_frame(next_frame)
        assert state(processor) == state(fresh)
        assert processor.coolant_buffer.to_list() == [-40]
        assert processor.osf_detector.s_idx == 0


@pytest.mark.parametrize("gap", [1, 61])
@pytest.mark.parametrize("invalid", [{"engine_load": float("nan")},
    {"ambient_temp": float("inf")}, {"coolant_temp": None}, {"engine_rpm": "bad"}])
def test_bad_sensor_cannot_reset_or_advance_state(gap, invalid):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    before = state(processor)
    assert processor.process_frame(frame(gap, **invalid)).failure_type == "SENSOR_ERROR"
    assert state(processor) == before


@pytest.mark.parametrize("gap", [1, 61])
def test_missing_pid_cannot_reset_session(gap):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    before = state(processor)
    invalid = frame(gap)
    del invalid["engine_rpm"]
    assert processor.process_frame(invalid).primary_pid == 0x0C
    assert state(processor) == before


@pytest.mark.parametrize("gap", [1, 61])
def test_smoothing_rejection_rolls_back_entire_session(monkeypatch, gap):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    processor.process_frame(frame(1))
    def fail():
        processor._rpm_median_buffer.push(999)
        raise ValueError("synthetic smoothing failure")
    monkeypatch.setattr(processor, "_smooth_current_values", fail)
    before = state(processor)
    assert processor.process_frame(frame(1 + gap)).failure_type == "SENSOR_ERROR"
    assert state(processor) == before


def test_thermal_rejection_uses_last_accepted_timestamp_and_rate_boundary():
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame())
    before = state(processor)
    assert processor.process_frame(frame(1, coolant_temp=94)).failure_type == "SENSOR_ERROR"
    assert state(processor) == before
    # 10 degrees over two seconds is exactly the existing guard boundary.
    assert processor.process_frame(frame(2, coolant_temp=98)).failure_type != "SENSOR_ERROR"
    assert processor.last_timestamp == (_BASE + timedelta(seconds=2)).timestamp()
    assert processor.osf_detector.s_idx == 0


def test_reset_and_repeated_replay_match_fresh_processor(monkeypatch):
    def forbidden_clock():
        raise AssertionError("offline processing consulted wall time")
    monkeypatch.setattr(time, "time", forbidden_clock)
    frames = [frame(t, engine_rpm=1000, engine_load=90) for t in (0, 1, 2, 30, 90, 151, 152)]
    for item in frames:
        validate_frame(item)
    processor = PdMProcessor("a" * 64, vehicle_class="H", window_size=7)
    def replay(target):
        timeline = []
        for item in frames:
            alert = target.process_frame(item)
            timeline.append((alert, state(target)))
        return timeline
    expected = replay(processor)
    assert processor.osf_detector.s_idx > 0
    processor.reset()
    fresh = PdMProcessor("a" * 64, vehicle_class="H", window_size=7)
    assert state(processor) == state(fresh)
    assert replay(processor) == replay(fresh) == expected


@pytest.mark.parametrize("interval,span", [(0.5, 29.5), (1, 59), (2, 118)])
def test_window_remains_sixty_samples_at_different_cadences(interval, span):
    processor = PdMProcessor("a" * 64)
    for i in range(61):
        item = frame(i * interval, engine_rpm=1000 + i)
        validate_frame(item)
        processor.process_frame(item)
    assert processor.rpm_buffer.to_list() == list(range(1001, 1061))
    assert processor._rpm_median_buffer.is_full
    assert (60 - 1) * interval == span
