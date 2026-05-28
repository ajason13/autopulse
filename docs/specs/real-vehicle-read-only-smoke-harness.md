# Real Vehicle Read-Only Smoke Harness

Status: Draft for Claude adversarial QA planning.

## Purpose

Define the minimum safe bridge from offline replay tooling to a first stationary vehicle check.

This story does not authorize road testing, unattended monitoring, write-capable services, active discovery, or production-grade adapter support. It exists to prove that AutoPulse can open a supported OBD-II adapter, poll a tiny allowlist of read-only signals at a conservative cadence, validate frames through existing schemas, and persist sanitized replay-compatible JSONL.

## Preconditions

- Runtime Logging Hardening is merged and Claude-approved.
- A Claude-reviewed adversarial QA plan exists for this story.
- The implementation has source-level live adapter boundaries; it must not depend on `tests.simulation` replay classes for live behavior.
- Operator checklist exists before any vehicle connection.
- The first vehicle check is stationary only.

## Safety Contract

- Read-only only.
- No DTC clearing.
- No UDS writes.
- No routines.
- No InputOutputControl.
- No SecurityAccess.
- No non-default diagnostic session.
- No TesterPresent keepalive for sustaining sessions.
- No active service discovery.
- No protocol renegotiation after connection.
- No road testing.
- No unattended operation.

Any attempted write/control/clear/routine/security/session-escalation behavior is a P0 violation.

## Initial Harness Shape

The expected implementation should be a narrow CLI or module that:

- accepts an explicit adapter/port argument;
- accepts an explicit output JSONL path;
- accepts an optional runtime log path;
- defaults to console status on `stderr` and structured result output on `stdout`;
- polls at max 1 Hz;
- enforces a small sample limit and/or duration limit;
- exits cleanly on operator interrupt;
- emits sanitized runtime events through `autopulse.logging_config.configure_logging()` and `autopulse.debugging.log_event()`;
- validates each normalized frame through existing schema validators;
- writes one sanitized replay-compatible JSON object per accepted sample.

## Candidate ICE PID Allowlist

Initial stationary ICE smoke capture should use only SAE J1979 Mode 01 current-data PIDs already represented by the US-001 schema:

- `0x04`: calculated engine load
- `0x05`: engine coolant temperature
- `0x0C`: engine RPM
- `0x0D`: vehicle speed
- `0x06`: short term fuel trim bank 1
- `0x07`: long term fuel trim bank 1

Optional future PID:

- `0x46`: ambient air temperature, only if adapter support is explicit and absence is handled without failing the capture.

The first implementation may be ICE-only. EV live capture should remain out of scope unless Claude and the project owner explicitly approve a separate EV-safe DID allowlist and source documentation requirement.

## Output Contract

Accepted ICE samples should conform to `schemas/engine_obd_frame.schema.json`.

Output must:

- include `vin_hashed` only;
- never include raw VIN;
- never include raw adapter payload bytes;
- never include seed/key/security material;
- never include unsupported or additional schema fields;
- be RFC 8259-safe;
- be replay-compatible with existing `replay-ice` tooling.

Rejected samples may increment counters and produce sanitized runtime log events, but must not be serialized as raw rejected-frame content.

## Failure Behavior

The harness should fail closed on:

- adapter open failure;
- no ECU response;
- unsupported protocol;
- missing required allowlist PID;
- schema validation failure above an explicit threshold;
- non-finite numeric values;
- any write-capable service request;
- raw VIN exposure attempt.

Operator interrupt should stop polling, close the adapter, flush logs/output, and return a sanitized summary.

## Explicit Non-Goals

- Road tests.
- Continuous monitoring.
- VIN read/storage.
- DTC scanning beyond pre-approved passive read-only behavior.
- DTC clearing.
- UDS active diagnostics.
- EV DID polling.
- Anomaly scoring changes.
- Production fleet support.
- Adapter auto-discovery beyond an explicit user-provided port.

## Open Questions For Claude

- Should the first smoke harness require all six ICE PIDs per sample, or allow partial samples with rejection counters?
- Should vehicle speed be required to remain `0` for stationary safety, or merely logged/validated?
- Should the harness hash a user-supplied VIN, reject VIN reads entirely, or require the user to provide a precomputed `vin_hashed`?
- Which adapter library is acceptable for the first implementation, and how should tests fake it without touching hardware?
- Should adapter configuration live under `src/autopulse/live/`, `src/autopulse/adapters/`, or another package to avoid the current `tests.simulation` dependency?
