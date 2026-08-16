# Claude — PR-002 current-source packet for fix re-review

This packet supplies the exact current contents requested in Claude’s 2026-08-13 access response. It is self-contained for Claude Chat: do not assume access to this workspace. Review these contents together with the previously supplied pre-fix implementation packet, then return the verdict format requested in `claude-pr-002-packaging-supply-chain-fix-rereview.md`.

## `scripts/verify_release_cell.py`

```python
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
```

## `scripts/packaging_policy.py`

```python
#!/usr/bin/env python3
"""Fail-closed package, privacy, schema, and license evidence checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
from typing import Any
import zipfile


SCHEMA_NAMES = (
    "engine_obd_frame.schema.json",
    "ev_obd_frame.schema.json",
)
ALLOWED_LICENSE_EXPRESSIONS = frozenset(
    {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "MIT",
        "MIT OR Apache-2.0",
        "MPL-2.0",
        "PSF-2.0",
    }
)
FORMULA_PREFIXES = ("=", "+", "-", "@")
_PRIVATE_TEXT_PATTERNS = (
    ("absolute local path", re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])")),
    ("private workspace URL", re.compile(r"https?://(?:www\.)?notion\.so/", re.I)),
    ("private key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    (
        "raw VIN-like identifier",
        # Require a letter to avoid treating 17-digit package timestamps and
        # lockfile integers as VINs. I/O/Q remain excluded per VIN syntax.
        re.compile(
            r"(?<![A-Z0-9])(?=[A-HJ-NPR-Z0-9]{0,16}[A-HJ-NPR-Z])"
            r"[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])"
        ),
    ),
)
_DENIED_PATH_PARTS = frozenset(
    {
        ".git",
        ".github",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "captures",
        "fixtures",
        "live",
        "telemetry",
        "tests",
    }
)
_DENIED_FILENAMES = frozenset({".env", ".envrc", ".DS_Store"})


class PolicyError(ValueError):
    """Raised when release evidence violates an AutoPulse policy gate."""


def verify_schema_resources(repository: Path) -> dict[str, str]:
    """Require packaged schemas to be byte-identical to canonical root files."""
    checksums: dict[str, str] = {}
    for name in SCHEMA_NAMES:
        canonical = repository / "schemas" / name
        packaged = repository / "src" / "autopulse" / "schemas" / name
        canonical_bytes = canonical.read_bytes()
        packaged_bytes = packaged.read_bytes()
        if canonical_bytes != packaged_bytes:
            raise PolicyError(f"Packaged schema drift detected: {name}")
        checksums[name] = hashlib.sha256(canonical_bytes).hexdigest()
    return checksums


def neutralize_csv_cell(value: object) -> str:
    """Prevent spreadsheet formula evaluation in support-oriented CSV output."""
    rendered = str(value)
    if rendered.startswith(FORMULA_PREFIXES):
        return "'" + rendered
    return rendered


def validate_license_records(
    records: object,
    *,
    allowlist: frozenset[str] = ALLOWED_LICENSE_EXPRESSIONS,
) -> list[dict[str, str]]:
    """Validate the normative pip-licenses JSON report against SPDX policy."""
    if not isinstance(records, list):
        raise PolicyError("License report must be a JSON array.")

    normalized: list[dict[str, str]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise PolicyError(f"License record {index} must be an object.")
        name = str(record.get("Name", "")).strip()
        version = str(record.get("Version", "")).strip()
        expression = str(record.get("License", "")).strip()
        if not name or not version or not expression:
            raise PolicyError(f"License record {index} is missing Name, Version, or License.")
        lowered = expression.lower()
        if lowered == "unknown" or "licenseref-" in lowered:
            raise PolicyError(f"Disallowed license expression for {name}: {expression}")
        if expression not in allowlist:
            raise PolicyError(f"License expression is not allowlisted for {name}: {expression}")
        normalized.append({"Name": name, "Version": version, "License": expression})
    return sorted(normalized, key=lambda item: (item["Name"].casefold(), item["Version"]))


def write_license_reports(input_path: Path, json_path: Path, csv_path: Path) -> None:
    """Validate actual pip-licenses JSON and emit deterministic safe artifacts."""
    records = validate_license_records(json.loads(input_path.read_text(encoding="utf-8")))
    json_path.write_text(
        json.dumps(records, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("Name", "Version", "License"),
            lineterminator="\n",
        )
        writer.writeheader()
        for record in records:
            writer.writerow({key: neutralize_csv_cell(value) for key, value in record.items()})


def _normalized_member_path(name: str, *, sdist: bool) -> PurePosixPath:
    if "\\" in name:
        raise PolicyError(f"Archive member uses a non-POSIX separator: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PolicyError(f"Unsafe archive member path: {name}")
    if sdist:
        if len(path.parts) < 2:
            raise PolicyError(f"sdist member is outside its single root: {name}")
        path = PurePosixPath(*path.parts[1:])
    return path


def _check_member_path(path: PurePosixPath, *, wheel: bool) -> None:
    git_parts = [part for part in path.parts if part.startswith(".git")]
    if git_parts and not (not wheel and str(path) == ".gitignore"):
        raise PolicyError(f"Denied VCS archive path: {path}")
    if any(part in _DENIED_PATH_PARTS for part in path.parts):
        raise PolicyError(f"Denied archive path: {path}")
    if path.name in _DENIED_FILENAMES or path.suffix in {".pyc", ".pyo"}:
        raise PolicyError(f"Denied archive file: {path}")
    if wheel:
        allowed = (
            path.parts[0] == "autopulse"
            or (len(path.parts) >= 2 and path.parts[0].endswith(".dist-info"))
        )
    else:
        allowed = (
            str(path)
            in {
                "LICENSE",
                # Hatchling always includes the root VCS ignore file in an
                # sdist. This single path is the documented backend exception.
                ".gitignore",
                "docs/offline-package.md",
                "pyproject.toml",
                "uv.lock",
                "PKG-INFO",
            }
            or path.parts[:1] == ("schemas",)
            or path.parts[:2] == ("src", "autopulse")
        )
    if not allowed:
        raise PolicyError(f"Archive member is not allowlisted: {path}")


def _scan_text(text: str, label: str) -> None:
    for description, pattern in _PRIVATE_TEXT_PATTERNS:
        if pattern.search(text):
            raise PolicyError(f"{description} detected in {label}")


def scan_json_evidence(path: Path) -> None:
    """Reject private values anywhere in generated JSON evidence."""
    payload = json.loads(path.read_text(encoding="utf-8"))

    def walk(value: Any, location: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                walk(key, f"{location}.<key>")
                walk(nested, f"{location}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                walk(nested, f"{location}[{index}]")
        elif isinstance(value, str):
            _scan_text(value, location)

    walk(payload, path.name)


def validate_archive(path: Path) -> dict[str, str]:
    """Validate wheel/sdist inventory, links, duplicates, and private content."""
    is_wheel = path.suffix == ".whl"
    is_sdist = path.name.endswith(".tar.gz")
    if not (is_wheel or is_sdist):
        raise PolicyError("Expected a .whl or .tar.gz package artifact.")

    contents: dict[str, str] = {}
    raw_names: set[str] = set()

    def consume(name: str, data: bytes, *, link: bool = False) -> None:
        if name in raw_names:
            raise PolicyError(f"Duplicate archive member: {name}")
        raw_names.add(name)
        if link:
            raise PolicyError(f"Links are prohibited in package artifacts: {name}")
        normalized = _normalized_member_path(name, sdist=is_sdist)
        _check_member_path(normalized, wheel=is_wheel)
        normalized_name = str(normalized)
        if normalized_name in contents:
            raise PolicyError(f"Duplicate normalized archive member: {normalized_name}")
        if data:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = ""
            if text:
                _scan_text(text, normalized_name)
        contents[normalized_name] = hashlib.sha256(data).hexdigest()

    if is_wheel:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                mode = info.external_attr >> 16
                if info.is_dir():
                    if stat.S_ISLNK(mode):
                        raise PolicyError(
                            f"Links are prohibited in package artifacts: {info.filename}"
                        )
                    continue
                consume(
                    info.filename,
                    archive.read(info),
                    link=stat.S_ISLNK(mode),
                )
    else:
        with tarfile.open(path, mode="r:gz") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk():
                    raise PolicyError(
                        f"Links are prohibited in package artifacts: {member.name}"
                    )
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member) if member.isfile() else None
                consume(
                    member.name,
                    b"" if extracted is None else extracted.read(),
                )
    return contents


def compare_reproducible(first: Path, second: Path) -> None:
    """Compare canonical JSON or archive payload inventories."""
    if first.suffix == ".json" and second.suffix == ".json":
        first_value = json.loads(first.read_text(encoding="utf-8"))
        second_value = json.loads(second.read_text(encoding="utf-8"))
    else:
        first_value = validate_archive(first)
        second_value = validate_archive(second)
    if first_value != second_value:
        raise PolicyError(f"Reproducibility comparison failed: {first.name} != {second.name}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    schemas = commands.add_parser("schemas")
    schemas.add_argument("repository", type=Path)

    archive = commands.add_parser("archive")
    archive.add_argument("artifact", type=Path)

    evidence = commands.add_parser("evidence")
    evidence.add_argument("json_file", type=Path)

    licenses = commands.add_parser("licenses")
    licenses.add_argument("pip_licenses_json", type=Path)
    licenses.add_argument("normative_json", type=Path)
    licenses.add_argument("support_csv", type=Path)

    compare = commands.add_parser("compare")
    compare.add_argument("first", type=Path)
    compare.add_argument("second", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "schemas":
        result = verify_schema_resources(args.repository)
        print(json.dumps(result, sort_keys=True))
    elif args.command == "archive":
        result = validate_archive(args.artifact)
        print(json.dumps(result, sort_keys=True))
    elif args.command == "evidence":
        scan_json_evidence(args.json_file)
    elif args.command == "licenses":
        write_license_reports(args.pip_licenses_json, args.normative_json, args.support_csv)
    elif args.command == "compare":
        compare_reproducible(args.first, args.second)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, tarfile.TarError, zipfile.BadZipFile, PolicyError) as exc:
        print(f"packaging policy failed: {exc}", file=os.sys.stderr)
        raise SystemExit(1) from exc
```

