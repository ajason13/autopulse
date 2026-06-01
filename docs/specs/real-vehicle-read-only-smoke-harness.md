# Real Vehicle Read-Only Smoke Harness

Status: Implemented and merged via PR #33. Claude re-review passed; stationary ICE smoke test is conditionally allowed only under the operator checklist.

## Purpose

Define the minimum safe bridge from offline replay tooling to a first stationary vehicle check.

This story does not authorize road testing, unattended monitoring, write-capable services, active discovery, or production-grade adapter support. It exists to prove that AutoPulse can open a supported OBD-II adapter, poll a tiny allowlist of read-only signals at a conservative cadence, validate frames through existing schemas, and persist sanitized replay-compatible JSONL.

## Preconditions

- Runtime Logging Hardening is merged and Claude-approved.
- Claude-reviewed adversarial QA and implementation re-review exist for this story.
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

Required CLI inputs:

- `--adapter-port`
- `--vin-hashed`
- `--output-path`
- `--max-samples` or `--max-duration-seconds`
- runtime preflight confirmation, or `--dry-run`

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

The first implementation is ICE-only. EV live capture remains out of scope unless Claude and the project owner explicitly approve a separate EV-safe DID allowlist and source documentation requirement.

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

The first implementation requires all six required ICE PIDs for an accepted sample. Partial samples are rejected and counted.

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
- vehicle speed greater than zero during stationary capture.

Operator interrupt should stop polling, close the adapter, flush logs/output, and return a sanitized summary.

Safety abort exit code is `2`. Adapter failure exit code is `3`.

## Explicit Non-Goals

- Road tests.
- Continuous monitoring.
- VIN read/storage.
- DTC scanning beyond pre-approved passive read-only behavior.
- DTC clearing.
- UDS active diagnostics.
- EV DID polling.
- VIN reads or VIN hashing from a raw VIN.
- Anomaly scoring changes.
- Production fleet support.
- Adapter auto-discovery beyond an explicit user-provided port.

## Claude QA Decisions

- Require complete six-PID samples for accepted frames.
- Abort if `vehicle_speed > 0`.
- Do not read VIN. Require a precomputed lowercase 64-character SHA-256 `vin_hashed`.
- Put live implementation under `src/autopulse/live/`.
- Use a fake adapter in tests; tests must not require hardware or import `python-obd`.
- Claude implementation audit and fix re-review passed before merge.
