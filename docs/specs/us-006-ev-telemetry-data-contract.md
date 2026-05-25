# US-006 EV Telemetry Data Contract

Status: Final Claude re-review conditionally passed. Cleared for Codex implementation handoff after the four minor mandatory corrections in this spec are preserved during implementation.

## Problem

AutoPulse currently validates read-only combustion-engine OBD-II telemetry. It cannot yet ingest or validate zero-emission vehicle telemetry from high-voltage battery packs, electric drivetrains, or EV diagnostic gateways.

US-006 defines the research-backed data contract direction for electric-vehicle telemetry while preserving AutoPulse's existing safety model:

- read-only diagnostics only
- no raw VIN or PII storage
- strict schema validation with `additionalProperties: false`
- default passive polling capped at 1 Hz
- no ECU writes, actuator control, DTC clearing, security-access, calibration, or programming flows

## Standards Notes

Gemini Deep Research identified SAE J1979-3 / ZEVonUDS as the target standards family for zero-emission diagnostics. It characterized ZEVonUDS as a zero-emission subset of the broader OBDonUDS transition from legacy emissions-oriented OBD modes to UDS Data Identifier reads.

Resolved policy for Claude re-review:

- Primary read path: UDS service `0x22` Read Data by Identifier.
- DTC read path: UDS service `0x19`, restricted to passive sub-functions `0x02` reportDTCByStatusMask and `0x06` reportDTCExtDataRecordByDTCNumber.
- Session keepalive: UDS service `0x3E` Tester Present only when needed for passive capture, rate-limited to no more than once per 4 seconds, and never used to sustain a non-Default diagnostic session.
- Default diagnostic session: UDS service `0x10` sub-function `0x01` is permitted only as passive DefaultSession. All other `0x10` sub-functions are forbidden.
- Forbidden services include `0x27` SecurityAccess, `0x2E` Write Data by Identifier, `0x2F` Input/Output Control, `0x31` Routine Control, and `0x14` Clear Diagnostic Trouble Codes.
- ZEVonUDS may be exposed over DoCAN or DoIP through the J1962 connector, but regulated diagnostics should use a single active bus path at a time.
- Several parameters remain uncertain or unevenly supported, including battery time-of-use, certified energy consumption interpretation, V2X discharge tracking, and standardized passenger-vehicle traction motor speed.

If a live session appears to transition between DoCAN and DoIP, AutoPulse must abort and log the transition instead of attempting automatic discovery or renegotiation.

Time-of-use, V2X discharge tracking, and certified energy consumption are out of scope for US-006. They require a later story after standards and OEM mappings are clearer.

## Recommended Schema Strategy

Use a parallel EV schema with a shared metadata envelope.

Do not extend US-001 with optional EV fields. A monolithic schema would either loosen `additionalProperties: false` or force downstream code into broad null-checking across unrelated powertrain fields.

Do not begin with one polymorphic mega-schema. Conditional schema logic would be harder to audit and could fail open if routing logic is wrong.

The recommended shape is:

```text
shared envelope
  timestamp
  vin_hashed
  protocol_identity
  powertrain_type
  payload

US-001 ICE payload
  existing combustion fields
  additionalProperties: false

US-006 EV payload
  EV fields only
  additionalProperties: false
```

Routing should inspect the envelope and dispatch to either the immutable US-001 validator or the new US-006 validator. EV payloads must not accept legacy ICE fields such as `coolant_temp` or fuel trims.

## Protocol Enum

US-006 EV frames may use only these protocol identifiers:

```json
[
  "SAE_J1979-3",
  "ISO_15765_4_DoCAN",
  "ISO_13400_DoIP"
]
```

Legacy `SAE_J1979` and `SAE_J1979-2` values remain valid only for non-EV contracts unless a later standards review proves that an EV payload should be carried under them. Unknown protocol strings, proprietary protocol names, and protocol changes within a single active vehicle session must be rejected.

US-001's ICE schema must also define its protocol enum canonically as:

```json
[
  "SAE_J1979",
  "SAE_J1979-2"
]
```

