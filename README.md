# AutoPulse

An educational, read-only OBD-II anomaly detection framework that learns a vehicle's healthy fingerprint and flags data drift before DTCs appear.

## Project Vitals

- Mission: Detect statistical drift in read-only OBD-II telemetry before diagnostic trouble codes appear.
- Governance: See [AGENTS.md](AGENTS.md) for the 2026 Multi-LLM engineering model and merge handshake.
- Notion: [AutoPulse Project Hub](https://www.notion.so/353834a0c8a680cfaab3dd2750ff730d)
- Primary domains: OBD-II ingestion, virtual replay, statistical anomaly scoring, and adversarial validation.

## Repository Layout

- `src/data/`: OBD-II ingestion and validation.
- `src/simulation/`: Virtual replay harness.
- `src/analysis/`: Statistical anomaly scoring.
- `schemas/`: JSON data contracts.
- `tests/`: Adversarial test suites.
- `docs/`: Technical design documents.
