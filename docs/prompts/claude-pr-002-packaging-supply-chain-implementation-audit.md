# Claude implementation-audit prompt — PR-002 (self-contained)

You are AutoPulse’s independent Lead Auditor. This is an implementation audit, not a public-release approval. Claude Chat has no local filesystem access: assess the supplied text below. It contains all new/changed packaging implementation files and the changed portion of the validator. The unchanged validator body may be compared with the public baseline at https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse/data/validator.py.

## Approved boundaries

AutoPulse’s offline release is educational replay/validation only. It must not distribute live capture, VIN reads, telemetry uploads, write/control diagnostics, DTC clearing, security access, session escalation, or a network-required runtime. CI changes and artifact publication are out of scope.

The implementation must package only the offline surface, use package resources instead of repository-relative schema paths, install from cell-specific prebuilt wheels with exact hashes and no network, fail closed for evidence/privacy/archive issues, and keep root schemas canonical. The only VCS-named artifact exception is a root .gitignore in an sdist because Hatchling always includes it; it is never allowed in a wheel, and .git/, .github/, nested .gitignore, and all other .git* entries remain prohibited.

## Recorded evidence and limitations

- Packaging policy tests: 33 passed.
- Targeted schema/package tests: 198 passed.
- Native CPython 3.14.6/macOS x86_64 offline prebuilt-wheel hash-checked install: passed.
- Deterministic sdist/wheel and CycloneDX SBOM checks: passed.
- Strict hashed pip-audit reported no known vulnerabilities; license policy, twine check --strict, check-wheel-contents, and git diff --check passed.
- The broader suite collected 640 tests; two runs returned exit 0 but output stopped at 33%, so treat the full suite as **incomplete**, not passed.
- CPython 3.13 and native Linux, Windows, and macOS-arm64 evidence remain outstanding.

## Audit questions

1. Can the configured artifacts accidentally include autopulse.live or a live console entry point?
2. Does the validator change really prevent installed-wheel failure when the repository is absent from sys.path?
3. Are schema integrity, offline hash/wheel install, archive allowlist, private-content scan, SBOM, vulnerability/license, and CSV formula safeguards load-bearing?
4. Is the root .gitignore exception correctly scoped and tested?
5. Do the implementation and evidence limitations preclude advancing the implementation to subsequent evidence work?

Return exactly one verdict: APPROVED FOR PR-002 MERGE, APPROVED WITH MINOR FIXES, or NOT APPROVED. List severity-ranked blockers with exact file/function/test references, then state whether the implementation may advance to PR-003/PR-005 evidence work. Do not approve a public release.

## Supplied implementation files

## pyproject.toml

```toml
[build-system]
requires = ["hatchling==1.31.0"]
build-backend = "hatchling.build"

[project]
name = "autopulse"
version = "0.1.0"
description = "Educational, read-only OBD-II validation and offline replay tools"
readme = "docs/offline-package.md"
requires-python = ">=3.13,<3.15"
license = "Apache-2.0"
license-files = ["LICENSE"]
authors = [
  { name = "AutoPulse contributors" },
]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Education",
  "License :: OSI Approved :: Apache Software License",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Topic :: Scientific/Engineering :: Information Analysis",
]
dependencies = [
  "jsonschema>=4.23,<5",
]

[project.optional-dependencies]
dev = [
  "pytest>=9,<10",
]
release = [
  "build==1.5.0",
  "check-wheel-contents==0.6.3",
  "cyclonedx-bom==7.3.1",
  "pip-audit==2.10.1",
  "pip-licenses==5.5.5",
  "twine==6.2.0",
  "uv==0.11.32",
]

[project.scripts]
autopulse-debug = "autopulse.debug:main"

[project.urls]
Repository = "https://github.com/ajason13/autopulse"

[tool.hatch.build]
directory = "dist"
exclude = [
  "/.gitignore",
  "/src/autopulse/live",
  "/src/autopulse/live/**",
]

[tool.hatch.build.targets.sdist]
include = [
  "/LICENSE",
  "/docs/offline-package.md",
  "/pyproject.toml",
  "/schemas/*.json",
  "/src/autopulse/**/*.py",
  "/src/autopulse/schemas/*.json",
  "/uv.lock",
]
exclude = [
  "/.gitignore",
  "/src/autopulse/live",
  "/src/autopulse/live/**",
]

[tool.hatch.build.targets.wheel]
packages = ["src/autopulse"]
exclude = [
  "/src/autopulse/live",
  "/src/autopulse/live/**",
]

[tool.pytest.ini_options]
pythonpath = [".", "src"]
```

