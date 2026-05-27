"""Debug CLI replay, alert preview, and guard inspection tests."""

from __future__ import annotations

import json
import logging
import math
import re

import pytest

from autopulse.debug import main as debug_main
from tests.simulation.virtual_replay import NoiseGenerator


RAW_VIN = "1HGCM82633A004352"


def write_jsonl(tmp_path, rows, filename="rows.jsonl"):
    path = tmp_path / filename
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def ev_row(**overrides):
    row = {
        "timestamp": "2026-05-26T10:00:00.000Z",
        "vin_hashed": "e" * 64,
        "protocol": "SAE_J1979-3",
        "battery_soh": 95.0,
        "battery_soce": 80.0,
        "battery_temp_avg": 35.0,
    }
    row.update(overrides)
    return row


def ice_row(**overrides):
    row = {
        "timestamp": "2026-05-26T10:00:00.000Z",
        "vin_hashed": "c" * 64,
        "protocol": "J1979_MODE01",
        "engine_rpm": 1200.0,
        "vehicle_speed": 30,
        "coolant_temp": 88.0,
        "engine_load": 22.0,
        "stft_bank1": 0.5,
        "ltft_bank1": -0.5,
    }
    row.update(overrides)
    return row


def parsed_stdout(capsys: pytest.CaptureFixture[str]):
    captured = capsys.readouterr()
    return json.loads(captured.out), captured


def assert_no_raw_vin(stdout: str) -> None:
    assert RAW_VIN not in stdout
    assert not re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", stdout)


def test_replay_ev_robust_loop_tallies_schema_rejections_without_crash(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(),
            ev_row(battery_temp_avg=999),
            ev_row(),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["ok"] is True
    assert summary["powertrain_type"] == "EV"
    assert summary["total_rows"] == 3
    assert summary["accepted_frames"] == 2
    assert summary["rejected_frames"] == 1
    assert summary["security_violations"] == 0
    assert summary["guard_events"] == []
    assert_no_raw_vin(captured.out)


def test_replay_ev_all_invalid_rows_still_returns_success_summary(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(battery_soce=math.nan),
            ev_row(battery_temp_avg=999),
            ev_row(battery_soh=None),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["ok"] is True
    assert summary["accepted_frames"] == 0
    assert summary["rejected_frames"] == 3
    assert summary["security_violations"] == 0


def test_replay_ev_malformed_jsonl_is_pre_loop_error(tmp_path, capsys):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(ev_row()) + "\nnot-json\n", encoding="utf-8")

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    payload, captured = parsed_stdout(capsys)
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error_type"] == "ValueError"
    assert "not-json" not in captured.out


def test_replay_ev_security_events_distinguish_red_line_and_rate_limit(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ev_row(__service_id__="0x2E"),
            ev_row(__service_id__="0x3E", __now__=10.0),
            ev_row(__service_id__="0x3E", __now__=12.0),
            ev_row(),
        ],
    )

    exit_code = debug_main(["replay-ev", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["accepted_frames"] == 2
    assert summary["security_violations"] == 1  # rate-limit must not count as red-line
    assert "SECURITY_VIOLATION_RED_LINE" in summary["guard_events"]
    assert "TESTER_PRESENT_RATE_LIMIT" in summary["guard_events"]
    assert_no_raw_vin(captured.out)


def test_replay_ice_robust_loop_tallies_out_of_bounds_rpm(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ice_row(),
            ice_row(engine_rpm=9501),
            ice_row(),
        ],
    )

    exit_code = debug_main(["replay-ice", "--jsonl", str(path)])

    summary, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["powertrain_type"] == "ICE"
    assert summary["accepted_frames"] == 2
    assert summary["rejected_frames"] == 1


def test_replay_ice_security_violation_uses_safe_guard_event(tmp_path, capsys):
    path = write_jsonl(
        tmp_path,
        [
            ice_row(),
            NoiseGenerator.inject_restricted_service(ice_row(), "0x2E"),
        ],
    )

    exit_code = debug_main(["replay-ice", "--jsonl", str(path)])

    summary, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert summary["accepted_frames"] == 1
    assert summary["security_violations"] == 1
    assert summary["guard_events"] == ["0x2E"]
    assert_no_raw_vin(captured.out)


def test_preview_alerts_outputs_hdf_alerts_partitioned_by_vin(tmp_path, capsys):
    healthy_vin = "a" * 64
    fault_vin = "b" * 64
    rows = [
        ice_row(vin_hashed=healthy_vin, engine_load=5.0),
        ice_row(
            vin_hashed=fault_vin,
            engine_rpm=900.0,
            engine_load=5.0,
            coolant_temp=30.0,
            ambient_temp=25.0,
        ),
    ]
    path = write_jsonl(tmp_path, rows)

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert len(alerts) == 1
    assert alerts[0]["vin_hashed"] == fault_vin
    assert alerts[0]["failure_type"] == "HDF"
    assert alerts[0]["failure_probability"] > 0.0
    assert_no_raw_vin(captured.out)


def test_preview_alerts_schema_invalid_frame_does_not_stop_vin_session(tmp_path, capsys):
    vin = "d" * 64
    rows = [
        ice_row(
            vin_hashed=vin,
            timestamp="2026-05-26T10:00:00.000Z",
            engine_rpm=1200.0,
            engine_load=5.0,
        ),
        ice_row(vin_hashed=vin, engine_rpm=99999.0),
        ice_row(
            vin_hashed=vin,
            timestamp="2026-05-26T10:01:00.000Z",
            engine_rpm=900.0,
            engine_load=5.0,
            coolant_temp=30.0,
            ambient_temp=25.0,
        ),
    ]
    path = write_jsonl(tmp_path, rows)

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert alerts[-1]["vin_hashed"] == vin
    assert alerts[-1]["failure_probability"] > 0.0


def test_preview_alerts_raw_vin_in_vin_hashed_is_rejected_cleanly(tmp_path, capsys):
    path = write_jsonl(tmp_path, [ice_row(vin_hashed=RAW_VIN)])

    exit_code = debug_main(["preview-alerts", "--jsonl", str(path)])

    alerts, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert alerts == []
    assert RAW_VIN not in captured.out


def test_inspect_guards_output_contains_expected_safe_constants(capsys):
    exit_code = debug_main(["inspect-guards"])

    payload, _captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert set(payload) == {
        "ice_bounds",
        "ev_bounds",
        "restricted_service_ids",
        "ice_protocols",
        "ev_protocols",
    }
    assert payload["restricted_service_ids"] == [
        "0x04",
        "0x08",
        "0x10",
        "0x14",
        "0x27",
        "0x2E",
        "0x2F",
        "0x31",
    ]


def test_inspect_guards_output_is_rfc8259_safe(capsys):
    exit_code = debug_main(["inspect-guards"])

    payload, captured = parsed_stdout(capsys)
    assert exit_code == 0
    assert payload["restricted_service_ids"]
    assert "NaN" not in captured.out
    assert "Infinity" not in captured.out


def test_replay_ev_verbose_logging_omits_rejected_field_values(tmp_path, caplog):
    path = write_jsonl(tmp_path, [ev_row(battery_temp_avg=999)])

    with caplog.at_level(logging.WARNING, logger="autopulse"):
        exit_code = debug_main(["--verbose", "replay-ev", "--jsonl", str(path)])

    assert exit_code == 0
    assert "ValidationError" in caplog.text
    assert "999" not in caplog.text
    assert RAW_VIN not in caplog.text
