"""Live smoke harness capture tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from autopulse.live.harness import OK_EXIT, SmokeHarnessConfig, run_smoke_capture

from tests.live.fakes import FakeICEAdapter, frame_values


def config(tmp_path: Path, vin_hashed: str, **overrides) -> SmokeHarnessConfig:
    values = {
        "adapter_port": "/dev/tty.fake",
        "vin_hashed": vin_hashed,
        "output_path": tmp_path / "capture.jsonl",
        "max_samples": 1,
        "confirmed_stationary": True,
    }
    values.update(overrides)
    return SmokeHarnessConfig(**values)


def test_smoke_capture_writes_valid_replay_jsonl(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values()])

    summary = run_smoke_capture(
        config(tmp_path, fake_vin_hashed),
        adapter,
        sleep=lambda _: None,
    )

    assert summary.exit_code == OK_EXIT
    assert summary.accepted_frames == 1
    rows = (tmp_path / "capture.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    frame = json.loads(rows[0])
    assert frame["vin_hashed"] == fake_vin_hashed
    assert frame["protocol"] == "SAE_J1979"
    assert set(frame) == {
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


def test_smoke_capture_respects_max_samples(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values(), frame_values(engine_rpm=1300.0)])

    summary = run_smoke_capture(
        config(tmp_path, fake_vin_hashed, max_samples=2),
        adapter,
        sleep=lambda _: None,
    )

    assert summary.exit_code == OK_EXIT
    assert summary.total_samples == 2
    assert summary.accepted_frames == 2
    assert len((tmp_path / "capture.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_smoke_capture_rejects_partial_or_invalid_frame_without_writing(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values(engine_rpm=9501.0)])

    summary = run_smoke_capture(
        config(tmp_path, fake_vin_hashed),
        adapter,
        sleep=lambda _: None,
    )

    assert summary.exit_code == OK_EXIT
    assert summary.accepted_frames == 0
    assert summary.rejected_frames == 1
    assert (tmp_path / "capture.jsonl").read_text(encoding="utf-8") == ""


def test_smoke_capture_enforces_one_second_cadence(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values()])
    monotonic_values = iter([0.0, 0.1, 0.2])
    sleeps = []

    run_smoke_capture(
        config(tmp_path, fake_vin_hashed),
        adapter,
        monotonic=lambda: next(monotonic_values),
        sleep=sleeps.append,
    )

    assert sleeps == [0.9]


def test_smoke_capture_logs_only_error_type_for_validation_rejection(
    tmp_path,
    fake_vin_hashed,
    caplog,
):
    adapter = FakeICEAdapter([frame_values(engine_rpm=99999.0)])
    logger = logging.getLogger("tests.live.capture")

    with caplog.at_level(logging.WARNING, logger="tests.live.capture"):
        run_smoke_capture(
            config(tmp_path, fake_vin_hashed),
            adapter,
            logger=logger,
            sleep=lambda _: None,
        )

    assert "ValidationError" in caplog.text
    assert "99999" not in caplog.text
