#!/usr/bin/env python3
"""Verify one native AutoPulse wheel-only, hash-checked, offline cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import venv

try:
    from scripts.packaging_policy import validate_archive
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from packaging_policy import validate_archive


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def _venv_python(environment_path: Path) -> Path:
    venv.EnvBuilder(with_pip=True).create(environment_path)
    scripts = environment_path / ("Scripts" if os.name == "nt" else "bin")
    return scripts / ("python.exe" if os.name == "nt" else "python")


def _pip_install_command(
    python: Path,
    wheelhouse: Path,
    requirements: Path,
) -> list[str]:
    return [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "--require-hashes",
        "--only-binary=:all:",
        "-r",
        str(requirements),
    ]


def _require_failed_install(
    *,
    environment_path: Path,
    wheelhouse: Path,
    requirements: Path,
    work: Path,
    environment: dict[str, str],
    expected_error: str,
) -> None:
    python = _venv_python(environment_path)
    result = subprocess.run(
        _pip_install_command(python, wheelhouse, requirements),
        cwd=work,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout + "\n" + result.stderr).lower()
    if result.returncode == 0:
        raise RuntimeError(f"Negative install probe unexpectedly passed: {expected_error}")
    if expected_error not in output:
        raise RuntimeError(
            f"Negative install probe failed for an unexpected reason; expected {expected_error!r}."
        )


def _cell_name() -> str:
    machine = platform.machine().lower()
    if sys.platform.startswith("linux"):
        operating_system = "linux"
    elif sys.platform == "darwin":
        operating_system = "macos"
    elif sys.platform == "win32":
        operating_system = "windows"
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
    return f"cp{sys.version_info.major}{sys.version_info.minor}-{operating_system}-{machine}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--locked-requirements", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--environment", type=Path)
    args = parser.parse_args()

    if platform.python_implementation() != "CPython":
        parser.error("Only CPython release cells are supported.")
    if sys.version_info[:2] not in {(3, 13), (3, 14)}:
        parser.error("Release-cell verification requires CPython 3.13 or 3.14.")

    wheel = args.wheel.resolve()
    sdist = args.sdist.resolve()
    validate_archive(wheel)
    validate_archive(sdist)
    wheelhouse = args.wheelhouse.resolve()
    wheelhouse.mkdir(parents=True, exist_ok=True)
    staged_wheel = wheelhouse / wheel.name
    if staged_wheel != wheel:
        shutil.copy2(wheel, staged_wheel)

    wheel_files = sorted(wheelhouse.glob("*.whl"), key=lambda item: item.name)
    if not wheel_files:
        parser.error("The cell wheelhouse contains no wheels.")
    manifest = [{"filename": item.name, "sha256": _sha256(item)} for item in wheel_files]
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if args.manifest_output:
        args.manifest_output.write_bytes(manifest_bytes)

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    with tempfile.TemporaryDirectory(prefix="autopulse-cell-") as temporary:
        work = Path(temporary)
        combined = work / "requirements.txt"
        locked_text = args.locked_requirements.read_text(encoding="utf-8").rstrip()
        if "://" in locked_text or " @ " in locked_text:
            parser.error("Locked requirements must not contain direct or remote URLs.")
        wheel_sha256 = _sha256(staged_wheel)
        combined.write_text(
            locked_text
            + "\n"
            + f"autopulse==0.1.0 --hash=sha256:{wheel_sha256}\n",
            encoding="utf-8",
        )
        environment_path = args.environment.resolve() if args.environment else work / "venv"
        if environment_path.exists():
            parser.error("--environment must not already exist")
        python = _venv_python(environment_path)
        scripts = environment_path / ("Scripts" if os.name == "nt" else "bin")
        debug_command = scripts / ("autopulse-debug.exe" if os.name == "nt" else "autopulse-debug")

        _run(
            _pip_install_command(python, wheelhouse, combined),
            cwd=work,
            environment=environment,
        )
        smoke = """
import importlib.metadata
import importlib.resources
import importlib.util
from autopulse.data.validator import ENGINE_OBD_FRAME_VALIDATOR, EV_OBD_FRAME_VALIDATOR, validate_frame

assert importlib.resources.files("autopulse.schemas").joinpath("engine_obd_frame.schema.json").is_file()
validate_frame({
    "timestamp": "2026-01-01T00:00:00Z",
    "vin_hashed": "a" * 64,
    "protocol": "SAE_J1979",
    "engine_rpm": 750.0,
    "vehicle_speed": 0,
    "coolant_temp": 90.0,
    "engine_load": 20.0,
    "stft_bank1": 0.0,
    "ltft_bank1": 0.0,
})
assert importlib.util.find_spec("autopulse.live") is None
files = [str(item) for item in importlib.metadata.files("autopulse") or ()]
assert not any(item.startswith("autopulse/live/") for item in files)
scripts = [entry.name for entry in importlib.metadata.entry_points(group="console_scripts") if entry.dist and entry.dist.name == "autopulse"]
assert scripts == ["autopulse-debug"]
"""
        _run([str(python), "-I", "-c", smoke], cwd=work, environment=environment)
        _run([str(debug_command), "--help"], cwd=work, environment=environment)

        tampered = work / "requirements-tampered-hash.txt"
        tampered.write_text(
            combined.read_text(encoding="utf-8").replace(wheel_sha256, "0" * 64, 1),
            encoding="utf-8",
        )
        _require_failed_install(
            environment_path=work / "tampered-hash-venv",
            wheelhouse=wheelhouse,
            requirements=tampered,
            work=work,
            environment=environment,
            expected_error="hash",
        )

        incomplete_wheelhouse = work / "incomplete-wheelhouse"
        incomplete_wheelhouse.mkdir()
        dependency_wheels = [item for item in wheel_files if item.name != staged_wheel.name]
        if not dependency_wheels:
            raise RuntimeError("Incomplete-wheelhouse probe requires a dependency wheel.")
        omitted_wheel = dependency_wheels[0]
        for item in wheel_files:
            if item != omitted_wheel:
                shutil.copy2(item, incomplete_wheelhouse / item.name)
        _require_failed_install(
            environment_path=work / "incomplete-wheelhouse-venv",
            wheelhouse=incomplete_wheelhouse,
            requirements=combined,
            work=work,
            environment=environment,
            expected_error="no matching distribution",
        )

    summary = [
        "# PR-002 Native Packaging Cell Evidence",
        "",
        f"- Cell: `{_cell_name()}`",
        f"- CPython: `{platform.python_version()}`",
        "- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)",
        "- Registry access during install probes: DISABLED (`--no-index` and `PIP_NO_INDEX=1`)",
        "- Tampered-hash install rejection: PASS",
        "- Incomplete-wheelhouse install rejection: PASS",
        "- Built wheel archive policy (`validate_archive()`): PASS",
        "- Built sdist archive policy (`validate_archive()`): PASS",
        "- Installed validator/schema resource smoke: PASS",
        "- Installed offline CLI smoke: PASS",
        "- `autopulse.live` absence (metadata and import): PASS",
        f"- AutoPulse wheel: `{staged_wheel.name}` (`sha256:{_sha256(staged_wheel)}`)",
        f"- AutoPulse sdist: `{sdist.name}` (`sha256:{_sha256(sdist)}`)",
        f"- Wheelhouse manifest SHA-256: `{manifest_sha256}`",
        "",
        "## Selected wheels",
        "",
    ]
    summary.extend(f"- `{item['filename']}` (`sha256:{item['sha256']}`)" for item in manifest)
    args.summary.write_text("\n".join(summary) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