## `tests/packaging/test_release_cell_verifier.py`

```python
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

from scripts.verify_release_cell import (
    _pip_install_command,
    _require_failed_install,
)


def _offline_environment() -> dict[str, str]:
    return {
        "PATH": str(Path(sys.executable).parent),
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }


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
```

## `tests/packaging/test_packaging_policy.py`

```python
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import shutil
import stat
import tarfile
import zipfile

import pytest

from scripts.packaging_policy import (
    PolicyError,
    compare_reproducible,
    scan_json_evidence,
    validate_archive,
    validate_license_records,
    verify_schema_resources,
    write_license_reports,
)


REPOSITORY = Path(__file__).resolve().parents[2]


def test_packaged_schemas_are_byte_identical_to_canonical_sources() -> None:
    checksums = verify_schema_resources(REPOSITORY)
    assert set(checksums) == {
        "engine_obd_frame.schema.json",
        "ev_obd_frame.schema.json",
    }
    assert all(len(checksum) == 64 for checksum in checksums.values())


def test_schema_integrity_check_detects_one_byte_source_mutation(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    shutil.copytree(REPOSITORY / "schemas", repository / "schemas")
    shutil.copytree(
        REPOSITORY / "src" / "autopulse" / "schemas",
        repository / "src" / "autopulse" / "schemas",
    )
    canonical = repository / "schemas" / "engine_obd_frame.schema.json"
    canonical.write_bytes(canonical.read_bytes() + b" ")

    with pytest.raises(PolicyError, match="drift"):
        verify_schema_resources(repository)


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_real_license_report_csv_neutralizes_formula_cells(
    tmp_path: Path,
    prefix: str,
) -> None:
    source = tmp_path / "pip-licenses.json"
    normative = tmp_path / "licenses.json"
    support = tmp_path / "licenses.csv"
    source.write_text(
        json.dumps([{"Name": prefix + "package", "Version": "1.0", "License": "MIT"}]),
        encoding="utf-8",
    )

    write_license_reports(source, normative, support)

    with support.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert rows[0]["Name"] == "'" + prefix + "package"
    assert json.loads(normative.read_text(encoding="utf-8"))[0]["Name"] == prefix + "package"


@pytest.mark.parametrize(
    "expression",
    ["UNKNOWN", "LicenseRef-Proprietary", "MIT AND", "GPL-3.0-only"],
)
def test_license_validator_fails_closed(expression: str) -> None:
    with pytest.raises(PolicyError):
        validate_license_records(
            [{"Name": "dependency", "Version": "1.0", "License": expression}]
        )


@pytest.mark.parametrize(
    "private_value",
    [
        "/Users/example/private/output.json",
        "/home/example/private/output.json",
        "https://www.notion.so/private-page",
        "-----BEGIN PRIVATE KEY-----",
        "1M8GDM9AXKP042788",
    ],
)
def test_json_evidence_scan_rejects_private_values(
    tmp_path: Path,
    private_value: str,
) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({"nested": [{"value": private_value}]}), encoding="utf-8")
    with pytest.raises(PolicyError):
        scan_json_evidence(evidence)


def _write_wheel(path: Path, members: list[tuple[str, bytes]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)


def test_wheel_inventory_accepts_only_offline_package_surface(tmp_path: Path) -> None:
    wheel = tmp_path / "autopulse-0.1.0-py3-none-any.whl"
    _write_wheel(
        wheel,
        [
            ("autopulse/__init__.py", b'__version__ = "0.1.0"\n'),
            ("autopulse/schemas/engine_obd_frame.schema.json", b"{}\n"),
            ("autopulse-0.1.0.dist-info/METADATA", b"Name: autopulse\n"),
            ("autopulse-0.1.0.dist-info/RECORD", b""),
        ],
    )
    inventory = validate_archive(wheel)
    assert "autopulse/__init__.py" in inventory
    assert all("/live/" not in member for member in inventory)


@pytest.mark.parametrize(
    ("member", "content"),
    [
        ("autopulse/live/cli.py", b""),
        ("tests/test_package.py", b""),
        ("autopulse/../secret.txt", b""),
        ("autopulse/module.pyc", b""),
        ("autopulse/module.py", b'RAW = "1M8GDM9AXKP042788"\n'),
    ],
)
def test_wheel_inventory_rejects_prohibited_members_and_content(
    tmp_path: Path,
    member: str,
    content: bytes,
) -> None:
    wheel = tmp_path / "autopulse-0.1.0-py3-none-any.whl"
    _write_wheel(wheel, [(member, content)])
    with pytest.raises(PolicyError):
        validate_archive(wheel)


def test_wheel_inventory_rejects_duplicate_members(tmp_path: Path) -> None:
    wheel = tmp_path / "autopulse-0.1.0-py3-none-any.whl"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("autopulse/__init__.py", b"one")
            archive.writestr("autopulse/__init__.py", b"two")
    with pytest.raises(PolicyError, match="Duplicate"):
        validate_archive(wheel)


def test_wheel_inventory_rejects_symlinks(tmp_path: Path) -> None:
    wheel = tmp_path / "autopulse-0.1.0-py3-none-any.whl"
    link = zipfile.ZipInfo("autopulse/link.py")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(link, "target.py")
    with pytest.raises(PolicyError, match="Links"):
        validate_archive(wheel)


def test_sdist_inventory_accepts_canonical_schema_and_offline_source(tmp_path: Path) -> None:
    sdist = tmp_path / "autopulse-0.1.0.tar.gz"
    members = {
        "autopulse-0.1.0/pyproject.toml": b"[project]\n",
        "autopulse-0.1.0/.gitignore": b"__pycache__/\n",
        "autopulse-0.1.0/schemas/engine_obd_frame.schema.json": b"{}\n",
        "autopulse-0.1.0/src/autopulse/__init__.py": b"",
    }
    with tarfile.open(sdist, "w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    inventory = validate_archive(sdist)
    assert "schemas/engine_obd_frame.schema.json" in inventory


@pytest.mark.parametrize(
    "member",
    [
        "autopulse-0.1.0/.github/workflows/ci.yml",
        "autopulse-0.1.0/.git/config",
        "autopulse-0.1.0/nested/.gitignore",
        "autopulse-0.1.0/.gitattributes",
    ],
)
def test_sdist_inventory_rejects_every_other_git_member(
    tmp_path: Path,
    member: str,
) -> None:
    sdist = tmp_path / "autopulse-0.1.0.tar.gz"
    data = b"test\n"
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo(member)
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    with pytest.raises(PolicyError, match="VCS"):
        validate_archive(sdist)


def test_wheel_inventory_rejects_root_gitignore_exception(tmp_path: Path) -> None:
    wheel = tmp_path / "autopulse-0.1.0-py3-none-any.whl"
    _write_wheel(wheel, [(".gitignore", b"__pycache__/\n")])
    with pytest.raises(PolicyError, match="VCS"):
        validate_archive(wheel)


def test_reproducibility_compare_detects_payload_change(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"bomFormat":"CycloneDX","components":[]}\n', encoding="utf-8")
    second.write_text('{"components":[],"bomFormat":"CycloneDX"}\n', encoding="utf-8")
    compare_reproducible(first, second)
    second.write_text('{"bomFormat":"CycloneDX","components":[{}]}\n', encoding="utf-8")
    with pytest.raises(PolicyError, match="Reproducibility"):
        compare_reproducible(first, second)
```

