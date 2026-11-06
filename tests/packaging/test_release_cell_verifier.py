from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import zipfile
from copy import deepcopy
import json
import subprocess

import pytest

from scripts.verify_release_cell import (
    _pip_install_command,
    _require_failed_install,
    _check_analysis_report,
    _verify_offline_analysis,
)


def _offline_environment() -> dict[str, str]:
    """Keep the host process usable while prohibiting pip network access."""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def test_offline_environment_preserves_platform_process_settings(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AUTOPULSE_RELEASE_CELL_TEST_MARKER", "preserved")
    monkeypatch.setenv("PYTHONPATH", "must-not-leak")
    monkeypatch.setenv("PYTHONHOME", "must-not-leak")

    environment = _offline_environment()

    assert environment["AUTOPULSE_RELEASE_CELL_TEST_MARKER"] == "preserved"
    assert "PATH" in environment
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert environment["PIP_NO_INDEX"] == "1"
    assert environment["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"


def _write_minimal_wheel(wheelhouse: Path) -> Path:
    wheel = wheelhouse / "demo_pkg-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("demo_pkg/__init__.py", "")
        archive.writestr(
            "demo_pkg-1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 1.0\n",
        )
        archive.writestr(
            "demo_pkg-1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr("demo_pkg-1.0.dist-info/RECORD", "")
    return wheel


def test_real_offline_pip_flow_rejects_tampered_hash(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    _write_minimal_wheel(wheelhouse)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"demo-pkg==1.0 --hash=sha256:{'0' * 64}\n",
        encoding="utf-8",
    )

    _require_failed_install(
        environment_path=tmp_path / "venv",
        wheelhouse=wheelhouse,
        requirements=requirements,
        work=tmp_path,
        environment=_offline_environment(),
        expected_error="hash",
    )


def test_real_offline_pip_flow_rejects_incomplete_wheelhouse(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    omitted = tmp_path / "omitted"
    omitted.mkdir()
    wheel = _write_minimal_wheel(omitted)
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        f"demo-pkg==1.0 --hash=sha256:{hashlib.sha256(wheel.read_bytes()).hexdigest()}\n",
        encoding="utf-8",
    )

    _require_failed_install(
        environment_path=tmp_path / "venv",
        wheelhouse=wheelhouse,
        requirements=requirements,
        work=tmp_path,
        environment=_offline_environment(),
        expected_error="no matching distribution",
    )


def test_pip_install_command_contains_every_fail_closed_flag(tmp_path: Path) -> None:
    command = _pip_install_command(
        tmp_path / "python",
        tmp_path / "wheelhouse",
        tmp_path / "requirements.txt",
    )
    assert "--no-index" in command
    assert "--require-hashes" in command
    assert "--only-binary=:all:" in command


@pytest.fixture
def analysis_report(capsys):
    from autopulse.debug import main

    fixture = Path(__file__).resolve().parents[2] / "examples" / "synthetic-ice.jsonl"
    assert main(["analyze-ice", "--jsonl", str(fixture)]) == 0
    return json.loads(capsys.readouterr().out)


def test_analysis_check_accepts_public_example_and_tiny_healthy_score(analysis_report):
    _check_analysis_report(json.dumps(analysis_report))
    analysis_report["vehicles"][0]["observations"][0]["failure_probability"] = 1e-16
    _check_analysis_report(json.dumps(analysis_report))


@pytest.mark.parametrize("defect", [
    "accounting", "rejection", "partition", "missing_vehicle", "missing_observation",
    "label", "score", "anomaly", "timestamp", "identity", "type", "uuid", "context",
    "raw_frame", "context_payload", "summary_payload", "summary_value", "nan", "infinity", "missing_field",
])
def test_analysis_check_rejects_broken_or_unsanitized_results(analysis_report, defect):
    report = deepcopy(analysis_report)
    observation = report["vehicles"][1]["observations"][1]
    if defect == "accounting":
        report["accepted_frames"] = 8
    elif defect == "rejection":
        report["rejections"][1]["stage"] = "input"
    elif defect == "partition":
        report["vehicles"].reverse()
    elif defect == "missing_vehicle":
        report["vehicles"].pop()
    elif defect == "missing_observation":
        report["vehicles"][1]["observations"].pop()
    elif defect == "raw_frame":
        observation["obd_frame"] = {"payload_bytes": "must-not-export"}
    elif defect == "context_payload":
        observation["@context"]["payload_bytes"] = "must-not-export"
    elif defect == "summary_payload":
        observation["window_summary"]["payload_bytes"] = "must-not-export"
    elif defect == "summary_value":
        observation["window_summary"]["engine_rpm"]["avg"] = 901
    elif defect == "missing_field":
        observation.pop("primary_pid")
    else:
        key, value = {
            "label": ("failure_type", "NONE"), "score": ("failure_probability", 0.1),
            "anomaly": ("is_anomaly", False), "timestamp": ("timestamp", 1779789603000),
            "identity": ("vin_hashed", "a" * 64), "type": ("@type", "other"),
            "uuid": ("@id", "not-a-uuid"), "context": ("@context", {}),
            "nan": ("failure_probability", float("nan")),
            "infinity": ("failure_probability", float("inf")),
        }[defect]
        observation[key] = value
    with pytest.raises(ValueError):
        _check_analysis_report(json.dumps(report))


def test_analysis_runner_supplies_only_fixture_and_checks_cli_result(
    tmp_path, monkeypatch, analysis_report,
):
    def run(command, **kwargs):
        assert command == ["installed-cli", "analyze-ice", "--jsonl", str(tmp_path / "synthetic-ice.jsonl")]
        assert kwargs == dict(cwd=tmp_path, env={"PIP_NO_INDEX": "1"}, check=True,
                              capture_output=True, text=True)
        assert [p.name for p in tmp_path.iterdir()] == ["synthetic-ice.jsonl"]
        assert len((tmp_path / "synthetic-ice.jsonl").read_text().splitlines()) == 8
        return subprocess.CompletedProcess(command, 0, json.dumps(analysis_report), "")

    monkeypatch.setattr("scripts.verify_release_cell.subprocess.run", run)
    _verify_offline_analysis(Path("installed-cli"), work=tmp_path, environment={"PIP_NO_INDEX": "1"})
    analysis_report["vehicles"] = []
    with pytest.raises(ValueError):
        _verify_offline_analysis(Path("installed-cli"), work=tmp_path, environment={"PIP_NO_INDEX": "1"})


def test_analysis_runner_propagates_missing_functionality(tmp_path, monkeypatch):
    def run(command, **kwargs):
        raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr("scripts.verify_release_cell.subprocess.run", run)
    with pytest.raises(subprocess.CalledProcessError):
        _verify_offline_analysis(Path("installed-cli"), work=tmp_path, environment={})