If existing replay code accepts older underscore aliases such as `SAE_J1979_2`, those aliases must normalize to the canonical hyphenated schema value before validation. The ICE and EV protocol enum sets must remain disjoint.

## Proposed EV Fields

| Field | Source Concept | Units | Type | Range | Required | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `battery_soh` | Battery state of health | percent | number | `0.0 <= x <= 100.0` | yes | Durability metric derived from pack capacity calculations. |
| `battery_soce` | State of certified energy | percent | number | `0.0 <= x <= 100.0` | yes | ZEVonUDS State of Certified Energy, not driver-facing State of Charge. Adapter source documentation must identify the DID/source and confirm this value is not an SOC proxy. |
| `battery_temp_avg` | Average high-voltage battery temperature | Celsius | number | `-40.0 <= x <= 80.0` | yes | Physics-based EV pack thermal guardrail. The prior 215C protocol-style ceiling is rejected as an ICE coolant artifact. |
| `traction_motor_speed` | Traction motor rotational speed | RPM | integer | `-20000 <= x <= 20000` | no | Optional because passenger EV support may be proprietary or non-standard. Negative values are permitted only when the adapter source defines negative RPM as reverse rotation using a documented OEM or standards sign convention. |
| `battery_throughput` | Cumulative battery current throughput | Ah | number | `0.0 <= x <= 500000.0` | no | Cumulative lifetime Ah throughput. Negative values are not permitted; this field does not represent net or signed throughput. |
| `grid_energy_in` | Cumulative off-board grid energy | kWh | number | `0.0 <= x <= 1000000.0` | no | Generous lifetime charging-energy ceiling for fleet/commercial use. Protocol maxima above this are rejected as physically implausible. |

All numeric fields must be finite before schema validation and JSON-LD serialization. `NaN`, `Infinity`, and `-Infinity` are invalid even if an upstream parser can represent them.

## UDS Allow/Deny Matrix

| Service | Sub-function | Policy | Notes |
| --- | --- | --- | --- |
| `0x22` ReadDataByIdentifier | EV DIDs only | allowed | Primary passive telemetry path. |
| `0x19` ReadDTCInformation | `0x02`, `0x06` | allowed | Passive DTC reads only. `0x06` may only request DTCs previously observed through a passive `0x19/0x02` read; speculative DTC-number iteration is prohibited. Other sub-functions are rejected until separately reviewed. |
| `0x3E` TesterPresent | passive keepalive | constrained | Max once per 4 seconds; forbidden outside DefaultSession. |
| `0x10` DiagnosticSessionControl | `0x01` DefaultSession | constrained | Only DefaultSession is permitted. |
| `0x10` DiagnosticSessionControl | any non-`0x01` | forbidden | Blocks programming/extended/session escalation. |
| `0x14` ClearDiagnosticInformation | any | forbidden | No automated DTC clearing in AutoPulse. |
| `0x27` SecurityAccess | any | forbidden | No seed-key or unlock flow. |
| `0x2E` WriteDataByIdentifier | any | forbidden | No write access. |
| `0x2F` InputOutputControlByIdentifier | any | forbidden | No actuator override. |
| `0x31` RoutineControl | any | forbidden | No routine start/stop/results. |

## Replay Harness Implications

US-002 should gain EV replay support only after Claude signs off on the contract. Expected replay work:

- normalize EV aging traces into `battery_soh`
- normalize EV battery/motor traces into `battery_temp_avg`, `battery_soce`, and optional motor speed
- preserve standard 1 Hz passive replay
- allow a clearly test-only 10 Hz burst mode for throughput and buffer testing
- inject dirty EV frames through the existing adversarial noise model

Potential dirty-data cases:

- out-of-range `battery_temp_avg`, such as `81.0`, `250.0`, or `-100.0`
- missing required EV fields
- extra ICE-only fields inside EV payloads
- rapid but range-valid SOH oscillation, such as `95 -> 15 -> 95`
- forbidden UDS service injection, such as `0x2E` or `0x14`
- non-finite values flowing toward JSON-LD alert export
- negative `traction_motor_speed` from a source with no registered sign convention
- speculative `0x19/0x06` DTC reads for DTCs not previously observed through `0x19/0x02`

