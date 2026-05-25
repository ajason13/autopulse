---
title: US-006 EV Telemetry Data Contract
description: Strict read-only EV telemetry schema, routing, replay, and adapter safety contract for AutoPulse.
---

US-006 adds electric-vehicle telemetry support without weakening the existing US-001 combustion-engine contract. EV frames use a separate schema and a shared envelope so ICE and EV validation paths remain isolated.

## Scope

US-006 implements:

- EV JSON Schema validation
- shared-envelope routing and cross-schema isolation
- read-only UDS adapter guardrails
- EV replay harness and dirty-data injection
- JSON-LD safety checks for EV validation and security events

US-006 does not implement EV anomaly scoring. EV-HDF, EV-OSF, time-of-use, V2X discharge tracking, certified energy consumption, and automatic DoCAN-to-DoIP discovery are deferred to future stories.

## Protocols

EV frames accept only:

```json
["SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"]
```

The ICE schema remains separate and accepts only `SAE_J1979` and `SAE_J1979-2`. The enum sets are intentionally disjoint, and protocol/powertrain mismatches are rejected at the routing layer before payload validation.

## EV Payload Fields

| Field | Units | Type | Range | Required | Notes |
| --- | --- | --- | --- | --- | --- |
| `battery_soh` | percent | number | `0.0` to `100.0` | yes | Battery state of health. |
| `battery_soce` | percent | number | `0.0` to `100.0` | yes | ZEVonUDS State of Certified Energy, not driver-facing State of Charge. |
| `battery_temp_avg` | Celsius | number | `-40.0` to `80.0` | yes | Physics-based EV pack thermal guardrail. |
| `traction_motor_speed` | RPM | integer | `-20000` to `20000` | no | Negative values require documented source sign convention. |
| `battery_throughput` | Ah | number | `0.0` to `500000.0` | no | Cumulative lifetime throughput; not net or signed throughput. |
| `grid_energy_in` | kWh | number | `0.0` to `1000000.0` | no | Lifetime charging-energy ceiling. |

All numeric values must be finite. `NaN`, `Infinity`, and `-Infinity` are rejected before serialization.

## UDS Safety Policy

| Service | Policy |
| --- | --- |
| `0x22` ReadDataByIdentifier | Allowed for EV DIDs. |
| `0x19` ReadDTCInformation | Limited to passive `0x02` and `0x06`; `0x06` may only request previously observed DTCs. |
| `0x3E` TesterPresent | DefaultSession only, rate-limited to once per 4 seconds. |
| `0x10` DiagnosticSessionControl | Only DefaultSession `0x01` is allowed. |
| `0x14`, `0x27`, `0x2E`, `0x2F`, `0x31` | Forbidden. |

If a live session changes protocol, AutoPulse aborts and logs the transition instead of attempting discovery or renegotiation.

## Verification

US-006 is covered by focused pytest suites for schema validation, routing isolation, adapter security, replay behavior, and EV JSON-LD serialization.