## `docs/qa/pr-002-cp313-macos-x86_64.md`

```text
# PR-002 Native Packaging Cell Evidence

- Cell: `cp313-macos-x86_64`
- CPython: `3.13.14`
- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)
- Registry access during install probes: DISABLED (`--no-index` and `PIP_NO_INDEX=1`)
- Tampered-hash install rejection: PASS
- Incomplete-wheelhouse install rejection: PASS
- Built wheel archive policy (`validate_archive()`): PASS
- Built sdist archive policy (`validate_archive()`): PASS
- Installed validator/schema resource smoke: PASS
- Installed offline CLI smoke: PASS
- `autopulse.live` absence (metadata and import): PASS
- AutoPulse wheel: `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- AutoPulse sdist: `autopulse-0.1.0.tar.gz` (`sha256:b31a42fec8de5080aa8f7c00bacc7a9477a343677d9b3ef4bd76467713c4fd8c`)
- Wheelhouse manifest SHA-256: `ab923c3684dc95b9c4562879c6c754ecd5811af5c54c583a7f972d3a09bcfdc5`

## Selected wheels

- `attrs-26.1.0-py3-none-any.whl` (`sha256:c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309`)
- `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- `jsonschema-4.26.0-py3-none-any.whl` (`sha256:d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce`)
- `jsonschema_specifications-2025.9.1-py3-none-any.whl` (`sha256:98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe`)
- `referencing-0.37.0-py3-none-any.whl` (`sha256:381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231`)
- `rpds_py-2026.6.3-cp313-cp313-macosx_10_12_x86_64.whl` (`sha256:3cfe765c1da0072636ca06628261e0ea05688e160d5c8a03e0217c3854037223`)
```

