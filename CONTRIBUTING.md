# Contributing to AutoPulse

AutoPulse is a read-only OBD-II telemetry and predictive maintenance project.
Contributions should preserve the repository governance model in `AGENTS.md`.

## Ground Rules

- Keep OBD-II behavior read-only.
- Treat `schemas/` as the source of truth for data contracts.
- Add or update tests for behavior changes.
- Keep changes focused on one user story or defect at a time.
- Do not commit secrets, VINs, private vehicle data, or proprietary logs.

## Development Setup

Use CPython **3.13 or 3.14**. Follow the
[Getting Started setup](grubby-galaxy/src/content/docs/guides/getting-started.md)
from the repository root, including its native PowerShell path for Windows.
It installs the editable local package, pytest, and the release tools needed
by the full suite (including `uv` for the lockfile contract). Activation and
`PYTHONPATH` overrides are unnecessary.

Runtime-only installation and focused-test installation are smaller options,
but the full suite also needs `requirements-release.txt`. The guide explains
the dependency files and extras; these source-development commands are
separate from disconnected installation.

## Verification

The legacy generated-report/scanner workflow has been retired. See
[maintained verification commands](docs/qa/verification-tooling.md) for the
replacement checks and the limits of historical reports.

Before requesting review, run the relevant test gates:

```bash
./.venv/bin/python -m pytest tests/test_engine_data_contract.py -q
./.venv/bin/python -m pytest tests/test_us002_virtual_replay_harness.py -q
```

For broad changes, run the full test suite:

```bash
./.venv/bin/python -m pytest -q
```

In native PowerShell, run the same gates with the selected environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_engine_data_contract.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_us002_virtual_replay_harness.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

## Pull Requests

Pull requests should include:

- Summary of the change.
- Safety or data-contract impact.
- Tests run and results.
- Any known limitations or follow-up work.

Material changes require auditor review before merge to `main`.
