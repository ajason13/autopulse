# Claude Adversarial Planning Prompt: Runtime Logging Hardening

You are Claude Sonnet 4.6 acting as the AutoPulse Lead Auditor.

## Stage

Pre-implementation adversarial QA planning for branch `logging-hardening`.

Gemini/Antigravity is temporarily unavailable, so Codex is acting as interim project/product manager for task framing. This is not a request to approve implementation code yet. Produce a QA plan and identify blockers before Codex starts the runtime logging hardening implementation.

## Project Context

AutoPulse is an educational, read-only OBD-II anomaly detection framework. Its mission is to detect statistical drift in read-only telemetry before DTCs appear.

Completed foundations:

- US-001 through US-006 are implemented and Claude-reviewed.
- The first debugging foundation added `src/autopulse/debugging.py` with:
  - `sanitize_debug_value()`
  - `log_event()`
  - `get_logger()`
- Follow-up hardening added precise VIN-key redaction, scoped verbose logging, and adversarial debug-output tests.
- Future Debugging Ergonomics merged via PR #31 and added:
  - robust `replay-ev` and `replay-ice` CLI summaries
  - `preview-alerts`
  - `inspect-guards`
  - shared `.vscode/launch.json`
  - additional privacy/security regression tests

Current decision:

- We will **not** start real-vehicle polling yet because there is no near-term vehicle access and the runtime boundary still needs hardening.
- The next task is **Runtime Logging Hardening**.
- The later task is **Real Vehicle Read-Only Smoke Harness**, deferred until logging hardening, source-level adapter boundaries, safe PID allowlist, and operator safety checklist exist.

## Non-Negotiable Security and Privacy Rules

- AutoPulse remains read-only.
- No ECU writes, clears, controls, routines, security access, diagnostic session escalation, active probing, or arbitrary adapter commands.
- Debug/runtime logs must preserve `vin_hashed` only.
- Logs must never include raw VINs, raw diagnostic payload bytes, seed-key material, tokens, secrets, private workspace links, rejected frame content, or raw exception messages that may embed rejected values.
- `guard_events` and security logging must use safe event codes and service IDs only.
- JSON log output must be RFC 8259-safe: no NaN, Infinity, or `-Infinity`.
- Root logger behavior must not be mutated unexpectedly by library imports.
- File logging must not silently create unsafe logs with sensitive payloads.

## Current Logging Surface

Current helper module:

```python
"""Safe debugging helpers for AutoPulse telemetry workflows."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Mapping


RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = frozenset(
    {
        "raw_vin",
        "payload_bytes",
        "seed",
        "key",
        "token",
        "secret",
    }
)


def get_logger(name: str) -> logging.Logger:
    """Return a module logger without configuring global handlers."""
    return logging.getLogger(name)


def sanitize_debug_value(value: Any) -> Any:
    """Return a debug-safe copy of a value.

    Raw VIN-like strings and sensitive key names are redacted. ``vin_hashed`` is
    preserved because it is the public vehicle identifier required by AutoPulse
    audit trails.
    """
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = sanitize_debug_value(item)
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(item)
        return sanitized

    if isinstance(value, list):
        return [sanitize_debug_value(item) for item in value]

    if isinstance(value, tuple):
        return [sanitize_debug_value(item) for item in value]

    if isinstance(value, str):
        return RAW_VIN_PATTERN.sub(REDACTED, value)

    return value


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured, sanitized debug event."""
    if not logger.isEnabledFor(level):
        return

    payload = {"event": event, **sanitize_debug_value(fields)}
    logger.log(level, json.dumps(payload, sort_keys=True, default=str))
```

Current debug CLI logging behavior:

- `python -m autopulse.debug --verbose ...` enables DEBUG logging on the `autopulse` logger only.
- It does not configure the root logger.
- Replay validation warnings log `error_type` and `row_index`, not rejected values.
- Guard/security logs use safe event codes/service IDs.

