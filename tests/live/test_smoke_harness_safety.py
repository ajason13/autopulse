"""Live smoke harness safety tests."""

from __future__ import annotations

import logging

from autopulse.live.harness import (
    ADAPTER_FAILURE_EXIT,
    SAFETY_ABORT_EXIT,
    SmokeHarnessConfig,
    run_smoke_capture,
)

from tests.live.fakes import FakeICEAdapter, RAW_VIN, frame_values


def config(tmp_path, vin_hashed, **overrides):
    values = {
        "adapter_port": "/dev/tty.fake",
        "vin_hashed": vin_hashed,
        "output_path": tmp_path / "capture.jsonl",
        "max_samples": 1,
        "confirmed_stationary": True,
    }
    values.update(overrides)
    return SmokeHarnessConfig(**values)


def test_motion_during_stationary_capture_aborts_and_disconnects(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values(vehicle_speed=1)])

    summary = run_smoke_capture(
        config(tmp_path, fake_vin_hashed),
        adapter,
        sleep=lambda _: None,
    )

    assert summary.exit_code == SAFETY_ABORT_EXIT
    assert summary.safety_abort is True
    assert adapter.disconnected is True
    assert (tmp_path / "capture.jsonl").read_text(encoding="utf-8") == ""


def test_adapter_open_failure_logs_sanitized_error_type(tmp_path, fake_vin_hashed, caplog):
    adapter = FakeICEAdapter(
        [frame_values()],
        connect_error=ConnectionError(f"failed for {RAW_VIN}"),
    )
    logger = logging.getLogger("tests.live.safety")

    with caplog.at_level(logging.ERROR, logger="tests.live.safety"):
        summary = run_smoke_capture(
            config(tmp_path, fake_vin_hashed),
            adapter,
            logger=logger,
            sleep=lambda _: None,
        )

    assert summary.exit_code == ADAPTER_FAILURE_EXIT
    assert "ConnectionError" in caplog.text
    assert RAW_VIN not in caplog.text


def test_unsupported_protocol_fails_closed(tmp_path, fake_vin_hashed):
    adapter = FakeICEAdapter([frame_values()], protocol="ISO_15765_4_DoCAN")

    summary = run_smoke_capture(
        config(tmp_path, fake_vin_hashed),
        adapter,
        sleep=lambda _: None,
    )

    assert summary.exit_code == ADAPTER_FAILURE_EXIT
    assert summary.adapter_failure is True
    assert adapter.disconnected is True
    assert adapter.queries == []


def test_adapter_fetch_exception_does_not_log_raw_message(tmp_path, fake_vin_hashed, caplog):
    adapter = FakeICEAdapter(
        [frame_values()],
        fetch_error=RuntimeError(f"raw payload 2E F4 B2 for {RAW_VIN}"),
    )
    logger = logging.getLogger("tests.live.fetch")

    with caplog.at_level(logging.ERROR, logger="tests.live.fetch"):
        summary = run_smoke_capture(
            config(tmp_path, fake_vin_hashed),
            adapter,
            logger=logger,
            sleep=lambda _: None,
        )

    assert summary.exit_code == ADAPTER_FAILURE_EXIT
    assert "RuntimeError" in caplog.text
    assert RAW_VIN not in caplog.text
    assert "2E F4 B2" not in caplog.text
