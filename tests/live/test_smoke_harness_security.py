"""Live smoke harness security tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from autopulse.data.validator import SecurityViolationRedLine
from autopulse.live.adapter import LIVE_ALLOWED_PIDS, LiveOBDAdapter, PIDNotAllowedError


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
