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
