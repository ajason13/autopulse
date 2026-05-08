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

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Verification

Before requesting review, run the relevant test gates:

```bash
python -m pytest tests/test_engine_data_contract.py -q
python -m pytest tests/test_us002_virtual_replay_harness.py -q
```

For broad changes, run the full test suite:

```bash
python -m pytest -q
```

## Pull Requests

Pull requests should include:

- Summary of the change.
- Safety or data-contract impact.
- Tests run and results.
- Any known limitations or follow-up work.

Material changes require auditor review before merge to `main`.
