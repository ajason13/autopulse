"""Live smoke harness CLI tests."""

from __future__ import annotations

import json

import pytest

from autopulse.live import cli


VIN_HASHED = "a" * 64


def test_cli_dry_run_validates_without_opening_adapter(tmp_path, capsys):
    exit_code = cli.main(
        [
            "--adapter-port",
            "/dev/tty.fake",
            "--vin-hashed",
            VIN_HASHED,
            "--output-path",
            str(tmp_path / "capture.jsonl"),
            "--max-samples",
            "1",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert not (tmp_path / "capture.jsonl").exists()


def test_cli_requires_vin_hashed_before_adapter_open(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                "A" * 64,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )


def test_cli_requires_limit(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--dry-run",
            ]
        )


def test_cli_requires_stationary_confirmation_for_live_capture(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--max-samples",
                "1",
            ]
        )


def test_cli_rejects_runtime_log_path_traversal_before_opening_file(tmp_path):
    log_path = tmp_path / ".." / "run.log"

    with pytest.raises(SystemExit):
        cli.main(
            [
                "--adapter-port",
                "/dev/tty.fake",
                "--vin-hashed",
                VIN_HASHED,
                "--output-path",
                str(tmp_path / "capture.jsonl"),
                "--runtime-log-path",
                str(log_path),
                "--max-samples",
                "1",
                "--dry-run",
            ]
        )

    assert not log_path.exists()
