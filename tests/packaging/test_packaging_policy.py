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
