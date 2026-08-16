#!/usr/bin/env python3
"""Emit a CI summary from explicitly approved, non-sensitive fields only."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ALLOWED = re.compile(r"^- (?:Cell|CPython|Install|Registry access|Tampered-hash|Incomplete-wheelhouse|Built wheel|Built sdist|Installed validator|Installed offline CLI|`autopulse.live` absence|AutoPulse wheel|AutoPulse sdist|Wheelhouse manifest|`[A-Za-z0-9_.-]+\.whl`)")


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
