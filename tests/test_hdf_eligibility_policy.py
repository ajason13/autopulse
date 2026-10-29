"""Production-backed #121 policy H1–H6/R1 synthetic acceptance vectors."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from autopulse.analysis.hdf_detector import HDFDetector
from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.data.validator import validate_frame


_BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def frame(seconds=0, *, ambient=22, **overrides):
    item = {
        "timestamp": (_BASE + timedelta(seconds=seconds)).isoformat(),
        "vin_hashed": "a" * 64, "protocol": "SAE_J1979",
        "engine_rpm": 850, "engine_load": 18, "coolant_temp": 88,
        "vehicle_speed": 0, "stft_bank1": 0, "ltft_bank1": 0,
    }
    if ambient is not None:
        item["ambient_temp"] = ambient
    item.update(overrides)
    validate_frame(item)
    return item


def snapshot(processor):
    return deepcopy({key: vars(value) if hasattr(value, "__dict__") else value
                     for key, value in vars(processor).items()})


@pytest.mark.parametrize("rpm", [0, 850])
def test_h1_engine_off_and_cold_stream_stay_disarmed(rpm):
    processor = PdMProcessor("a" * 64)
    for second in range(15):
        alert = processor.process_frame(frame(second, engine_rpm=rpm,
            engine_load=18 if rpm else 0, coolant_temp=22 + second if rpm else 22))
        assert processor.hdf_detector.score == 0
        assert not processor.hdf_detector.armed
        assert alert.failure_type != "HDF"


@pytest.mark.parametrize("raw,smoothed,armed", [
    (14.999, 20, False), (20, 14.999, False), (15, 15, True),
])
def test_h2_direct_arming_requires_both_deltas_and_defers_scoring(raw, smoothed, armed):
    detector = HDFDetector()
    assert detector.update(raw_rpm=850, raw_delta_t=raw,
        smoothed_delta_t=smoothed, smoothed_rpm=850) == 0
    assert detector.armed == armed
    score = detector.update(raw_rpm=850, raw_delta_t=5,
        smoothed_delta_t=5, smoothed_rpm=850)
    assert score == (1 if armed else 0)


def test_h2_normal_warmup_and_already_warm_first_frame():
    processor = PdMProcessor("a" * 64)
    saw_arming = False
    for second in range(187):
        coolant = min(22 + second, 88)
        was_armed = processor.hdf_detector.armed
        alert = processor.process_frame(frame(second, coolant_temp=coolant))
        smoothed = processor._coolant_median_buffer.get_ewma(0.1)
        if not was_armed:
            assert processor.hdf_detector.score == 0
            assert processor.hdf_detector.armed == (coolant - 22 >= 15 and smoothed - 22 >= 15)
        if processor.hdf_detector.armed and not was_armed:
            saw_arming = True
            assert coolant - 22 >= 15
            assert smoothed - 22 >= 15
        assert processor.hdf_detector.score < 0.5
        assert alert.failure_type != "HDF"
    assert saw_arming
    warm = PdMProcessor("a" * 64)
    assert warm.process_frame(frame()).failure_probability == 0
    assert warm.hdf_detector.armed
    warm.process_frame(frame(1))
    assert 0 < warm.hdf_detector.score < 0.5


def test_h3_armed_synthetic_cooling_fault_survives_smoothing():
    processor = PdMProcessor("a" * 64)
    coolants = [88] * 120 + list(range(87, 26, -1)) + [27] * 120
    for second, coolant in enumerate(coolants):
        alert = processor.process_frame(frame(second, coolant_temp=coolant))
        assert alert.failure_type != "SENSOR_ERROR"
        assert processor.hdf_detector.armed
        assert processor.osf_detector.s_idx == 0
    assert processor._coolant_median_buffer.get_ewma(0.1) - 22 < 8.6
    assert processor.hdf_detector.score == 1
    assert alert.failure_type == "HDF"
    assert alert.failure_probability == 1


@pytest.mark.parametrize("delta,rpm,critical", [(8.5, 1379, True),
    (8.6, 1379, False), (8.5, 1380, False), (12, 1100, False)])
def test_h4_eligible_boundaries_through_processor(delta, rpm, critical):
    # Capacity one makes the production smoothing exact for these boundaries.
    processor = PdMProcessor("a" * 64, window_size=1)
    processor.process_frame(frame(engine_rpm=rpm))
    alert = processor.process_frame(frame(60, engine_rpm=rpm, coolant_temp=22 + delta))
    score = processor.hdf_detector.score
    assert score == pytest.approx(HDFDetector.compute_probability(delta, rpm))
    assert (score == 1) == critical
    if delta == 12:
        assert 0.5 < score < 1
    assert alert.failure_type == ("HDF" if score > 0.5 else "NONE")


def test_h5_absent_ambient_disarms_without_stopping_other_branches():
    processor = PdMProcessor("a" * 64)
    processor.process_frame(frame(engine_rpm=1000, engine_load=90))
    assert processor.hdf_detector.armed
    for second in range(1, 15):
        alert = processor.process_frame(frame(second, ambient=None, engine_rpm=1000,
            engine_load=90, coolant_temp=max(22, 88 - 5 * second)))
        assert alert.failure_type != "SENSOR_ERROR"
        assert processor.hdf_detector.score == 0
        assert not processor.hdf_detector.armed
    assert processor.osf_detector.s_idx == 14
    assert len(processor.coolant_buffer) == 15
    assert processor._coolant_median_buffer.get_ewma(0.1) - 22 > 15
    processor.process_frame(frame(15, coolant_temp=22, engine_rpm=1000, engine_load=90))
    assert not processor.hdf_detector.armed  # raw delta prevents stale-smoothing arming
    assert processor.hdf_detector.score == 0
    assert processor.osf_detector.s_idx == 15
    assert processor.last_coolant_temp == 22


def test_h5_engine_off_disarms_despite_lag_and_restart_must_rearm():
    processor = PdMProcessor("a" * 64)
    for second in range(3):
        processor.process_frame(frame(second, coolant_temp=40))
    assert processor.hdf_detector.armed
    alert = processor.process_frame(frame(3, coolant_temp=40, engine_rpm=0))
    assert processor._rpm_median_buffer.get_ewma(0.3) > 0
    assert processor.hdf_detector.score == 0
    assert not processor.hdf_detector.armed
    assert alert.failure_type == "STATISTICAL_ANOMALY"
    for second, coolant in [(4, 35), (5, 30), (6, 25), (7, 22)]:
        processor.process_frame(frame(second, coolant_temp=coolant))
        assert not processor.hdf_detector.armed
        assert processor.hdf_detector.score == 0
    # A warm restart can arm, but cannot score on the arming frame.
    for second in range(27, 50):
        was_armed = processor.hdf_detector.armed
        alert = processor.process_frame(frame(second, coolant_temp=88))
        assert alert.failure_type != "SENSOR_ERROR"
        if not was_armed:
            assert processor.hdf_detector.score == 0
    assert processor.hdf_detector.armed


@pytest.mark.parametrize("gap,armed,scored", [(60, True, True), (60.001, False, False)])
def test_h5_gap_reset_and_first_frame_rearming(gap, armed, scored):
    processor = PdMProcessor("a" * 64, window_size=1)
    processor.process_frame(frame())
    processor.process_frame(frame(1))
    processor.process_frame(frame(1 + gap, coolant_temp=27))
    assert processor.hdf_detector.armed == armed
    assert processor.hdf_detector.score == (1 if scored else 0)
    if not armed:
        processor.process_frame(frame(2 + gap, coolant_temp=27))
        assert not processor.hdf_detector.armed
        assert processor.hdf_detector.score == 0


@pytest.mark.parametrize("armed", [False, True])
@pytest.mark.parametrize("invalid", ["rate", "missing", "numeric", "timestamp", "smoothing"])
def test_h6_rejected_frames_cannot_arm_or_disarm_or_mutate_state(monkeypatch, armed, invalid):
    processor = PdMProcessor("a" * 64)
    coolant = 40 if armed else 22
    processor.process_frame(frame(coolant_temp=coolant, engine_load=90))
    processor.process_frame(frame(1, coolant_temp=coolant, engine_load=90))
    assert processor.hdf_detector.armed == armed
    assert processor.osf_detector.s_idx == 1
    item = frame(2, ambient=None if armed else 0, coolant_temp=coolant, engine_rpm=0 if armed else 850)
    if invalid == "rate":
        item["coolant_temp"] = coolant + 6
    elif invalid == "missing":
        del item["engine_load"]
    elif invalid == "numeric":
        item["engine_load"] = float("nan")
    elif invalid == "timestamp":
        item["timestamp"] = frame(1)["timestamp"]
    else:
        def reject():
            raise ValueError("synthetic rejection")
        monkeypatch.setattr(processor, "_smooth_current_values", reject)
    before = snapshot(processor)
    if invalid == "timestamp":
        with pytest.raises(ValueError):
            processor.process_frame(item)
    else:
        assert processor.process_frame(item).failure_type == "SENSOR_ERROR"
    assert snapshot(processor) == before
    monkeypatch.undo()
    # Exactly five degrees per second remains accepted in either eligibility state.
    assert processor.process_frame(frame(2, coolant_temp=coolant + 5)).failure_type != "SENSOR_ERROR"


def test_r1_reset_after_positive_score_and_exposure_matches_fresh_replay():
    items = [frame(t, coolant_temp=coolant, engine_load=90)
             for t, coolant in [(0, 88), (60, 27), (61, 27)]]
    def replay(processor):
        return [(processor.process_frame(item), snapshot(processor)) for item in items]
    processor = PdMProcessor("a" * 64, window_size=1)
    expected = replay(processor)
    assert processor.hdf_detector.armed
    assert processor.hdf_detector.score == 1
    assert processor.osf_detector.s_idx == 60
    processor.reset()
    assert not processor.hdf_detector.armed
    assert processor.hdf_detector.score == 0
    assert replay(processor) == replay(PdMProcessor("a" * 64, window_size=1)) == expected


def test_direct_raw_off_gate_and_reset_clear_latch_and_score():
    detector = HDFDetector()
    detector.update(raw_rpm=850, raw_delta_t=66, smoothed_delta_t=66, smoothed_rpm=850)
    assert detector.update(raw_rpm=850, raw_delta_t=5, smoothed_delta_t=5, smoothed_rpm=850) == 1
    assert detector.update(raw_rpm=0, raw_delta_t=0, smoothed_delta_t=66, smoothed_rpm=850) == 0
    assert not detector.armed
    detector.update(raw_rpm=850, raw_delta_t=66, smoothed_delta_t=66, smoothed_rpm=850)
    detector.reset()
    assert not detector.armed
    assert detector.score == 0
