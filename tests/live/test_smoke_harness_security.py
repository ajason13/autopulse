"""Live smoke harness security tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from autopulse.data.validator import CommandBlockedException, SecurityViolationRedLine
from autopulse.live.adapter import LIVE_ALLOWED_PIDS, LiveOBDAdapter, PIDNotAllowedError
from autopulse.live.harness import SAFETY_ABORT_EXIT, SmokeHarnessConfig, run_smoke_capture
from tests.live.fakes import FakeICEAdapter, frame_values


@pytest.mark.parametrize("service_id", [0x2E, 0x31, 0x10, 0x27, 0x2F, 0x08, 0x04])
def test_live_adapter_blocks_write_capable_services_before_transmission(service_id):
    adapter = LiveOBDAdapter("/dev/tty.fake", obd_module=object())

    with pytest.raises(SecurityViolationRedLine):
        adapter.validate_outgoing_request(service_id, 0x0C)


def test_live_adapter_rejects_pid_outside_allowlist():
    adapter = LiveOBDAdapter("/dev/tty.fake", obd_module=object())

    with pytest.raises(PIDNotAllowedError):
        adapter.validate_outgoing_request(0x01, 0x09)


def test_live_pid_allowlist_is_exact_initial_ice_set():
    assert LIVE_ALLOWED_PIDS == {0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D}


def test_live_package_does_not_import_tests_namespace():
    live_root = Path("src/autopulse/live")
    for path in live_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("tests")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("tests")


@pytest.mark.parametrize(
    "exc",
    [
        SecurityViolationRedLine(0x2E),
        CommandBlockedException("SECURITY_VIOLATION_RED_LINE", "blocked"),
    ],
)
def test_security_violation_during_capture_aborts_and_disconnects(
    tmp_path,
    fake_vin_hashed,
    exc,
):
    adapter = FakeICEAdapter([frame_values()], fetch_error=exc)
    config = SmokeHarnessConfig(
        adapter_port="/dev/tty.fake",
        vin_hashed=fake_vin_hashed,
        output_path=tmp_path / "capture.jsonl",
        max_samples=1,
        confirmed_stationary=True,
    )

    summary = run_smoke_capture(config, adapter, sleep=lambda _: None)

    assert summary.exit_code == SAFETY_ABORT_EXIT
    assert summary.safety_abort is True
    assert adapter.disconnected is True
    assert (tmp_path / "capture.jsonl").read_text(encoding="utf-8") == ""
