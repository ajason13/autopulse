from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import tomllib


REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE = REPOSITORY / "src" / "autopulse"


def test_project_metadata_exposes_only_offline_console_script() -> None:
    metadata = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["requires-python"] == ">=3.13,<3.15"
    assert metadata["project"]["scripts"] == {"autopulse-debug": "autopulse.debug:main"}
    assert metadata["project"]["dependencies"] == ["jsonschema>=4.26.0,<5"]
    assert "release" in metadata["project"]["optional-dependencies"]


def test_build_configuration_excludes_live_package_from_both_artifacts() -> None:
    metadata = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    for target in ("sdist", "wheel"):
        excluded = metadata["tool"]["hatch"]["build"]["targets"][target]["exclude"]
        assert "/src/autopulse/live/**" in excluded


def test_committed_project_declarations_match_uv_lock() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "uv", "export", "--locked", "--all-extras", "--no-emit-project", "--format", "requirements-txt"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


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
