# Adversarial QA Plan: Real Vehicle Read-Only Smoke Harness

Auditor: Claude Sonnet 4.6

Date: 2026-05-28

Branch: `vehicle-smoke-harness-planning`

## Verdict

Proceed with conditions.

Runtime Logging Hardening is merged via PR #32. The draft spec and safety constraints are sound, but the completed live harness still requires a second Claude review before any real vehicle connection.

## Blockers Resolved Into Implementation Constraints

- Live code must not use `src/autopulse/adapters.py`, `providers.py`, `replayer.py`, or `tests.simulation` replay classes.
- First harness must not read VIN. It must require operator-supplied precomputed `vin_hashed`.
- Live adapter must call `command_filter()` before every outgoing request.
- Poll cadence must be enforced in code with a monotonic clock and minimum one-second cycle.
- Unsupported protocol must fail closed without additional negotiation.
- Vehicle speed greater than zero is a safety abort.
- A finite sample or duration limit is required; no unlimited default.
- Adapter exception text must never be logged raw.
- Operator preflight must be runtime-enforced through flags/checks, not documentation only.

## Required Initial Scope

- ICE-only stationary smoke harness.
- Mandatory `--vin-hashed`, `--adapter-port`, and `--output-path`.
- Mandatory `--max-samples` or `--max-duration-seconds`.
- Runtime preflight confirmation before opening the adapter.
- `--dry-run` mode that validates arguments and exits without opening hardware.
- Accepted samples conform to `schemas/engine_obd_frame.schema.json`.
- JSONL output contains accepted frames only.
- Logs use `autopulse.logging_config.configure_logging()` and `autopulse.debugging.log_event()`.

## Required Tests

- Security: attempted services `0x2E`, `0x31`, `0x10`, `0x27`, `0x2F`, `0x08`, and `0x04` are blocked before transmission.
- Privacy: raw VIN and raw payload byte-like content do not appear in logs or JSONL under failure paths.
- Safety: speed greater than zero disconnects and returns safety-abort exit code.
- Cadence: polling loop enforces at least one second per cycle.
- CLI: missing required args fail before adapter open; dry-run does not open adapter.
- Output: valid accepted frames write replay-compatible JSONL; partial/invalid frames increment rejection counters and are not written.
- Adapter failures: open/fetch/disconnect failures are summarized without raw exception text.

## Go/No-Go

Current status: No-Go for real vehicle.

Go conditions:

- `src/autopulse/live/` implementation exists and does not import `tests.*`.
- Required tests pass.
- Operator checklist/preflight is runtime-enforced.
- Claude performs a second implementation audit and returns safe-to-proceed for stationary vehicle smoke test.
