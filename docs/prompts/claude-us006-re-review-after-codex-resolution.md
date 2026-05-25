# Claude Re-Review Prompt: US-006 EV Telemetry Resolution

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Codex has addressed your US-006 adversarial feedback at the architecture/specification level. No implementation code has been written. Please re-review the resolved US-006 contract and either approve it for Codex implementation handoff or identify remaining blockers.

## What Changed After Your Feedback

Codex accepted the conservative defaults you recommended:

- `battery_temp_avg` maximum changed from `215.0` C to `80.0` C.
- `battery_throughput` changed from signed protocol-sized range to cumulative non-negative `0.0 <= x <= 500000.0` Ah.
- `grid_energy_in` maximum changed from `429496729.5` kWh to `1000000.0` kWh.
- EV protocol enum narrowed to:
  - `SAE_J1979-3`
  - `ISO_15765_4_DoCAN`
  - `ISO_13400_DoIP`
- Legacy `SAE_J1979` and `SAE_J1979-2` are excluded from EV payloads unless a later standards review proves they are valid for EV frames.
- `0x14` ClearDiagnosticInformation remains categorically forbidden.
- `0x10` is allowed only for DefaultSession `0x01`; all other diagnostic sessions are forbidden.
- `0x27` SecurityAccess is forbidden.
- `0x19` is restricted to passive read sub-functions `0x02` and `0x06`.
- `0x3E` TesterPresent is rate-limited to at most once per 4 seconds and is forbidden outside DefaultSession.
- DoCAN-to-DoIP transition behavior is abort-and-log, with no automatic discovery.
- `traction_motor_speed` remains optional; negative RPM is allowed only when the adapter source defines negative values as reverse rotation using a documented OEM or standards sign convention.
- EV-HDF and EV-OSF formulas are explicitly out of scope for US-006.
- Time-of-use, V2X discharge, and certified energy consumption are explicitly out of scope for US-006.

## Resolved US-006 Implementation Scope

US-006 should implement only:

- EV schema validation
- shared-envelope routing and cross-schema isolation
- adapter guardrails for read-only UDS behavior
- EV replay harness and dirty-data injection
- JSON-LD safety checks for EV validation/security events

US-006 should not implement:

- EV-HDF
- EV-OSF
- EV anomaly scoring under `src/autopulse/analysis/`
- time-of-use
- V2X discharge tracking
- certified energy consumption
- automatic protocol discovery between DoCAN and DoIP

## Final Field Table For Re-Review

| Field | Units | Type | Range | Required | Notes |
| --- | --- | --- | --- | --- | --- |
| `battery_soh` | percent | number | `0.0 <= x <= 100.0` | yes | Battery state of health. |
| `battery_soce` | percent | number | `0.0 <= x <= 100.0` | yes | State of certified energy. |
| `battery_temp_avg` | Celsius | number | `-40.0 <= x <= 80.0` | yes | Physics-based EV battery thermal guardrail. |
| `traction_motor_speed` | RPM | integer | `-20000 <= x <= 20000` | no | Optional; signed only with documented source sign convention. |
| `battery_throughput` | Ah | number | `0.0 <= x <= 500000.0` | no | Cumulative lifetime throughput; not signed net throughput. |
| `grid_energy_in` | kWh | number | `0.0 <= x <= 1000000.0` | no | Generous lifetime charging-energy ceiling. |

All numeric fields must reject `NaN`, `Infinity`, and `-Infinity`.

## Final UDS Policy For Re-Review

| Service | Sub-function | Policy |
| --- | --- | --- |
| `0x22` ReadDataByIdentifier | EV DIDs only | allowed |
| `0x19` ReadDTCInformation | `0x02`, `0x06` only | allowed |
| `0x3E` TesterPresent | passive keepalive | constrained: max once per 4 seconds; DefaultSession only |
| `0x10` DiagnosticSessionControl | `0x01` only | constrained: DefaultSession only |
| `0x10` DiagnosticSessionControl | non-`0x01` | forbidden |
| `0x14` ClearDiagnosticInformation | any | forbidden |
| `0x27` SecurityAccess | any | forbidden |
| `0x2E` WriteDataByIdentifier | any | forbidden |
| `0x2F` InputOutputControlByIdentifier | any | forbidden |
| `0x31` RoutineControl | any | forbidden |

## Requested Claude Output

Please return:

1. Pass/fail verdict on whether these resolutions are sufficient for Codex implementation handoff.
2. Any remaining blockers that still must be resolved before coding.
3. Final test file list and test IDs Codex must implement.
4. Any corrections to field bounds, protocol enum, or UDS policy.
5. Explicit confirmation that EV anomaly analysis is out of scope for US-006.

Do not write implementation code. This is a final adversarial re-review before Codex implementation handoff.
