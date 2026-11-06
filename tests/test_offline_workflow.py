"""Production CLI replay-to-export regression using the public synthetic fixture."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

import pytest

from autopulse.debug import main
from autopulse.offline_workflow import analyze_ice_jsonl


EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "synthetic-ice.jsonl"


def semantic(report):
    result = deepcopy(report)
    for vehicle in result["vehicles"]:
        for observation in vehicle["observations"]:
            assert UUID(observation.pop("@id").removeprefix("urn:uuid:")).version == 4
    return result


def test_public_example_full_cli_workflow(capsys):
    assert main(["analyze-ice", "--jsonl", str(EXAMPLE)]) == 0
    output = capsys.readouterr().out
    actual = json.loads(output)
    assert actual["ok"] is True
    assert actual["powertrain_type"] == "ICE"
    assert (actual["total_rows"], actual["accepted_frames"], actual["rejected_frames"]) == (8, 5, 3)
    assert actual["rejections"] == [
        {"row_index": 5, "stage": "input"},
        {"row_index": 6, "stage": "analysis"},
        {"row_index": 7, "stage": "analysis"},
    ]
    assert [v["vin_hashed"] for v in actual["vehicles"]] == ["a" * 64, "b" * 64]
    for vehicle, labels, seconds in zip(actual["vehicles"],
                                       [["NONE", "NONE"], ["NONE", "HDF", "HDF"]],
                                       [[0, 1], [0, 1, 3]], strict=True):
        observations = vehicle["observations"]
        assert [o["failure_type"] for o in observations] == labels
        assert [o["timestamp"] for o in observations] == [1779789600000 + s * 1000 for s in seconds]
        for observation, label in zip(observations, labels, strict=True):
            assert observation["vin_hashed"] == vehicle["vin_hashed"]
            assert observation["@type"] == "sosa:Observation"
            assert observation["is_anomaly"] is (label == "HDF")
            assert observation["failure_probability"] == pytest.approx(1.0 if label == "HDF" else 0.0)
            assert observation["primary_pid"] is None
            assert set(observation) == {"@id", "@type", "@context", "timestamp", "vin_hashed",
                                        "failure_type", "failure_probability", "is_anomaly",
                                        "primary_pid", "window_summary"}
            for name, value in [("engine_rpm", 900.0), ("coolant_temp", 88.0), ("engine_load", 5.0)]:
                assert observation["window_summary"][name] == {
                    "min": value, "max": value, "avg": value, "std_dev": 0.0,
                    "z_score": 0.0, "iqr_low": value, "iqr_high": value,
                    "is_statistical_outlier": False,
                }
    assert json.dumps(actual, allow_nan=False)
    assert semantic(actual) == semantic(analyze_ice_jsonl(EXAMPLE.read_text().splitlines()))


def test_rejections_and_interleaving_do_not_change_vehicle_state():
    lines = EXAMPLE.read_text().splitlines()
    combined = analyze_ice_jsonl(lines)
    for identity in ("a" * 64, "b" * 64):
        clean = [line for index, line in enumerate(lines, 1)
                 if index not in {5, 6, 7} and json.loads(line)["vin_hashed"] == identity]
        isolated = analyze_ice_jsonl(clean)
        expected = semantic(isolated)["vehicles"][0]
        actual = next(v for v in semantic(combined)["vehicles"] if v["vin_hashed"] == identity)
        assert actual == expected


@pytest.mark.parametrize("change", [
    {"protocol": "J1979_MODE01"}, {"protocol": "SAE_J1979-3"},
    {"powertrain_type": "EV"}, {"payload": {}}, {"__service_id__": "0x2E"},
    {"payload_bytes": "private-marker"}, {"vin_hashed": "1HGCM82633A004352"},
    {"vin_hashed": "c" * 64 + "\n"}, {"timestamp": None}, {"timestamp": "bad"},
    {"engine_rpm": True}, {"engine_rpm": "900"}, {"engine_rpm": float("nan")},
    {"ambient_temp": float("inf")}, {"engine_rpm": None}, {"vehicle_speed": 1.5},
])
def test_raw_rejections_cannot_seed_or_change_analysis(change, caplog):
    lines = EXAMPLE.read_text().splitlines()
    invalid = json.loads(lines[0]) | change
    report = analyze_ice_jsonl([json.dumps(invalid), *lines[:4]])
    assert report["total_rows"] == 5
    assert report["accepted_frames"] == 4
    assert report["rejected_frames"] == 1
    assert report["rejections"] == [{"row_index": 1, "stage": "input"}]
    assert semantic(report)["vehicles"] == semantic(analyze_ice_jsonl(lines[:4]))["vehicles"]
    output = json.dumps(report, allow_nan=False) + caplog.text
    for forbidden in ("private-marker", "1HGCM82633A004352", "payload_bytes", "obd_frame", "NaN", "Infinity"):
        assert forbidden not in output


def test_malformed_nonobjects_missing_fields_and_blank_lines():
    report = analyze_ice_jsonl(["\n", "not-json", "null", "[]", "1", "true", "{}"])
    assert report["total_rows"] == report["rejected_frames"] == 6
    assert report["accepted_frames"] == 0
    assert report["vehicles"] == []
    assert report["rejections"] == [{"row_index": i, "stage": "input"} for i in range(2, 8)]
    assert analyze_ice_jsonl([])["total_rows"] == 0


@pytest.mark.parametrize("depth", [1100, 10000])
def test_excessive_nesting_rejects_one_row_and_continues(tmp_path, capsys, depth):
    path = tmp_path / "nested.jsonl"
    valid = EXAMPLE.read_text().splitlines()[0]
    path.write_text("[" * depth + "]" * depth + "\n" + valid, encoding="utf-8")
    assert main(["analyze-ice", "--jsonl", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["total_rows"], report["accepted_frames"], report["rejected_frames"]) == (2, 1, 1)
    assert report["rejections"] == [{"row_index": 1, "stage": "input"}]
    assert len(report["vehicles"][0]["observations"]) == 1


@pytest.mark.parametrize("kind", ["missing", "encoding"])
def test_file_failure_returns_safe_nonzero_result(tmp_path, capsys, kind):
    path = tmp_path / "private-marker.jsonl"
    if kind == "encoding":
        path.write_bytes(b"\xff")
    assert main(["analyze-ice", "--jsonl", str(path)]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"ok": False, "error": "offline_analysis_failed"}
    assert "private-marker" not in captured.out + captured.err
