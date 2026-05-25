---
name: autopulse-obd-schema-security
description: Use when changing AutoPulse OBD-II/UDS schemas, validators, adapters, replay harnesses, noise injectors, alert exporters, or tests that enforce read-only diagnostic security and telemetry data contracts.
metadata:
  short-description: Enforce AutoPulse OBD security
---

# AutoPulse OBD Schema Security

Use this skill for security-sensitive AutoPulse code under `schemas/`, `src/autopulse/data/`, adapters, replay/noise utilities, alert exporters, and related tests.

## Non-Negotiable Rules

- AutoPulse is read-only. No writes, clears, controls, routines, security access, or session escalation.
- `additionalProperties: false` is a security boundary, not a style preference.
- Raw VIN must never be stored, logged, serialized, or included in validation errors.
- JSON output must be RFC 8259-safe: reject or sanitize NaN, Infinity, and `-Infinity`.
- Unknown protocol or powertrain combinations must fail closed.
- Schema changes require adversarial tests and existing-contract regression tests.

## UDS Red Lines

Block at adapter/guard level:

- `0x2E` WriteDataByIdentifier
- `0x2F` InputOutputControlByIdentifier
- `0x31` RoutineControl
- `0x14` ClearDiagnosticInformation unless a future approved human workflow explicitly allows it
- `0x27` SecurityAccess
- `0x10` non-default DiagnosticSessionControl

Restrict:

- `0x3E` TesterPresent: rate-limited and never used to sustain non-default sessions.
- `0x19`: only approved passive sub-functions, no speculative DTC probing.
- Protocol transitions: abort and log unless a future approved configuration allows discovery.

## Schema Review Checklist

- Required fields are explicit.
- Numeric bounds are physically defensible, not only protocol-maximum artifacts.
- Unit and source descriptions are clear enough to prevent semantic drift.
- Optional fields are truly optional and have documented absence behavior.
- ICE and EV payload fields do not collide accidentally.
- Protocol enums are disjoint where routing depends on them.

## Test Expectations

Include focused tests for:

- Positive nominal frames.
- Boundary values at min/max and just outside.
- Missing required fields.
- Additional/foreign fields.
- Non-finite numbers.
- Raw VIN leakage.
- Protocol/powertrain mismatch.
- Security-service blocking.
- Replay dirty-data behavior.
- Existing story regression tests.
