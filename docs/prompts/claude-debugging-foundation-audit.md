# Claude Audit Prompt: Debugging Support Foundation

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

## Stage

Implementation audit before merge.

## Scope

Codex added the first debugging layer for AutoPulse. Review for privacy leakage, security red-line regressions, and missing adversarial tests.

## Project Constraints

AutoPulse is an educational, read-only OBD-II / EV telemetry validation and anomaly detection framework.

Security red lines:

- Never store, log, serialize, or expose a raw VIN.
- Preserve only `vin_hashed` for audit correlation.
- Never log raw diagnostic payload bytes, seed-key material, tokens, or secrets.
- Never weaken read-only UDS/OBD guardrails.
- Block write/control/session-escalation services and keep EV burst mode test-scoped.
- Debugging must not alter schema validation, routing, replay, adapter guardrail, or alert serialization behavior.

## Implementation Summary

Codex changed:

- `src/autopulse/debugging.py`
  - Adds `sanitize_debug_value()`, `log_event()`, and `get_logger()`.
  - Redacts raw VIN-like strings and sensitive key names such as `raw_vin`, `vin`, `payload_bytes`, `seed`, `key`, `token`, and `secret`.
  - Preserves `vin_hashed` unless the value itself looks like a raw VIN.

- `src/autopulse/data/validator.py`
  - Adds structured debug/security events around frame validation, routing rejection, UDS service blocking, protocol transition blocking, tester-present rate limiting, speculative DTC probing, and undocumented negative motor-speed sign convention.

- `tests/simulation/virtual_replay.py`
  - Adds structured replay events for adapter connect/disconnect, accepted ICE/EV frames, replay start/stop, replay frame errors, EV sequence replay, burst-mode violations, and security violations.

- `src/autopulse/alert_exporter.py`
  - Adds structured debug events when ICE and EV alert payloads are serialized.

- `src/autopulse/debug.py`
  - Adds `python -m autopulse.debug` with:
    - `validate-frame --powertrain ICE|EV|ROUTED`
    - `replay-ev --jsonl`
    - `--verbose` for DEBUG logs
  - Outputs sanitized JSON summaries and omits raw validation messages for JSON Schema failures.

- `tests/test_debugging.py`
  - Tests redaction of raw VINs and payload bytes.
  - Tests structured logging output.
  - Tests security blocking logs omit raw payloads.
  - Tests CLI schema-error output is sanitized.

- `README.md` and `CONTEXT.md`
  - Document debugging commands, safety rules, and deferred future debugging work.

## Verification

Codex ran:

- `python3 -m pytest tests/test_debugging.py -q` -> `4 passed`
- `python3 -m pytest tests/test_debugging.py tests/test_us006_ev_adapter_security.py tests/test_us006_ev_replay_harness.py tests/test_us006_ev_alert_exporter.py tests/test_us006_schema_routing.py -q` -> `63 passed`
- `python3 -m pytest -q` -> `535 passed`
- CLI smoke success:
  - `PYTHONPATH=src python3 -m autopulse.debug validate-frame --powertrain EV --json '<valid EV frame>'` -> `{"ok": true, "powertrain_type": "EV"}`
- CLI smoke rejection:
  - raw-VIN EV frame -> sanitized JSON error with no raw VIN or payload bytes

## Requested Review

Return:

1. PASS/FAIL verdict for merge readiness.
2. Blocker findings, ordered by severity.
3. Non-blocking recommendations.
4. Missing adversarial tests, especially privacy/security tests.
5. Explicit confirmation whether Claude sign-off is required before merge and whether this implementation is ready for that sign-off.

Do not propose any change that logs raw VINs, raw diagnostic payload bytes, seed-key material, tokens, or private workspace data.