## US-006 Scope Boundary

US-006 implementation scope is limited to:

- EV schema validation
- envelope routing and cross-schema isolation
- adapter guardrails for read-only UDS behavior
- EV replay harness and dirty-data injection
- JSON-LD safety checks for EV validation/security events

EV anomaly scoring is explicitly out of scope for US-006. Gemini's draft EV-HDF and EV-OSF formulas are not implementation-ready because the thresholds, required fields, and expected distributions are not yet supported by enough physics or OEM evidence.

Future EV anomaly analysis should be handled in a separate story after US-006 schema/replay safety is verified.

## Acceptance Criteria For Implementation

- US-001 and US-006 validation paths remain isolated.
- EV frames route only to the US-006 schema.
- ICE frames route only to the US-001 schema.
- US-001 protocol enum is patched to canonical `SAE_J1979` and `SAE_J1979-2`, with any underscore replay aliases normalized before schema validation.
- ICE and EV protocol enums are disjoint.
- Protocol and powertrain mismatches are rejected at the envelope/routing layer before either payload validator runs.
- EV payloads enforce `additionalProperties: false`.
- Forbidden UDS services are blocked before transmission or downstream parsing.
- Security-access and seed-key flows are never requested.
- `0x19/0x06` is limited to DTC numbers passively observed through `0x19/0x02`.
- Negative `traction_motor_speed` is rejected or flagged with `SIGN_CONVENTION_UNDOCUMENTED` when source sign convention is missing.
- Standard passive polling remains capped at 1 Hz.
- Replay-only burst mode, if implemented, is explicitly test-scoped.
- Raw VINs are never stored or serialized.
- JSON-LD numeric output remains RFC 8259-safe and finite.
- EV-HDF and EV-OSF analysis are not implemented in US-006.

## Resolved Claude Blockers

- `0x14` ClearDiagnosticInformation is categorically forbidden for US-006. Any future maintenance workflow requires a separate human-approved story.
- `battery_temp_avg` uses `80.0` C as the initial physics-based maximum.
- `battery_throughput` uses a cumulative non-negative range of `0.0 <= x <= 500000.0` Ah.
- `grid_energy_in` uses `0.0 <= x <= 1000000.0` kWh.
- DoCAN-to-DoIP transitions abort and log; no automatic discovery.
- `traction_motor_speed` remains optional and signed only with documented source convention.
- EV-HDF and EV-OSF are deferred out of US-006 scope.
- Time-of-use, V2X discharge, and certified energy consumption are deferred out of US-006 scope.

## Final Claude Mandatory Corrections

Claude's final re-review returned a conditional pass. These minor corrections are mandatory for Codex implementation:

- EV schema descriptions must state that `battery_throughput` is cumulative, non-negative, and not net/signed throughput.
- EV schema descriptions must define `battery_soce` as ZEVonUDS State of Certified Energy, distinguish it from SOC, and require adapter source documentation.
- Adapter tests must cover undocumented negative `traction_motor_speed` sign convention as `SEC-018`.
- Protocol enum work must use Option B: independent ICE and EV schema enums. Patch ICE protocol enum to `["SAE_J1979", "SAE_J1979-2"]`; define EV enum as `["SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"]`; add disjoint enum and protocol/powertrain mismatch tests.

## Final Test Additions From Claude

- `ISO-011`: confirm ICE and EV protocol enums are disjoint sets.
- `ISO-012`: submit `protocol: "SAE_J1979-3"` with `powertrain_type: "ICE"`; router rejects as an envelope-level protocol/powertrain mismatch before payload validation.
- `SEC-018`: submit `traction_motor_speed = -5000` from an adapter source with no registered sign convention; adapter rejects or flags `SIGN_CONVENTION_UNDOCUMENTED`.
- `SEC-019`: call `0x19/0x06` with a DTC number not previously observed through `0x19/0x02`; adapter logs `SPECULATIVE_DTC_PROBE`.
