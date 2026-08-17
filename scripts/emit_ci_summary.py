#!/usr/bin/env python3
"""Emit a CI summary from explicitly approved, non-sensitive fields only."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ALLOWED = re.compile(
    r"^- (?:"
    r"Cell: `cp(?:313|314)-(?:linux|macos|windows)-[a-z0-9_]+`|"
    r"CPython: `3\.(?:13|14)\.\d+`|"
    r"Install: PASS \(`--no-index --require-hashes --only-binary=:all:`\)|"
    r"Registry access during install probes: DISABLED \(`--no-index` and `PIP_NO_INDEX=1`\)|"
    r"(?:Tampered-hash|Incomplete-wheelhouse) install rejection: PASS|"
    r"Built (?:wheel|sdist) archive policy \(`validate_archive\(\)`\): PASS|"
    r"Installed validator/schema resource smoke: PASS|"
    r"Installed offline CLI smoke: PASS|"
    r"`autopulse\.live` absence \(metadata and import\): PASS|"
    r"AutoPulse (?:wheel|sdist): `autopulse-[A-Za-z0-9_.-]+` \(`sha256:[0-9a-f]{64}`\)|"
    r"Wheelhouse manifest SHA-256: `[0-9a-f]{64}`|"
    r"`[A-Za-z0-9_.-]+\.whl` \(`sha256:[0-9a-f]{64}`\)"
    r")$"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("--commit must be a full lowercase SHA")
    lines = args.source.read_text(encoding="utf-8").splitlines()
    selected = [line for line in lines if ALLOWED.fullmatch(line)]
    if not selected or len(selected) != sum(line.startswith("- ") for line in lines):
        raise ValueError("CI summary source contains an unapproved field")
    args.output.write_text("# AutoPulse release-gate summary\n\n- Commit: `" + args.commit + "`\n" + "\n".join(selected) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
