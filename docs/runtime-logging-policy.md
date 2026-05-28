# AutoPulse Runtime Logging Policy

AutoPulse runtime logging exists to support replay debugging, future live-capture triage, and auditability without weakening the read-only diagnostic boundary.

This policy applies to `autopulse.debugging.log_event()` and `autopulse.logging_config.configure_logging()`.

## Logging Model

Runtime events that carry vehicle, diagnostic, replay, guard, or alert context must be emitted as structured JSON through `log_event()`.

Plain text `INFO` messages are allowed only for startup or configuration state that does not include vehicle data, frame data, adapter payloads, exception messages, guard context, or alert payloads.

## Logger Scope

All runtime handlers are attached to the `autopulse` logger or its children. AutoPulse must not configure the root logger.

`configure_logging()`:

- sets the `autopulse` logger level;
- disables propagation from `autopulse` to root;
- adds a console handler only when requested;
- adds a file handler only when an explicit path is provided;
- reuses existing AutoPulse runtime/debug CLI handlers instead of duplicating them.

Console logging writes to `stderr`. CLI JSON command output remains on `stdout`.

## Event Payload Rules

Allowed structured fields include:

- `event`
- `row_index`
- `error_type`
- `event_code`
- `service_id`
- validated `vin_hashed` only when traceability requires it

Forbidden fields or values include:

- raw VINs;
- raw diagnostic payload bytes;
- seed/key/security access material;
- tokens or secrets;
- raw exception messages from validation or adapter paths;
- tracebacks or `exc_info` content;
- rejected frame content;
- non-finite numbers such as `NaN`, `Infinity`, and `-Infinity`.

`log_event()` sanitizes fields before serialization, validates `vin_hashed` shape before preserving it, rejects non-finite numbers, and serializes with `allow_nan=False`.

## File Logging

File logging is opt-in.

Callers must pass an explicit `file_path`; AutoPulse does not create `logs/autopulse.log` or any other default file. Parent directories must already exist unless the caller passes `create_parents=True`.

File handlers use UTF-8 and append mode. Rotation is intentionally deferred. Any future rotation support must define max size, backup count, retention behavior, and whether backups are compressed before implementation.

## Event Taxonomy

Current and planned event families:

- `validation_*`: schema or physics validation outcomes; use `row_index` and `error_type`, not raw exception text.
- `replay_*`: replay lifecycle and row-level accepted/rejected counts; avoid frame payloads.
- `guard_*` / `security_*`: read-only guard events; use safe event codes and service IDs only.
- `alert_*`: alert preview or export events; include `vin_hashed` only after shape validation.
- `adapter_*`: connect/disconnect/lifecycle events; do not include payload bytes or raw adapter frames.
- `live_capture_*`: reserved for a future read-only smoke harness after separate QA planning.

## Live Vehicle Boundary

This logging layer does not authorize live polling, road testing, write-capable services, or new OBD/UDS access. Real-vehicle work remains deferred until a separate stationary read-only smoke harness, PID allowlist, runtime stop behavior, and operator checklist are reviewed.
