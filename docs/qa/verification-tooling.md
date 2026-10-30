# Maintained verification tooling

## Legacy workflow retirement

Issue [#135](https://github.com/ajason13/autopulse/issues/135) removes
`scripts/verification_reporter.py` and `scripts/redline_scanner.py`.
Inspection of tracked source, tests, workflows, packaging configuration, and
documentation found only one caller: the reporter invoked the scanner.
Neither script was a required CI or release gate. No supported legacy entry
point remains.

The reporter ignored child exit codes, read an obsolete active-context path,
and embedded raw Git diffs and test output in generated Markdown. Its scanner
matched text patterns without establishing protocol safety. Removal avoids
presenting these outputs as successful verification.

The two `verification_report_2026-05-18_*.md` files in this directory are
historical snapshots. Their recorded scanner output and unsigned checklists
do not establish current test, security, or review status. Preserve their
original contents as history; do not regenerate them.

## Current checks

Follow [development setup](../../CONTRIBUTING.md#development-setup) first.
Run checks directly from the repository root and use their exit status:

```sh
./.venv/bin/python -m pytest tests/packaging -q
./.venv/bin/python -m pytest -q
```

In native PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/packaging -q
.\.venv\Scripts\python.exe -m pytest -q
```

For feature changes, also use the focused tests described in
[CONTRIBUTING.md](../../CONTRIBUTING.md#verification). A failed command remains
a failed check; a generated document or successful later command cannot
replace its result.

[CI](../../.github/workflows/ci.yml) defines the required release-cell
sequence: independent builds, wheel and sdist comparisons with
`scripts/packaging_policy.py compare`, installed-package checks with
`scripts/verify_release_cell.py`, supply-chain evidence, and the full Python
suite. Use that workflow for exact arguments and prerequisites, and the
[offline package guide](../offline-package.md) for the distribution boundary.
The retirement changes none of these gates or runtime guards.

`scripts/emit_ci_summary.py` formats approved fields from release-cell
evidence after successful checks in CI. It does not run tests or independently
establish that a check passed. Keep its allowlist and the existing CI failure
handling intact.

Record commands, exit status, tested commit, and concise results in the issue
or PR. Review and sanitize any evidence before sharing; do not automatically
publish raw diffs or logs. Keep session checkpoints under the Git directory
as directed by `AGENTS.md`.
