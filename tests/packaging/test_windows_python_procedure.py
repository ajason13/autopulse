"""Native failure propagation for the desktop verification entry point."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Native PowerShell procedure")
def test_native_failure_stops_before_checkout_or_dependency_install(tmp_path):
    powershell = shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell 7 is not installed")
    failing_python = tmp_path / "failing python.cmd"
    failing_python.write_text("@exit /b 23\n", encoding="ascii")
    work = tmp_path / "must remain absent"
    procedure = Path(__file__).resolve().parents[2] / "scripts/verify_windows_python.ps1"
    result = subprocess.run(
        [powershell, "-NoProfile", "-File", str(procedure),
         "-Python", str(failing_python), "-Commit", "a" * 40, "-WorkRoot", str(work)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "exit code 23" in result.stderr
    assert not work.exists()