## `docs/qa/pr-002-cp314-macos-x86_64.md`

```text
# PR-002 Native Packaging Cell Evidence

- Cell: `cp314-macos-x86_64`
- CPython: `3.14.6`
- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)
- Registry access during install probes: DISABLED (`--no-index` and `PIP_NO_INDEX=1`)
- Tampered-hash install rejection: PASS
- Incomplete-wheelhouse install rejection: PASS
- Built wheel archive policy (`validate_archive()`): PASS
- Built sdist archive policy (`validate_archive()`): PASS
- Installed validator/schema resource smoke: PASS
- Installed offline CLI smoke: PASS
- `autopulse.live` absence (metadata and import): PASS
- AutoPulse wheel: `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- AutoPulse sdist: `autopulse-0.1.0.tar.gz` (`sha256:b31a42fec8de5080aa8f7c00bacc7a9477a343677d9b3ef4bd76467713c4fd8c`)
- Wheelhouse manifest SHA-256: `d09b9af5747486ae1a57bc6f35cdb2bd12d88635d12d070f809d67820a5847be`

## Selected wheels

- `attrs-26.1.0-py3-none-any.whl` (`sha256:c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309`)
- `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- `jsonschema-4.26.0-py3-none-any.whl` (`sha256:d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce`)
- `jsonschema_specifications-2025.9.1-py3-none-any.whl` (`sha256:98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe`)
- `referencing-0.37.0-py3-none-any.whl` (`sha256:381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231`)
- `rpds_py-2026.6.3-cp314-cp314-macosx_10_12_x86_64.whl` (`sha256:931908d9fc855d8f74783377822be318edb6dcb19e47169dc038f9a1bf60b06e`)
```

