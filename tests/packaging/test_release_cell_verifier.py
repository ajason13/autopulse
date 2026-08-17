from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import zipfile

from scripts.verify_release_cell import (
    _pip_install_command,
    _require_failed_install,
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