## Proposed Runtime Logging Hardening Scope

Codex is considering implementing:

1. **Runtime Logging Policy**
   - Define a documented event taxonomy for:
     - schema validation
     - replay accepted/rejected rows
     - guard/security events
     - alert serialization/preview
     - adapter connect/disconnect
     - future live capture start/stop/failure events
   - Define allowed and forbidden log fields.

2. **Logging Configuration Helper**
   - Add an explicit helper, likely in `src/autopulse/debugging.py`, for configuring AutoPulse logging.
   - Requirements:
     - no root logger mutation
     - idempotent handler setup
     - optional console handler
     - optional file handler under a caller-provided path
     - explicit log level
     - structured JSON output where practical
     - always sanitize values before emission

3. **File Logging Safety**
   - If file logging is added:
     - no default unsafe path
     - no automatic capture of raw frame payloads
     - parent directories should be explicit or safely created only when requested
     - file content must be sanitized and RFC 8259-safe
     - future retention/rotation expectations documented

4. **Tests**
   - Extend `tests/test_debugging.py` or create `tests/test_runtime_logging.py`.
   - Cover:
     - redaction in console and file logs
     - no root logger mutation
     - duplicate handler/idempotency behavior
     - level filtering
     - non-finite numeric rejection or safe serialization
     - raw VIN and sensitive-key redaction
     - rejected frame values absent from log output
     - interaction with existing `--verbose` CLI behavior

5. **Documentation**
   - Update `CONTEXT.md` and possibly `docs/` with:
     - runtime logging policy
     - local operator guidance
     - retention/rotation notes
     - explicit statement that live vehicle capture remains deferred

## Open Design Questions for Claude

Please evaluate these before Codex implements:

1. Should runtime logs use only JSON events, or is a mixed model acceptable for startup/configuration messages?
2. Should `log_event()` raise on non-finite numbers, or should the logging config use `json.dumps(..., allow_nan=False)` and fail closed?
3. Should file logging require an explicit path every time, or is a conventional local path such as `logs/autopulse.log` acceptable?
4. Should runtime logging include `vin_hashed` in all vehicle-related events, or only when needed for traceability?
5. Should `sanitize_debug_value()` continue preserving `vin_hashed` blindly, or should it validate the value shape when logging runtime events?
6. Should file handlers use rotation now, or should rotation be documented as future work?
7. Should logging configuration belong in `autopulse.debugging`, or should it be promoted to a new `autopulse.logging`/`autopulse.observability` module to avoid the "debug-only" name?

## Required Output

Produce a Markdown adversarial QA plan with these sections:

1. **Audit Verdict**
   - Is the proposed logging-hardening scope safe to implement?
   - Identify any blockers or required design changes before Codex starts.

2. **Threat Model**
   - Privacy leakage paths.
   - Security boundary weakening paths.
   - Operational risks from file logging or handler configuration.

3. **Required Implementation Constraints**
   - Exact must/never rules for log fields, handlers, file output, levels, and serialization.

4. **Positive Test Scenarios**
   - Expected successful behavior for console logging, file logging, structured events, CLI verbose mode, and idempotent config.

5. **Negative and Adversarial Test Scenarios**
   - Raw VIN leakage attempts.
   - Sensitive key leakage attempts.
   - Rejected validation value leakage.
   - Non-finite numbers.
   - Duplicate handlers.
   - Root logger mutation.
   - Unsafe file path or accidental log creation.
   - Guard/security event pollution.

6. **Recommended Test Structure**
   - Test file placement and naming.
   - `caplog`/tmp_path patterns.
   - Assertions to prefer and assertions to avoid.

7. **Open Questions / Blockers**
   - Decisions that must be resolved before Codex implements.

8. **Sign-Off Language**
   - State whether Codex is approved to begin implementation after addressing any blockers.

Do not write implementation code. This is a pre-implementation adversarial planning handoff for Runtime Logging Hardening.
