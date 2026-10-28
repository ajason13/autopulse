"""Production-backed #120 acceptance vectors O1–O5, T2 and R1."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from autopulse.analysis.osf_detector import OSFDetector
from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.data.validator import validate_frame


_BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def frame(seconds, rpm=1000, load=90, **overrides):
    item = {
        "timestamp": (_BASE + timedelta(seconds=seconds)).isoformat(),
        "vin_hashed": "a" * 64, "protocol": "SAE_J1979",
        "engine_rpm": rpm, "engine_load": load,
        "coolant_temp": 88, "vehicle_speed": 0,
        "stft_bank1": 0, "ltft_bank1": 0,
    }
    item.update(overrides)
    validate_frame(item)
    return item


def snapshot(processor):
    return deepcopy({key: vars(value) if hasattr(value, "__dict__") else value
                     for key, value in vars(processor).items()})


@pytest.mark.parametrize("vehicle_class", ["L", "M", "H"])
@pytest.mark.parametrize("step", [0.5, 1, 2])
@pytest.mark.parametrize("rpm,load", [(850, 18), (2000, 40)])
def test_o1_healthy_streams_never_accumulate_exposure(vehicle_class, step, rpm, load):
    processor = PdMProcessor("a" * 64, vehicle_class)
    for index in range(int(600 / step) + 1):
        alert = processor.process_frame(frame(index * step, rpm, load))
        assert processor.osf_detector.s_idx == 0
        assert processor.osf_detector.compute_probability() == 0
        assert alert.failure_type == "NONE"
        assert alert.failure_probability == 0


@pytest.mark.parametrize("step", [0.5, 1, 2])
def test_o2_processor_constant_fault_input(step):
    processor = PdMProcessor("a" * 64)
    for index in range(int(120 / step) + 1):
        seconds = index * step
        alert = processor.process_frame(frame(seconds))
        expected = min(seconds / 60, 1)
        assert processor.osf_detector.compute_probability() == pytest.approx(expected)
        assert alert.failure_probability == pytest.approx(expected)
        assert alert.failure_type == ("NONE" if expected <= 0.5 else
                                      "OSF_ANOMALY" if expected < 1 else "OSF")
        assert alert.is_anomaly == (expected > 0.5)


def test_o3_left_hold_and_exact_partial_expiry():
    detector = OSFDetector()
    previous = 0
    for seconds, load, expected in [(0, 90, 0), (30, 18, 30), (60, 18, 30),
                                     (75, 18, 15), (75.25, 18, 14.75), (90, 18, 0)]:
        detector.update(load, 1000, seconds - previous)
        assert detector.s_idx == pytest.approx(expected, abs=1e-9)
        assert detector.compute_probability() == pytest.approx(expected / 60, abs=1e-9)
        previous = seconds
    assert not detector._intervals


@pytest.mark.parametrize("rpm,load,expected", [(1500, 90, 0), (1000, 80, 0),
    (0, 90, 0), (1499, 80.1, 1), (1000, 100, 1), (9500, 90, 0)])
def test_o4_indicator_strict_boundaries(rpm, load, expected):
    detector = OSFDetector()
    detector.update(load, rpm, 0)
    detector.update(load, rpm, 1)
    assert detector.s_idx == expected


def test_o4_raw_off_resets_only_osf_and_restart_seeds_new_history():
    processor = PdMProcessor("a" * 64)
    for seconds in range(32):
        processor.process_frame(frame(seconds, ambient_temp=22))
    assert processor.osf_detector.s_idx == 31
    off = processor.process_frame(frame(32, rpm=0, ambient_temp=22))
    assert off.failure_type == "STATISTICAL_ANOMALY"  # raw gate still executes
    assert processor.osf_detector.s_idx == 0
    assert processor.osf_detector._held_exposure is None
    assert not processor.osf_detector._intervals
    assert processor._rpm_median_buffer.get_ewma(0.3) > 0
    assert len(processor.rpm_buffer) == 33
    assert processor.last_coolant_temp == 88
    assert processor.last_timestamp == (_BASE + timedelta(seconds=32)).timestamp()
    processor.process_frame(frame(33, ambient_temp=22))
    assert processor.osf_detector.s_idx == 0
    processor.process_frame(frame(34, ambient_temp=22))
    assert processor.osf_detector.s_idx == 1


@pytest.mark.parametrize("step", [0.5, 1, 2, None])
def test_o5_same_indicator_trajectory_is_cadence_invariant(step):
    checkpoints = [0, 1, 30, 31, 60, 75, 75.25, 90, 120]
    if step is None:
        subdivisions = [0.125, 3.875, 29.999, 30.125, 43.75, 74.125, 100.001]
    else:
        subdivisions = [index * step for index in range(int(120 / step) + 1)]
    detector = OSFDetector()
    previous = 0
    for seconds in sorted(set(checkpoints + subdivisions)):
        detector.update(90 if seconds < 30 else 18, 1000, seconds - previous)
        if seconds in checkpoints:
            expected = max(0, min(seconds, 30) - max(0, seconds - 60))
            assert detector.s_idx == pytest.approx(expected, abs=1e-9)
            assert detector.compute_probability() == pytest.approx(expected / 60, abs=1e-9)
        previous = seconds


@pytest.mark.parametrize("gap,expected", [(60, 1), (60.001, 0), (3600, 0)])
def test_t2_first_frame_and_gap_boundary(gap, expected):
    processor = PdMProcessor("a" * 64)
    assert processor.process_frame(frame(0)).failure_probability == 0
    assert processor.osf_detector.s_idx == 0
    alert = processor.process_frame(frame(gap))
    assert processor.osf_detector.compute_probability() == expected
    assert alert.failure_probability == expected


def test_r1_reset_replay_matches_fresh_processor():
    items = [frame(t, load=90 if t < 30 else 18) for t in (0, 1, 30, 31, 60, 75.25)]
    def replay(processor):
        return [(processor.process_frame(item), snapshot(processor)) for item in items]
    processor = PdMProcessor("a" * 64)
    expected = replay(processor)
    assert processor.osf_detector.s_idx > 0
    processor.reset()
    assert replay(processor) == replay(PdMProcessor("a" * 64)) == expected


@pytest.mark.parametrize("invalid", ["timestamp", "sensor", "rate", "smoothing"])
def test_rejections_preserve_positive_exposure_and_held_sample(monkeypatch, invalid):
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame(0))
    processor.process_frame(frame(1))
    item = frame(2, rpm=0)
    if invalid == "timestamp":
        item["timestamp"] = frame(1)["timestamp"]
    elif invalid == "sensor":
        item["engine_load"] = float("nan")
    elif invalid == "rate":
        item["coolant_temp"] = 94
    else:
        def reject():
            raise ValueError("synthetic smoothing rejection")
        monkeypatch.setattr(processor, "_smooth_current_values", reject)
    before = snapshot(processor)
    if invalid == "timestamp":
        with pytest.raises(ValueError):
            processor.process_frame(item)
    else:
        assert processor.process_frame(item).failure_type == "SENSOR_ERROR"
    assert snapshot(processor) == before
    if invalid == "smoothing":
        monkeypatch.undo()
    processor.process_frame(frame(3))
    assert processor.osf_detector.s_idx == 3


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_detector_rejects_invalid_elapsed_before_mutation(value):
    detector = OSFDetector()
    detector.update(90, 1000, 0)
    detector.update(90, 1000, 1)
    before = deepcopy(vars(detector))
    with pytest.raises(ValueError):
        detector.update(90, 1000, value)
    assert vars(detector) == before


def test_continuous_exposure_history_merges_and_expires():
    detector = OSFDetector()
    for _ in range(10000):
        detector.update(90, 1000, 0.125)
    assert detector.s_idx == 60
    assert len(detector._intervals) == 1
    detector.update(18, 1000, 0)
    detector.update(18, 1000, 60)
    assert detector.s_idx == 0
    assert not detector._intervals


def test_separate_exposure_intervals_expire_without_counting_gaps():
    detector = OSFDetector()
    previous = 0
    for seconds, load, expected in [(0, 90, 0), (10, 18, 10), (20, 90, 10),
                                    (40, 18, 30), (65, 18, 25), (75, 18, 20),
                                    (85, 18, 15), (100, 18, 0)]:
        detector.update(load, 1000, seconds - previous)
        assert detector.s_idx == pytest.approx(expected)
        previous = seconds
    assert not detector._intervals
