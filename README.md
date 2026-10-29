# AutoPulse

An educational, read-only OBD-II anomaly detection framework that learns a vehicle's healthy fingerprint and flags data drift before DTCs appear.

## Project Vitals

- Mission: Detect statistical drift in read-only OBD-II telemetry before diagnostic trouble codes appear.
- Governance: See [AGENTS.md](AGENTS.md) for current repository constraints and verification.
- Codex sessions: [Start, continue, and troubleshoot](docs/codex-sessions.md).
- Primary domains: OBD-II ingestion, virtual replay, statistical anomaly scoring, and adversarial validation.

## Repository Layout

- `src/autopulse/data/`: OBD-II ingestion and validation.
- `tests/simulation/`: Virtual replay harness.
- `src/autopulse/analysis/`: Statistical anomaly scoring.
- `schemas/`: JSON data contracts.
- `tests/`: Adversarial test suites.
- `docs/`: Technical design documents.

## Python Development

Use CPython **3.13 or 3.14** (`>=3.13,<3.15` in `pyproject.toml`). Follow
[Getting Started](grubby-galaxy/src/content/docs/guides/getting-started.md)
for Unix and native Windows PowerShell setup, an installed CLI example, and
verification commands. [CONTRIBUTING.md](CONTRIBUTING.md) describes the test gates.

Install the local package before using it: this repository uses a `src/` layout.
Runtime requirements alone do not install AutoPulse or its CLI. Source development
uses online dependency installation; disconnected wheelhouse installation is
documented separately in [the offline package guide](docs/offline-package.md).

## Debugging

AutoPulse debug output is sanitized by default. Debug helpers preserve `vin_hashed` for audit correlation but redact raw VIN-like strings, payload bytes, tokens, keys, and other sensitive fields.

Validate one frame from the command line:

```sh
./.venv/bin/autopulse-debug validate-frame --powertrain EV --file frame.json
```

Replay EV JSONL rows through the read-only replay path:

```sh
./.venv/bin/autopulse-debug replay-ev --jsonl ev_rows.jsonl
```

Enable structured DEBUG logs when troubleshooting validation, routing, replay, adapter guardrails, or alert serialization:

```sh
./.venv/bin/autopulse-debug --verbose validate-frame --powertrain EV --file frame.json
./.venv/bin/python -m pytest tests/test_us006_ev_adapter_security.py -q -vv --tb=short --log-cli-level=DEBUG
./.venv/bin/python -m pytest tests/test_debugging.py -q -vv --tb=short
```

These Unix examples assume you supply local input files. In PowerShell, use
`.\.venv\Scripts\autopulse-debug.exe` and `.\.venv\Scripts\python.exe`
instead; Getting Started includes a complete synthetic example.

Do not add raw VINs, raw diagnostic payload bytes, seed-key material, tokens, or private workspace links to debug fixtures or logs.

## Documentation Site

AutoPulse uses a Starlight-based documentation site for specifications and guides.

To run the docs locally:

```sh
cd grubby-galaxy
nvm use
npm install
npm run dev
```

See [grubby-galaxy/README.md](grubby-galaxy/README.md) for full setup and build details.
