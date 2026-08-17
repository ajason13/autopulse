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
import shutil

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
    target_python = args.target_python
    if not target_python.is_absolute():
        resolved = shutil.which(str(target_python))
        if resolved is None:
            parser.error("--target-python must name an executable on PATH or an absolute path")
        target_python = Path(resolved)
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
            str(target_python),
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
            str(target_python),
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