## `docs/specs/pr-002-packaging-supply-chain-decision-record.md`

```text
# PR-002: Packaging and Supply-Chain Implementation Decision Record

**Status:** Codex-owned implementation contract; Claude's 2026-08-13 re-review returned `NO BLOCKERS` and authorized PR-002 implementation.  
**Parent policy:** docs/specs/pr-001-offline-release-profile-and-threat-model.md.  
**Checked:** 2026-08-13.

## Scope and boundary

PR-002 will make AutoPulse installable as a local, educational offline/replay package. It may change Python package metadata, dependency installation inputs, schema-resource loading required by an installed package, build/support scripts, tests, and documentation. It must not add live adapters, vehicle capture, VIN reads, uploads, analytics, write-capable diagnostics, CI workflow changes, or release publication.

The repository has a src package but no pyproject metadata, lock, package build, SBOM, or release artifact. requirements.txt is unpinned and lists pandas, numpy, and python-dotenv even though source imports do not currently use them. Their removal or reclassification requires tested evidence; they are not carried into runtime metadata without a documented use.

## Approved design

| Concern | Decision |
| --- | --- |
| Build backend | PEP 621 pyproject metadata with Hatchling, static PEP 440 version, Python >=3.13,<3.15, and reproducible builds. Use python -m build so the wheel is built from the sdist. |
| Package contents | Explicitly include the offline autopulse modules and exclude autopulse/live/** plus any live-only module from the wheel and sdist. The installed offline wheel must make import autopulse.live fail. Build exactly one pure-Python wheel and one sdist. Root schemas remain canonical; the build stages byte-identical copies as package resources. |
| Installed schema loader | Rewrite autopulse.data.validator to remove its repository-relative SCHEMA_PATH/EV_SCHEMA_PATH lookup and eager file opening. Its only production schema source is packaged data loaded through importlib.resources; it must construct both Draft7Validator instances successfully in an installed wheel with the repository absent from sys.path. |
| Public CLI | autopulse-debug maps only to the existing sanitized offline debug CLI. The live CLI receives no public console entry point. |
| Dependency groups | Runtime metadata lists only dependencies proven necessary by source/import and installed-workflow tests. pytest and package/security tools are isolated development/tooling groups. |
| Resolution authority | Commit one universal uv.lock. It locks exact versions across allowed markers, but is not wheel evidence. Pin/hash build frontend/backend and tooling separately. |
| Per-cell installation proof | Export a fully pinned, SHA-256-hashed requirements view per supported Python/OS/architecture cell. Native clean jobs use pip --require-hashes --only-binary=:all: with matching local wheelhouse. Cross-platform download is only early validation, never final support proof. |
| Offline install | Build and verify one wheelhouse per supported cell; clean install uses --no-index and --find-links, followed by installed-wheel replay/validation. |
| SBOM | CycloneDX JSON 1.6 via pinned cyclonedx-py from the exact clean installed release environment, schema-validated and reproducibly generated. Bind each SBOM to commit, AutoPulse wheel SHA-256, and selected dependency-wheel manifest SHA-256; build twice under controlled inputs and compare the canonicalized result. |
| Vulnerability and license evidence | Pinned pip-audit performs strict JSON known-vulnerability checks. Pinned pip-licenses produces a normative JSON expression/license inventory and a CSV support inventory whose cells are formula-neutralized. An AutoPulse-owned validator, not pip-licenses --allow-only alone, rejects UNKNOWN, LicenseRef, unparseable, or non-allowlisted expressions. Findings or license failures fail closed unless PR-001's independent, expiry-dated exception procedure applies. |
| Artifact gates | Run twine check --strict, check-wheel-contents as a supplemental check, and an AutoPulse-owned deterministic inventory validator for both wheel and sdist. The validator normalizes POSIX paths, rejects absolute/parent/link/duplicate members, and compares all members with the approved allowlist. Hatchling's unavoidable root `.gitignore` is the sole VCS-named exception: it is allowed only in an sdist at its exact root, never in a wheel; `.git/`, `.github/`, and every other `.git*` member remain prohibited. |
| Privacy gates | Scan generated SBOMs and evidence for absolute-local paths and private URLs. Inventory checks deny env files, VCS metadata, caches/bytecode, tests/test-only modules, fixture data, secrets, raw telemetry, and private operational artifacts by both normalized member path and a lightweight raw-identifier/content scan. The content scan is intentionally suppression-free: new sanctioned examples must avoid raw identifiers or be excluded from the release artifact, so no label can weaken this fail-closed gate. |

## Required implementation artifacts

- pyproject metadata with package/resource configuration and the offline-only CLI;
- universal uv.lock; per-cell hashed requirements exports; wheelhouse manifests containing filenames and SHA-256 values;
- deterministic build, wheelhouse, resource-integrity, archive-inventory, SBOM/privacy, license, and vulnerability scripts;
- a documented local matrix-evidence runner that produces a sanitized, reviewable `docs/qa/` summary of commands, supported-cell results, selected wheel names, and SHA-256 values. It is the PR-002 evidence mechanism until PR-003 moves the matrix into CI; no wheelhouse or binary artifact is committed;
- a CycloneDX JSON SBOM for each distinct resolved supported environment, unless equality is demonstrated;
- tests for installed-wheel import of `autopulse.data.validator` with no checkout on `sys.path`, installed-wheel replay/validation, canonical-to-packaged schema checksum equality including a drift-detection mutation, absence and import failure of autopulse.live and any live-only module, no public live CLI, wheel-only hash-checked install, artifact allowlist and content-scan rejection, SBOM privacy rejection, deterministic SBOM/build comparison, and formula escaping in the generated pip-licenses CSV inventory for values beginning =, +, -, or @;
- user documentation that states supported cells, offline installation, and live/use prohibitions.

No generated wheelhouse, release artifact, scan output, or environment-specific evidence is committed until the PR-004/PR-005 retention/publication decision permits it.

## Acceptance criteria

1. Every supported cell performs native clean installation from only prebuilt wheels, exact hashes, and a matching local wheelhouse. Missing wheel, hash, or attempted network access fails. The documented local matrix-evidence runner produces the sanitized `docs/qa/` summary for the implementation audit.
2. With the repository absent from `sys.path`, the installed wheel imports `autopulse.data.validator`, constructs both schema validators from `importlib.resources`, and completes documented replay/validation. A source/resource byte comparison and deliberate one-byte source-schema mutation prove drift detection works.
3. The sdist, wheel archive listing, and wheel `RECORD` contain no live-capture path; `import autopulse.live` and `import autopulse.live.cli` fail after installation. Both artifacts pass the explicit content allowlist and content scan.
4. SBOM, normative JSON license report, formula-neutralized CSV license inventory, and vulnerability report are generated from the exact resolved clean environment. SBOM validation, privacy scans, and a controlled build-twice/canonicalized-SBOM comparison fail closed.
5. A critical/high vulnerability exception names owner, rationale, mitigation, expiry, and independent Claude approval. No implementer self-approval is accepted.
6. Claude-selected tests and the existing suite pass. CI workflow changes and release publication are deferred to PR-003 and PR-005.

## Verification plan

Run focused package tests; build sdist and wheel twice from clean trees; install the wheel without network from each matching wheelhouse and without the checkout on `sys.path`; execute replay smoke checks; validate packaged schemas and a deliberate drift mutation; inspect wheel, sdist, and `RECORD` inventories; generate and scan SBOM/license/vulnerability evidence; write the sanitized local matrix summary; then run the complete suite and git diff --check.

## Primary-source basis and caveats

Sources checked 2026-08-13:

- Hatch, build configuration: https://hatch.pypa.io/1.10/config/build/
- PyPA build CLI: https://build.pypa.io/en/latest/reference/cli.html
- uv project layout and universal lock: https://docs.astral.sh/uv/concepts/projects/layout/
- uv resolver caveat: https://docs.astral.sh/uv/reference/internals/resolver/
- pip secure installs: https://pip.pypa.io/en/stable/topics/secure-installs/
- pip download: https://pip.pypa.io/en/stable/cli/pip_download/
- CycloneDX Python tool: https://cyclonedx-bom-tool.readthedocs.io/en/latest/usage.html
- pip-audit: https://pypi.org/project/pip-audit/
- pip-licenses: https://pypi.org/project/pip-licenses/
- check-wheel-contents: https://github.com/jwodder/check-wheel-contents

The exact package name, public import surface, jsonschema lower bound, license allowlist, retention policy, attestation mechanism, and Linux/macOS wheel-tag policy remain maintainer decisions or implementation evidence. A universal lock does not prove wheel availability, and scanner success is not a guarantee that dependencies are benign.
```

## `/private/tmp/pr002-full-suite.log`

```text
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 44%]
........................................................................ [ 55%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 89%]
...................................................................      [100%]
643 passed in 57.54s
```


