# Claude Adversarial Planning Prompt: US-006 EV Telemetry Data Contract

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Your task is to review the US-006 EV telemetry specification and produce an adversarial QA plan before Codex implements anything.

## Current Project Context

AutoPulse is an educational, read-only OBD-II anomaly detection framework. Existing completed work:

- US-001: strict combustion-engine data contract with `additionalProperties: false`
- US-002: deterministic replay harness with dirty-data injection
- US-003: anomaly scoring for HDF/OSF and statistical drift
- US-004: Median(3) to EWMA smoothing to reduce alert flicker
- US-005: JSON-LD alert serialization with hashed VINs and finite RFC 8259-safe numbers

US-006 proposes EV telemetry support through a new parallel EV schema using a shared metadata envelope. It must not mutate or weaken US-001.

## Project Tech Stack And Layout

Assume you cannot inspect the repository. Use this stack summary when proposing tests and implementation guidance.

Runtime and test stack:

- Language: Python
- Test runner: pytest
- Schema validation: JSON Schema via the `jsonschema` Python package
- Data utilities already available: `pandas`, `numpy`
- Documentation site: Starlight/Astro under a separate `grubby-galaxy/` directory

Current repository layout:

- `schemas/engine_obd_frame.schema.json`: current US-001 combustion-engine JSON Schema.
- `src/autopulse/data/validator.py`: current schema validation entry point.
- `src/autopulse/adapters.py`: adapter/security boundary for diagnostic reads.
- `src/autopulse/replayer.py`: replay harness code.
- `src/autopulse/noise.py`: dirty-data/noise injection utilities.
- `tests/simulation/virtual_replay.py`: simulation test support.
- `src/autopulse/analysis/`: HDF/OSF, smoothing, rolling-window, and PdM processor logic.
- `src/autopulse/alert_exporter.py`: JSON-LD alert serialization from US-005.
- Existing tests live in `tests/` and use direct pytest assertions.

Known existing test files:

- `tests/test_engine_data_contract.py`
- `tests/test_us002_virtual_replay_harness.py`
- `tests/test_us003_pdm_algorithms.py`
- `tests/test_us004_smoothing.py`
- `tests/test_us005_alert_exporter.py`

Likely US-006 implementation locations for Codex:

- new EV schema under `schemas/`
- EV routing or validator additions in `src/autopulse/data/validator.py`
- adapter read-service filtering in `src/autopulse/adapters.py`
- EV replay/noise additions in `src/autopulse/replayer.py`, `src/autopulse/noise.py`, or `tests/simulation/virtual_replay.py`
- optional future analysis logic under `src/autopulse/analysis/`
- alert serialization extensions in `src/autopulse/alert_exporter.py`

When proposing QA artifacts, prefer concrete pytest file names such as:

- `tests/test_us006_ev_data_contract.py`
- `tests/test_us006_schema_routing.py`
- `tests/test_us006_ev_adapter_security.py`
- `tests/test_us006_ev_replay_harness.py`
- `tests/test_us006_ev_alert_exporter.py`

## Proposed US-006 Architecture

Recommended validation strategy:

- shared envelope with timestamp, hashed VIN, protocol identity, powertrain type, and payload
- isolated US-001 validator for ICE payloads
- isolated US-006 validator for EV payloads
- strict `additionalProperties: false` inside each payload
- routing based on envelope metadata

Proposed EV fields:

| Field | Units | Type | Range | Required |
| --- | --- | --- | --- | --- |
| `battery_soh` | percent | number | `0.0 <= x <= 100.0` | yes |
| `battery_soce` | percent | number | `0.0 <= x <= 100.0` | yes |
| `battery_temp_avg` | Celsius | number | `-40.0 <= x <= 80.0` | yes |
| `traction_motor_speed` | RPM | integer | `-20000 <= x <= 20000` | no |
| `battery_throughput` | Ah | number | `0.0 <= x <= 500000.0` | no |
| `grid_energy_in` | kWh | number | `0.0 <= x <= 1000000.0` | no |

Security red lines:

- no ECU write commands
- no actuator control
- no DTC clearing unless explicitly approved by a human after audit
- no security-access or seed-key flows
- no raw VIN storage
- standard passive polling capped at 1 Hz
- replay-only burst mode must be test-scoped if accepted
- no non-finite numbers in JSON-LD

UDS service assumptions from Gemini research:

- allowed candidate: `0x22` Read Data by Identifier
- allowed candidate: `0x19` Read DTC Information for ZEV DTC reads only
- allowed candidate: `0x3E` Tester Present for passive session keepalive only
- forbidden: `0x2E`, `0x2F`, `0x31`, `0x14`

Treat these assumptions as claims to audit, not facts to trust blindly.

## Your Required Output

Produce a Markdown QA plan with these sections:

1. Audit verdict on the proposed schema strategy.
2. Security red lines, ranked by severity.
3. Positive test scenarios.
4. Negative and adversarial test scenarios.
5. Boundary-value matrix for every proposed EV field.
6. Cross-schema isolation tests proving US-006 cannot weaken US-001.
7. Adapter-level forbidden-service tests.
8. Replay harness dirty-data scenarios.
9. JSON-LD alert serialization tests.
10. Specific implementation guidance for Codex, including proposed test file names.
11. Open questions or blockers that must be resolved before implementation.

## Specific Attacks To Consider

- EV payload containing legacy ICE fields such as `coolant_temp` or `stft_bank1`
- ICE payload containing EV fields such as `battery_soh`
- malformed envelope routing that sends EV payloads to the ICE validator
- `powertrain_type` spoofing
- DoCAN versus DoIP protocol identity ambiguity
- forbidden UDS service injection: `0x2E`, `0x2F`, `0x31`, `0x14`
- security-access or seed-key negotiation attempts
- `TesterPresent` misuse to keep unauthorized sessions alive
- raw VIN leakage through envelope, validation error, logs, or JSON-LD output
- non-finite values: `NaN`, `Infinity`, `-Infinity`
- rapid but range-valid SOH or SOCE oscillation
- required field dropout
- optional field type confusion
- replay-only 10 Hz burst mode escaping into production/passive monitoring

## Open Questions To Challenge

- Should AutoPulse categorically forbid UDS service `0x14` Clear DTC even if ZEVonUDS permits it under certain conditions?
- Should draft or unevenly supported parameters such as time-of-use, V2X discharge, and certified energy consumption stay out of US-006?
- Should the adapter abort on a CAN-to-Ethernet diagnostic transition instead of attempting automatic discovery?
- Should `traction_motor_speed` remain optional unless a generic passenger-vehicle mapping is available?
- Are the proposed EV-HDF and EV-OSF formulas testable now, or should US-006 stop at schema and replay validation?

Do not write implementation code. This is an adversarial planning handoff for Codex.
