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
