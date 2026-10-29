"""Observe #118 ICE counterexamples with production classes and synthetic data.

Run from the repository root:
    PYTHONPATH=src .venv/bin/python scripts/probe_ice_scoring.py

This is a diagnostic reproducer, not a test requiring the old defects to remain.
It reads no vehicle data, opens no connection, and writes only a JSON summary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from autopulse.analysis.hdf_detector import HDFDetector
from autopulse.analysis.osf_detector import OSFDetector
from autopulse.analysis.pdm_processor import PdMProcessor
from autopulse.data.validator import validate_frame


_SYNTHETIC_HASH = "a" * 64
_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def frame(second: int, **overrides: float) -> dict:
    result = {
        "timestamp": (_START + timedelta(seconds=second)).isoformat(),
        "vin_hashed": _SYNTHETIC_HASH,
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
    validate_frame(result)
    return result


def observe(frames: list[dict]) -> dict:
    processor = PdMProcessor(_SYNTHETIC_HASH)
    first = None
    for item in frames:
        alert = processor.process_frame(item)
        if first is None:
            first = {
                "failure_type": alert.failure_type,
                "score_field": alert.failure_probability,
                "s_idx": processor.osf_detector.s_idx,
                "hdf_score": processor.hdf_detector.score,
                "hdf_armed": processor.hdf_detector.armed,
            }
    return {
        "frames": len(frames),
        "first": first,
        "last": {
            "failure_type": alert.failure_type,
            "score_field": alert.failure_probability,
            "s_idx": processor.osf_detector.s_idx,
            "hdf_score": processor.hdf_detector.score,
            "hdf_armed": processor.hdf_detector.armed,
        },
    }


def main() -> None:
    osf = OSFDetector("L")
    osf.update(18.0, 850.0, 0.0)
    osf.update(18.0, 850.0, 1.0)
    direct_osf = {
        "recent_exposure_seconds": osf.s_idx,
        "classification": osf.classify(),
        "score_field": osf.compute_probability(),
    }
    osf.reset()
    direct_osf["s_idx_after_reset"] = osf.s_idx
    print(json.dumps({
        "direct_osf_idle": direct_osf,
        "legacy_pure_hdf_equation_at_zero": HDFDetector.compute_probability(0.0, 0.0),
        "gated_hdf_engine_off": HDFDetector().update(
            raw_rpm=0, raw_delta_t=0, smoothed_delta_t=0, smoothed_rpm=0),
        "idle_600_seconds": observe([frame(i) for i in range(601)]),
        "engine_off": observe([frame(i, engine_rpm=0.0, engine_load=0.0,
                                     coolant_temp=22.0) for i in range(2)]),
        "cold_start": observe([frame(i, coolant_temp=22.0 + i) for i in range(15)]),
    }, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
