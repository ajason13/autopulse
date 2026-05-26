# AutoPulse

An educational, read-only OBD-II anomaly detection framework that learns a vehicle's healthy fingerprint and flags data drift before DTCs appear.

## Project Vitals

- Mission: Detect statistical drift in read-only OBD-II telemetry before diagnostic trouble codes appear.
- Governance: See [AGENTS.md](AGENTS.md) for the 2026 Multi-LLM engineering model and merge handshake.
- Notion: [AutoPulse Project Hub](https://www.notion.so/353834a0c8a680cfaab3dd2750ff730d)
- Primary domains: OBD-II ingestion, virtual replay, statistical anomaly scoring, and adversarial validation.

## Repository Layout

- `src/autopulse/data/`: OBD-II ingestion and validation.
- `tests/simulation/`: Virtual replay harness.
- `src/autopulse/analysis/`: Statistical anomaly scoring.
- `schemas/`: JSON data contracts.
- `tests/`: Adversarial test suites.
- `docs/`: Technical design documents.

## Debugging

AutoPulse debug output is sanitized by default. Debug helpers preserve `vin_hashed` for audit correlation but redact raw VIN-like strings, payload bytes, tokens, keys, and other sensitive fields.

Validate one frame from the command line:

```sh
PYTHONPATH=src python3 -m autopulse.debug validate-frame --powertrain EV --file frame.json
PYTHONPATH=src python3 -m autopulse.debug validate-frame --powertrain ROUTED --json '{"powertrain_type":"EV"}'
```

Replay EV JSONL rows through the read-only replay path:

```sh
PYTHONPATH=src python3 -m autopulse.debug replay-ev --jsonl ev_rows.jsonl
```

Enable structured DEBUG logs when troubleshooting validation, routing, replay, adapter guardrails, or alert serialization:

```sh
PYTHONPATH=src python3 -m autopulse.debug --verbose validate-frame --powertrain EV --file frame.json
pytest tests/test_us006_ev_adapter_security.py -q -vv --tb=short --log-cli-level=DEBUG
pytest tests/test_debugging.py -q -vv --tb=short
```

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
