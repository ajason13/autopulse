# Codex Implementation Handoff: US-006 EV Telemetry Data Contract

You are Codex/GPT-5.5 acting as AutoPulse Lead Developer.

Implement US-006 only after reading:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/specs/us-006-ev-telemetry-data-contract.md`
- `docs/prompts/claude-adversarial-planning-us006-ev-integration.md`

Claude has given a conditional pass for implementation after the four final corrections are incorporated. This prompt is the implementation handoff.

## Scope

Implement:

- EV JSON Schema validation
- shared-envelope routing and cross-schema isolation
- adapter guardrails for read-only UDS behavior
- EV replay harness and dirty-data injection
- JSON-LD safety checks for EV validation/security events

Do not implement:

- EV-HDF
- EV-OSF
- EV anomaly scoring under `src/autopulse/analysis/`
- time-of-use
- V2X discharge tracking
- certified energy consumption
- automatic DoCAN-to-DoIP discovery

## Mandatory Schema Decisions

Create `schemas/ev_obd_frame.schema.json` as a standalone Draft-07 schema.

US-006 EV protocol enum:

```json
["SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"]
```

Patch the existing ICE schema protocol enum in `schemas/engine_obd_frame.schema.json` to canonical:

```json
["SAE_J1979", "SAE_J1979-2"]
```

If existing replay inputs use underscore aliases such as `SAE_J1979_2`, keep compatibility at the replay/adapter normalization layer, but schema output must use the canonical hyphenated value.

EV field table:

| Field | Units | Type | Range | Required | Required description behavior |
| --- | --- | --- | --- | --- | --- |
| `battery_soh` | percent | number | `0.0 <= x <= 100.0` | yes | Battery state of health. |
| `battery_soce` | percent | number | `0.0 <= x <= 100.0` | yes | ZEVonUDS State of Certified Energy, not SOC; adapter source documentation required. |
| `battery_temp_avg` | Celsius | number | `-40.0 <= x <= 80.0` | yes | Physics-based EV battery thermal guardrail. |
| `traction_motor_speed` | RPM | integer | `-20000 <= x <= 20000` | no | Optional; negative only with documented sign convention. |
| `battery_throughput` | Ah | number | `0.0 <= x <= 500000.0` | no | Cumulative lifetime Ah throughput; negative values are not permitted; not net/signed throughput. |
| `grid_energy_in` | kWh | number | `0.0 <= x <= 1000000.0` | no | Lifetime charging-energy ceiling. |

All numeric fields must reject `NaN`, `Infinity`, and `-Infinity`.

## Mandatory UDS Policy

| Service | Sub-function | Policy |
| --- | --- | --- |
| `0x22` ReadDataByIdentifier | EV DIDs only | allowed |
| `0x19` ReadDTCInformation | `0x02`, `0x06` only | allowed with constraint |
| `0x3E` TesterPresent | passive keepalive | max once per 4 seconds; DefaultSession only |
| `0x10` DiagnosticSessionControl | `0x01` only | DefaultSession only |
| `0x10` DiagnosticSessionControl | non-`0x01` | forbidden |
| `0x14` ClearDiagnosticInformation | any | forbidden |
| `0x27` SecurityAccess | any | forbidden |
| `0x2E` WriteDataByIdentifier | any | forbidden |
| `0x2F` InputOutputControlByIdentifier | any | forbidden |
| `0x31` RoutineControl | any | forbidden |

`0x19/0x06` may only request DTC numbers previously observed through passive `0x19/0x02`. Speculative DTC iteration must log `SPECULATIVE_DTC_PROBE`.

If a live session transitions between DoCAN and DoIP, abort and log; do not auto-discover or renegotiate.

## Required Test Files

Create or update:

- `tests/test_us006_ev_data_contract.py`
- `tests/test_us006_schema_routing.py`
- `tests/test_us006_ev_adapter_security.py`
- `tests/test_us006_ev_replay_harness.py`
- `tests/test_us006_ev_alert_exporter.py`

Also preserve:

- `tests/test_engine_data_contract.py`

## Required Test IDs

Implement the Claude test inventory:

- POS-001 through POS-012
- NEG-001 through NEG-023
- full boundary matrix for all six EV fields
- ISO-001 through ISO-012
- SEC-001 through SEC-019
- RPL-001 through RPL-012
- ALS-001 through ALS-010

New final re-review additions:

- `ISO-011`: ICE and EV protocol enums are disjoint.
- `ISO-012`: `protocol: "SAE_J1979-3"` with `powertrain_type: "ICE"` rejects at envelope/routing layer before payload validation.
- `SEC-018`: negative `traction_motor_speed` from a source with no registered sign convention rejects or flags `SIGN_CONVENTION_UNDOCUMENTED`.
- `SEC-019`: `0x19/0x06` for a DTC not previously observed via `0x19/0x02` logs `SPECULATIVE_DTC_PROBE`.

## Verification

Run targeted tests first:

```bash
python3 -m pytest tests/test_engine_data_contract.py tests/test_us006_ev_data_contract.py tests/test_us006_schema_routing.py tests/test_us006_ev_adapter_security.py tests/test_us006_ev_replay_harness.py tests/test_us006_ev_alert_exporter.py
```

Then run the full suite:

```bash
python3 -m pytest -q
```

Record exact command output in the implementation summary.