## requirements.txt

```text
jsonschema>=4.23,<5
```

## requirements-dev.txt

```text
-r requirements.txt
pytest>=9,<10
```

## requirements-release.txt

```text
# Release tooling is exact-pinned here; uv.lock and per-cell hashed exports are
# the installation authority once generated on supported CPython 3.13/3.14.
build==1.5.0
check-wheel-contents==0.6.3
cyclonedx-bom==7.3.1
hatchling==1.31.0
pip-audit==2.10.1
pip-licenses==5.5.5
twine==6.2.0
uv==0.11.32
```

## src/autopulse/__init__.py

```python
"""AutoPulse public package interfaces."""

__version__ = "0.1.0"
```

## scripts/packaging_policy.py

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

## scripts/build_release_artifacts.py

```python
#!/usr/bin/env python3
"""Build exactly one AutoPulse sdist and one wheel from that sdist."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


def _run(command: list[str], *, environment: dict[str, str]) -> None:
    subprocess.run(command, check=True, env=environment)


def _extract_sdist(sdist: Path, destination: Path) -> Path:
    """Extract a link-free, single-root sdist without path traversal."""
    roots: set[str] = set()
    with tarfile.open(sdist, mode="r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise RuntimeError(f"Unsafe sdist member: {member.name}")
            roots.add(path.parts[0])
            if member.issym() or member.islnk():
                raise RuntimeError(f"sdist links are prohibited: {member.name}")
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Unable to read sdist member: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read())
    if len(roots) != 1:
        raise RuntimeError(f"Expected one sdist root, found {len(roots)}")
    return destination / roots.pop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("--output must be an empty directory")

    environment = dict(os.environ)
    environment["SOURCE_DATE_EPOCH"] = str(args.source_date_epoch)
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--sdist",
            "--outdir",
            str(output),
            ".",
        ],
        environment=environment,
    )
    sdists = list(output.glob("*.tar.gz"))
    if len(sdists) != 1:
        raise RuntimeError(f"Expected one sdist, found {len(sdists)}")
    with tempfile.TemporaryDirectory(prefix="autopulse-sdist-") as temporary:
        source = _extract_sdist(sdists[0], Path(temporary))
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--wheel",
                "--outdir",
                str(output),
                str(source),
            ],
            environment=environment,
        )
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one wheel, found {len(wheels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## scripts/verify_release_cell.py

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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, environment: dict[str, str]) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)


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
        combined.write_text(
            locked_text
            + "\n"
            + f"autopulse==0.1.0 --hash=sha256:{_sha256(staged_wheel)}\n",
            encoding="utf-8",
        )
        environment_path = args.environment.resolve() if args.environment else work / "venv"
        if environment_path.exists():
            parser.error("--environment must not already exist")
        venv.EnvBuilder(with_pip=True).create(environment_path)
        scripts = environment_path / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        debug_command = scripts / ("autopulse-debug.exe" if os.name == "nt" else "autopulse-debug")

        _run(
            [
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
                str(combined),
            ],
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

    summary = [
        "# PR-002 Native Packaging Cell Evidence",
        "",
        f"- Cell: `{_cell_name()}`",
        f"- CPython: `{platform.python_version()}`",
        "- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)",
        "- Installed validator/schema resource smoke: PASS",
        "- Installed offline CLI smoke: PASS",
        "- `autopulse.live` absence (metadata and import): PASS",
        f"- AutoPulse wheel: `{staged_wheel.name}` (`sha256:{_sha256(staged_wheel)}`)",
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

## scripts/generate_supply_chain_evidence.py

```python
#!/usr/bin/env python3
"""Generate and validate one cell's SBOM, license, and vulnerability evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from packaging_policy import scan_json_evidence, write_license_reports


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _bind_sbom(
    path: Path,
    *,
    commit: str,
    wheel_sha256: str,
    manifest_sha256: str,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("bomFormat") != "CycloneDX" or payload.get("specVersion") != "1.6":
        raise ValueError("Expected a validated CycloneDX JSON 1.6 SBOM.")
    metadata = payload.setdefault("metadata", {})
    properties = metadata.setdefault("properties", [])
    properties.extend(
        [
            {"name": "autopulse:commit", "value": commit},
            {"name": "autopulse:wheel:sha256", "value": wheel_sha256},
            {"name": "autopulse:wheelhouse-manifest:sha256", "value": manifest_sha256},
        ]
    )
    properties.sort(key=lambda item: (item["name"], item["value"]))
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-python", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--locked-requirements", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", action="append", required=True)
    args = parser.parse_args()

    if not __import__("re").fullmatch(r"[0-9a-f]{7,64}", args.commit):
        parser.error("--commit must be a lowercase hexadecimal Git object ID")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error("--output must be empty")

    sbom = output / "sbom.cdx.json"
    raw_licenses = output / "pip-licenses.raw.json"
    normative_licenses = output / "licenses.json"
    support_licenses = output / "licenses.csv"
    vulnerabilities = output / "vulnerabilities.json"

    _run(
        [
            "cyclonedx-py",
            "environment",
            str(args.target_python),
            "--pyproject",
            "pyproject.toml",
            "--mc-type",
            "application",
            "--spec-version",
            "1.6",
            "--output-reproducible",
            "--output-format",
            "JSON",
            "--validate",
            "--output-file",
            str(sbom),
        ]
    )
    _bind_sbom(
        sbom,
        commit=args.commit,
        wheel_sha256=_sha256(args.wheel),
        manifest_sha256=_sha256(args.wheelhouse_manifest),
    )
    scan_json_evidence(sbom)

    _run(
        [
            "pip-licenses",
            "--python",
            str(args.target_python),
            "--from",
            "mixed",
            "--format",
            "json",
            "--packages",
            *args.package,
            "--output-file",
            str(raw_licenses),
        ]
    )
    write_license_reports(raw_licenses, normative_licenses, support_licenses)
    scan_json_evidence(normative_licenses)

    _run(
        [
            "pip-audit",
            "--strict",
            "--progress-spinner=off",
            "--format",
            "json",
            "--requirement",
            str(args.locked_requirements),
            "--require-hashes",
            "--disable-pip",
            "--output",
            str(vulnerabilities),
        ]
    )
    scan_json_evidence(vulnerabilities)

    _run(["twine", "check", "--strict", str(args.wheel)])
    _run(["check-wheel-contents", "--no-config", str(args.wheel)])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"supply-chain evidence failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
```

## tests/packaging/test_package_contract.py

```python
from __future__ import annotations

import ast
from pathlib import Path
import sys
import tomllib


REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE = REPOSITORY / "src" / "autopulse"


def test_project_metadata_exposes_only_offline_console_script() -> None:
    metadata = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["requires-python"] == ">=3.13,<3.15"
    assert metadata["project"]["scripts"] == {"autopulse-debug": "autopulse.debug:main"}
    assert metadata["project"]["dependencies"] == ["jsonschema>=4.23,<5"]
    assert "release" in metadata["project"]["optional-dependencies"]


def test_build_configuration_excludes_live_package_from_both_artifacts() -> None:
    metadata = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    for target in ("sdist", "wheel"):
        excluded = metadata["tool"]["hatch"]["build"]["targets"][target]["exclude"]
        assert "/src/autopulse/live/**" in excluded


def test_offline_package_has_no_unexpected_third_party_imports() -> None:
    third_party: set[str] = set()
    for source in PACKAGE.rglob("*.py"):
        if "live" in source.relative_to(PACKAGE).parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            else:
                continue
            third_party.update(
                name
                for name in names
                if name not in sys.stdlib_module_names and name != "autopulse"
            )
    assert third_party == {"jsonschema"}
```

## tests/packaging/test_packaging_policy.py

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

## docs/offline-package.md

```markdown
# AutoPulse Offline Package

AutoPulse is an educational, read-only OBD-II validation, analysis, and replay
package. This distribution operates on previously supplied local JSON/JSONL/CSV
input. It does not connect to a vehicle, collect telemetry, or use a network at
runtime.

## Supported release cells

The intended support matrix is CPython 3.13 and 3.14 on Ubuntu 24.04 x86_64,
macOS 15 or newer on Apple Silicon or Intel, and Windows 11 x86_64. A cell is
not release-supported until its native wheel-only installation and offline
replay evidence passes. CPython 3.12 and older, PyPy, prereleases,
free-threaded Python, containers, and other operating systems are outside this
profile.

## Disconnected installation

Use only the wheelhouse and hashed requirements export produced for the exact
Python/OS/architecture cell. On a disconnected machine, run:

```text
python -m pip install --no-index --find-links WHEELHOUSE \
  --require-hashes --only-binary=:all: -r HASHED_REQUIREMENTS
```

Do not substitute a wheelhouse from another cell. A missing file or hash is a
hard failure; source builds and network fallback are not supported.

The only installed command is `autopulse-debug`. For example:

```text
autopulse-debug validate-frame --powertrain ICE --file SANITIZED_FRAME_JSON
autopulse-debug replay-ice --jsonl SANITIZED_REPLAY_JSONL
```

Inputs and outputs remain on the operator-controlled filesystem. Debug output
is sanitized, but vehicle-derived identifiers and raw telemetry must not be
placed in shared support artifacts.

## Safety boundary

This package does not support live adapters, vehicle capture, VIN reads, road
testing, unattended monitoring, DTC clearing, actuator/control requests,
diagnostic session escalation, security access, or any write-capable OBD-II or
UDS service. `autopulse.live` is deliberately absent from both package
artifacts and has no console entry point. Existing repository-only stationary
smoke-harness material is outside the offline distribution.
```

## docs/qa/pr-002-cp314-macos-x86_64.md

```markdown
# PR-002 Native Packaging Cell Evidence

- Cell: `cp314-macos-x86_64`
- CPython: `3.14.6`
- Install: PASS (`--no-index --require-hashes --only-binary=:all:`)
- Installed validator/schema resource smoke: PASS
- Installed offline CLI smoke: PASS
- `autopulse.live` absence (metadata and import): PASS
- AutoPulse wheel: `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- Wheelhouse manifest SHA-256: `d09b9af5747486ae1a57bc6f35cdb2bd12d88635d12d070f809d67820a5847be`

## Selected wheels

- `attrs-26.1.0-py3-none-any.whl` (`sha256:c647aa4a12dfbad9333ca4e71fe62ddc36f4e63b2d260a37a8b83d2f043ac309`)
- `autopulse-0.1.0-py3-none-any.whl` (`sha256:7cfa93be7134295e4e76a713bafa652f21af72c3a6da0ea2faa3dbb0742fc9da`)
- `jsonschema-4.26.0-py3-none-any.whl` (`sha256:d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce`)
- `jsonschema_specifications-2025.9.1-py3-none-any.whl` (`sha256:98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe`)
- `referencing-0.37.0-py3-none-any.whl` (`sha256:381329a9f99628c9069361716891d34ad94af76e461dcb0335825aecc7692231`)
- `rpds_py-2026.6.3-cp314-cp314-macosx_10_12_x86_64.whl` (`sha256:931908d9fc855d8f74783377822be318edb6dcb19e47169dc038f9a1bf60b06e`)
```

## src/autopulse/data/validator.py (changed schema-loader section only)

```python
"""Frame validation and read-only diagnostic service filtering."""

from __future__ import annotations

import json
import math
from importlib.resources import files
import time
from typing import Any

from autopulse.debugging import get_logger, log_event
from jsonschema import Draft7Validator, FormatChecker


LOGGER = get_logger(__name__)
_SCHEMA_PACKAGE = "autopulse.schemas"

ICE_PROTOCOLS = frozenset({"SAE_J1979", "SAE_J1979-2"})
EV_PROTOCOLS = frozenset(
    {"SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"}
)

RESTRICTED_SERVICE_IDS = frozenset(
    {
        int("08", 16),  # J1979: Request Control of On-Board System
        int("31", 16),  # UDS: RoutineControl
        int("04", 16),  # J1979: Clear / Reset Diagnostic Information
        int("14", 16),  # UDS: ClearDiagnosticInformation
        int("2E", 16),  # UDS: WriteDataByIdentifier
        int("10", 16),  # UDS: DiagnosticSessionControl
        int("27", 16),  # UDS: SecurityAccess
        int("2F", 16),  # UDS: InputOutputControlByIdentifier
    }
)

_RED_LINE_SERVICES = frozenset({0x2E, 0x31, 0x10, 0x27, 0x2F})
_HIGH_SEVERITY_SERVICES = frozenset({0x14})
_ALLOWED_DTC_SUBFUNCTIONS = frozenset({0x02, 0x06})
_DEFAULT_SESSION = 0x01
_TESTER_PRESENT_MIN_INTERVAL_SECONDS = 4.0


class SecurityViolationRedLine(Exception):
    """Raised when a blocked CAN service ID is intercepted."""

    def __init__(self, service_id: int):
        self.service_id = service_id
        super().__init__(
            "SECURITY_VIOLATION_RED_LINE: Restricted Service ID "
            f"0x{service_id:02X} was intercepted and blocked."
        )


class RoutingError(ValueError):
    """Raised when a shared-envelope frame cannot be safely routed."""


class CommandBlockedException(Exception):
    """Raised when an unsafe diagnostic service or sub-function is blocked."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _load_packaged_schema(filename: str) -> dict[str, Any]:
    """Load one immutable schema resource from the installed package."""
    resource = files(_SCHEMA_PACKAGE).joinpath(filename)
    with resource.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    if not isinstance(schema, dict):
        raise TypeError(f"Packaged schema {filename!r} must contain an object.")
    return schema


def load_engine_obd_frame_schema() -> dict[str, Any]:
    """Load the strict US-001 engine OBD-II frame packaged resource."""
    return _load_packaged_schema("engine_obd_frame.schema.json")


def load_ev_obd_frame_schema() -> dict[str, Any]:
    """Load the strict US-006 EV telemetry frame packaged resource."""
    return _load_packaged_schema("ev_obd_frame.schema.json")


ENGINE_OBD_FRAME_SCHEMA = load_engine_obd_frame_schema()
ENGINE_OBD_FRAME_VALIDATOR = Draft7Validator(
    ENGINE_OBD_FRAME_SCHEMA,
    format_checker=FormatChecker(),
)
EV_OBD_FRAME_SCHEMA = load_ev_obd_frame_schema()
EV_OBD_FRAME_VALIDATOR = Draft7Validator(
    EV_OBD_FRAME_SCHEMA,
    format_checker=FormatChecker(),
)


def validate_frame(frame: dict[str, Any]) -> None:
    """Validate an engine OBD-II frame against the US-001 JSON schema."""
    _validate_finite_numbers(frame)
    ENGINE_OBD_FRAME_VALIDATOR.validate(frame)
    log_event(
        LOGGER,
        10,
        "frame_validated",
```


