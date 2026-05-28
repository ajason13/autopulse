# Claude Prompt: Real Vehicle Read-Only Smoke Harness Adversarial QA Plan

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Stage: pre-implementation adversarial QA planning.

Branch: `vehicle-smoke-harness-planning`

Gemini/Antigravity is temporarily unavailable, so Codex is acting as interim project/product manager. This is not a request to approve implementation code. Produce an adversarial QA plan and identify blockers before Codex implements any live-vehicle code.

## Objective

Challenge the proposed **Real Vehicle Read-Only Smoke Harness** story.

The goal is the minimum safe bridge from replay-only AutoPulse tooling to a first stationary vehicle check. The harness should open a supported OBD-II adapter, poll a tiny read-only allowlist at max 1 Hz, validate normalized samples through existing schemas, log safely through the new runtime logging layer, and persist replay-compatible sanitized JSONL.

The project owner may not have vehicle access immediately, but this story should make the eventual first connection safer.

## Required Auditor Output

Return:

1. Verdict: safe to proceed, proceed with conditions, or do not proceed.
2. Blockers/open questions that must be resolved before implementation.
3. Threat model: vehicle safety, privacy, logging, adapter, protocol, and operator risks.
4. Positive test scenarios.
5. Negative/adversarial test scenarios.
6. Recommended test files, fixtures, and naming.
7. Required implementation constraints.
8. Explicit go/no-go recommendation for eventual real-vehicle connection after implementation.

Severity-rank blockers. Be concrete and adversarial.

## Non-Negotiable Security Red Lines

- AutoPulse is read-only.
- No DTC clearing.
- No UDS writes.
- No routines.
- No InputOutputControl.
- No SecurityAccess.
- No non-default diagnostic session.
- No TesterPresent keepalive to sustain sessions.
- No active service discovery.
- No protocol renegotiation after connection.
- No road testing.
- No unattended operation.
- No raw VIN storage or logging.
- No raw diagnostic payload byte storage or logging.

Any write/control/clear/routine/security/session escalation path is a P0 issue.

## Proposed Scope

The expected implementation should be a narrow source-level module/CLI that:

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

Initial implementation should be ICE-only unless you explicitly approve an EV-safe DID allowlist and documentation requirement.

Candidate ICE PID allowlist:

- `0x04`: calculated engine load
- `0x05`: engine coolant temperature
- `0x0C`: engine RPM
- `0x0D`: vehicle speed
- `0x06`: short term fuel trim bank 1
- `0x07`: long term fuel trim bank 1

Optional future PID:

- `0x46`: ambient air temperature, only if adapter support is explicit and absence is handled without failing capture.

## Specific Questions For Claude

1. Should the first harness require all six ICE PIDs per sample, or allow partial samples with rejection counters?
2. Should vehicle speed be required to remain `0` for stationary safety, or only validated/logged?
3. Should the harness ever read VIN and hash it, or should it reject VIN reads entirely and require a user-provided precomputed `vin_hashed`?
4. Which adapter abstraction should Codex implement first, and how should tests fake it without hardware?
5. Should live adapter code live under `src/autopulse/live/`, `src/autopulse/adapters/`, or another package?
6. Is the current source/test separation acceptable for live work, given that `src/autopulse/adapters.py`, `providers.py`, and `replayer.py` currently re-export from `tests.simulation`?
7. What exact operator checklist is required before first vehicle connection?
8. What evidence would be sufficient to say “safe to try stationary vehicle smoke test”?

## Current Project State

`CONTEXT.md` says:

```markdown
## Current Epic
**Runtime Hardening & Observability**
*   **Status:** QA planning.
*   **Active Story:** **Real Vehicle Read-Only Smoke Harness** - define a stationary, read-only, operator-safe first-vehicle check.

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Debugging Safety:** Debug logs and CLI output must preserve `vin_hashed` only; raw VINs, raw diagnostic payload bytes, seed-key material, tokens, and private workspace links must be redacted or omitted.
*   **Live Vehicle Boundary:** Do not start real-vehicle polling or road tests until a read-only smoke harness, runtime logging policy, safe PID allowlist, and operator safety checklist exist.

## Active Work: Real Vehicle Read-Only Smoke Harness
*   **Goal:** Prepare the minimum safe bridge from replay-only tooling to a first stationary vehicle check.
*   **Current status:** Draft spec exists in `docs/specs/real-vehicle-read-only-smoke-harness.md`; Claude adversarial QA planning prompt is being prepared on branch `vehicle-smoke-harness-planning`.
*   **Required scope before any vehicle connection:**
    *   Define a stationary-only read-only harness with no write-capable UDS services and no clearing/resetting/coding behavior.
    *   Use a strict safe PID allowlist, max 1 Hz polling, explicit sample limits, and operator stop/failure behavior.
    *   Persist only replay-compatible sanitized JSONL; do not store raw VINs or raw diagnostic payload bytes.
    *   Route runtime events through `autopulse.logging_config.configure_logging()` and `log_event()`.
    *   Add adapter-open failure handling, unsupported-protocol behavior, and no-vehicle/no-ECU negative tests.
    *   Add an operator checklist covering stationary setup, ignition state, battery condition, adapter selection, and stop conditions.
*   **Architecture constraint:** Live vehicle code must live in a source package with a clear adapter boundary. Do not reuse `tests.simulation` replay classes as the live adapter implementation.
*   **Draft decision:** First smoke harness should be ICE-only unless Claude identifies a safe EV-specific DID allowlist and source-documentation requirement.
*   **Out of scope for this task:** road testing, unattended monitoring, write-capable services, performance claims, production-grade adapter support, and new anomaly algorithms.
```

## Draft Spec

`docs/specs/real-vehicle-read-only-smoke-harness.md`:

```markdown
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
```

## Relevant Existing Code And Contracts

### `src/autopulse/adapters.py`

This is currently only a compatibility export from test replay classes. Live code should not use this as-is.

```python
"""Compatibility exports for replay adapter imports."""

from tests.simulation.virtual_replay import (
    DataPacket,
    EVDataPacket,
    EVMockAdapter,
    MockAdapter,
    OBDAdapter,
)

__all__ = ["DataPacket", "EVDataPacket", "EVMockAdapter", "MockAdapter", "OBDAdapter"]
```

### `src/autopulse/providers.py`

Also currently re-exports test replay providers.

```python
"""Compatibility exports for replay log providers and parsers."""

from tests.simulation.virtual_replay import (
    AI4IParser,
    CSVProvider,
    CandidParser,
    JSONLProvider,
    LogProvider,
)

__all__ = [
    "AI4IParser",
    "CSVProvider",
    "CandidParser",
    "JSONLProvider",
    "LogProvider",
]
```

### `src/autopulse/replayer.py`

Also currently re-exports test replay timing.

```python
"""Compatibility exports for replay timing."""

from tests.simulation.virtual_replay import LogReplayer, ReplayMode, replay_ev_sequence

__all__ = ["LogReplayer", "ReplayMode", "replay_ev_sequence"]
```

### `src/autopulse/data/validator.py` key constants and guardrails

```python
ICE_PROTOCOLS = frozenset({"SAE_J1979", "SAE_J1979-2"})
EV_PROTOCOLS = frozenset(
    {"SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"}
)

RESTRICTED_SERVICE_IDS = frozenset(
    {
        int("08", 16),  # J1979: Request Control of On-Board System
        int("31", 16),  # UDS: RoutineControl
        int("04", 16),  # J1979: Clear / Reset Diagnostic Information
        int("14", 16),  # UDS: ClearDiagnosticInformation
        int("2E", 16),  # UDS: WriteDataByIdentifier
        int("10", 16),  # UDS: DiagnosticSessionControl
        int("27", 16),  # UDS: SecurityAccess
        int("2F", 16),  # UDS: InputOutputControlByIdentifier
    }
)

_RED_LINE_SERVICES = frozenset({0x2E, 0x31, 0x10, 0x27, 0x2F})
_HIGH_SEVERITY_SERVICES = frozenset({0x14})
_ALLOWED_DTC_SUBFUNCTIONS = frozenset({0x02, 0x06})
_DEFAULT_SESSION = 0x01
_TESTER_PRESENT_MIN_INTERVAL_SECONDS = 4.0
```

```python
def validate_frame(frame: dict[str, Any]) -> None:
    """Validate an engine OBD-II frame against the US-001 JSON schema."""
    _validate_finite_numbers(frame)
    ENGINE_OBD_FRAME_VALIDATOR.validate(frame)
    log_event(
        LOGGER,
        10,
        "frame_validated",
        powertrain_type="ICE",
        protocol=frame.get("protocol"),
        vin_hashed=frame.get("vin_hashed"),
    )
```

```python
def command_filter(service_id: int) -> None:
    """Block restricted write/control diagnostic services before CAN transmit."""
    if service_id in RESTRICTED_SERVICE_IDS:
        log_event(
            LOGGER,
            40,
            "security_service_blocked",
            service_id=f"0x{service_id:02X}",
            severity="red_line",
        )
        raise SecurityViolationRedLine(service_id)
```

```python
class UDSCommandGuard:
    """Stateful read-only UDS policy gate for US-006 adapter behavior."""

    def validate(
        self,
        service_id: int | str,
        sub_function: int | str | None = None,
        *,
        dtc: str | None = None,
        now: float | None = None,
    ) -> None:
        """Validate a UDS command against AutoPulse read-only guardrails."""
        service = _parse_hex_or_int(service_id)
        subfn = None if sub_function is None else _parse_hex_or_int(sub_function)

        if service == 0x22:
            return

        if service == 0x19:
            self._validate_read_dtc(subfn, dtc)
            return

        if service == 0x3E:
            self._validate_tester_present(now)
            return

        if service == 0x10:
            self._validate_diagnostic_session(subfn)
            return

        if service in _RED_LINE_SERVICES:
            self._block("SECURITY_VIOLATION_RED_LINE", service, subfn)

        if service in _HIGH_SEVERITY_SERVICES:
            self._block("SECURITY_VIOLATION_HIGH", service, subfn)

        command_filter(service)
```

```python
    def _validate_read_dtc(self, subfn: int | None, dtc: str | None) -> None:
        if subfn not in _ALLOWED_DTC_SUBFUNCTIONS:
            self._block("SECURITY_VIOLATION_HIGH", 0x19, subfn)

        if subfn == 0x06 and (dtc is None or str(dtc) not in self.observed_dtcs):
            self.events.append("SPECULATIVE_DTC_PROBE")
            log_event(
                LOGGER,
                30,
                "speculative_dtc_probe_blocked",
                service_id="0x19",
                sub_function="0x06",
            )
            raise CommandBlockedException(
                "SPECULATIVE_DTC_PROBE",
                "0x19/0x06 requires a previously observed DTC.",
            )

    def _validate_tester_present(self, now: float | None) -> None:
        if self.current_session != _DEFAULT_SESSION:
            self._block("SECURITY_VIOLATION_RED_LINE", 0x3E, None)

        current_time = time.monotonic() if now is None else float(now)
        if (
            self.last_tester_present_at is not None
            and current_time - self.last_tester_present_at
            < _TESTER_PRESENT_MIN_INTERVAL_SECONDS
        ):
            self.events.append("TESTER_PRESENT_RATE_LIMIT")
            log_event(
                LOGGER,
                30,
                "tester_present_rate_limited",
                service_id="0x3E",
                min_interval_seconds=_TESTER_PRESENT_MIN_INTERVAL_SECONDS,
            )
            raise CommandBlockedException(
                "TESTER_PRESENT_RATE_LIMIT",
                "TesterPresent is limited to once per 4 seconds.",
            )
        self.last_tester_present_at = current_time

    def _validate_diagnostic_session(self, subfn: int | None) -> None:
        if subfn == _DEFAULT_SESSION:
            self.current_session = _DEFAULT_SESSION
            return
        self._block("SECURITY_VIOLATION_RED_LINE", 0x10, subfn)
```

### Schema summary

`schemas/engine_obd_frame.schema.json`:

```text
required = [
  "timestamp", "vin_hashed", "protocol", "engine_rpm", "vehicle_speed",
  "coolant_temp", "engine_load", "stft_bank1", "ltft_bank1"
]
additionalProperties = false
vin_hashed pattern = ^[a-f0-9]{64}$
protocol enum = ["SAE_J1979", "SAE_J1979-2"]
engine_rpm min/max = 0.0 / 9500.0
vehicle_speed min/max = 0 / 255
coolant_temp min/max = -40.0 / 140.0
ambient_temp optional min/max = -40.0 / 80.0
engine_load min/max = 0.0 / 100.0
stft_bank1 min/max = -50.0 / 50.0
ltft_bank1 min/max = -50.0 / 50.0
```

`schemas/ev_obd_frame.schema.json`:

```text
required = ["timestamp", "vin_hashed", "protocol", "powertrain_type", "payload"]
additionalProperties = false
vin_hashed pattern = ^[a-f0-9]{64}$
protocol enum = ["SAE_J1979-3", "ISO_15765_4_DoCAN", "ISO_13400_DoIP"]
powertrain_type enum = ["EV"]
payload additionalProperties = false
payload required = ["battery_soh", "battery_soce", "battery_temp_avg"]
battery_soh min/max = 0.0 / 100.0
battery_soce min/max = 0.0 / 100.0
battery_temp_avg min/max = -40.0 / 80.0
traction_motor_speed optional min/max = -20000 / 20000
battery_throughput optional min/max = 0.0 / 500000.0
grid_energy_in optional min/max = 0.0 / 1000000.0
```

### Runtime logging policy

`docs/runtime-logging-policy.md`:

```markdown
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
```

### `src/autopulse/debugging.py`

```python
RAW_VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
VIN_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
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

def sanitize_debug_value(value: Any, *, validate_vin_shape: bool = False) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_lower = key_text.lower()
            if key_lower == "vin_hashed":
                sanitized[key_text] = _sanitize_vin_hash(
                    item,
                    validate_vin_shape=validate_vin_shape,
                )
                continue
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[key_text] = REDACTED
                continue
            sanitized[key_text] = sanitize_debug_value(
                item,
                validate_vin_shape=validate_vin_shape,
            )
        return sanitized

    if isinstance(value, list):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            sanitize_debug_value(item, validate_vin_shape=validate_vin_shape)
            for item in value
        ]

    if isinstance(value, str):
        return RAW_VIN_PATTERN.sub(REDACTED, value)

    return value

def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    if not logger.isEnabledFor(level):
        return

    payload = {
        "event": event,
        **sanitize_debug_value(fields, validate_vin_shape=True),
    }
    _validate_finite_numbers(payload)
    logger.log(level, json.dumps(payload, allow_nan=False, sort_keys=True))
```

### `src/autopulse/logging_config.py`

```python
def configure_logging(
    *,
    level: int = logging.INFO,
    console: bool = True,
    file_path: Path | str | None = None,
    create_parents: bool = False,
) -> logging.Logger:
    """Configure AutoPulse runtime logging without mutating the root logger.

    File logging is opt-in and requires an explicit path. Parent directories are
    only created when the caller explicitly requests it.
    """
    logger = logging.getLogger(AUTOPULSE_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if console:
        _ensure_console_handler(logger, level)

    if file_path is not None:
        _ensure_file_handler(
            logger,
            Path(file_path),
            level,
            create_parents=create_parents,
        )

    return logger
```

### Existing debug CLI replay behavior

`src/autopulse/debug.py` has robust offline replay commands but no live capture command:

```python
def _replay_rows(
    powertrain_type: str,
    rows: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    adapter = (
        EVMockAdapter(JSONLProvider(rows))
        if powertrain_type == "EV"
        else MockAdapter(JSONLProvider(rows))
    )
    total_rows = 0
    accepted_frames = 0
    rejected_frames = 0
    security_violations = 0
    guard_events: list[str] = []

    adapter.connect()
    try:
        while True:
            try:
                adapter.fetch_frame()
                total_rows += 1
                accepted_frames += 1
            except StopIteration:
                break
            except SecurityViolationError as exc:
                total_rows += 1
                ...
            except (ValidationError, ValueError, TypeError) as exc:
                total_rows += 1
                rejected_frames += 1
                _log_validation_rejection(exc, total_rows)
    finally:
        adapter.disconnect()

    return {
        "ok": True,
        "powertrain_type": powertrain_type,
        "total_rows": total_rows,
        "accepted_frames": accepted_frames,
        "rejected_frames": rejected_frames,
        "security_violations": security_violations,
        "guard_events": _safe_guard_events(guard_events),
        "mode": mode,
    }
```

```python
def _write_json(payload: Any) -> None:
    print(json.dumps(sanitize_debug_value(payload), allow_nan=False, sort_keys=True))
```

### Existing replay adapter behavior for reference only

`tests/simulation/virtual_replay.py` contains replay adapters and should not become the live adapter implementation. Relevant parts:

```python
class OBDAdapter(ABC):
    """Minimal read-only OBD adapter interface used by replay drivers."""

    @abstractmethod
    def fetch_frame(self) -> "DataPacket":
        """Fetch the next normalized engine data frame."""
```

```python
US001_BOUNDS: dict[str, tuple[float, float]] = {
    "engine_rpm": (0.0, 9500.0),
    "vehicle_speed": (0.0, 255.0),
    "coolant_temp": (-40.0, 140.0),
    "engine_load": (0.0, 100.0),
    "stft_bank1": (-50.0, 50.0),
    "ltft_bank1": (-50.0, 50.0),
}

PROTOCOL_ALIASES = {
    "SAE_J1979": "SAE_J1979",
    "SAE_J1979_2": "SAE_J1979-2",
    "SAE_J1979-2": "SAE_J1979-2",
    "J1979_MODE01": "SAE_J1979",
    "J1979_2_SERVICE22": "SAE_J1979-2",
}
```

```python
class MockAdapter(OBDAdapter):
    """Stateful replay adapter that replaces a physical ELM327 adapter."""

    def connect(self) -> None:
        self._connected = True
        log_event(LOGGER, logging.DEBUG, "adapter_connected", adapter="MockAdapter")

    def disconnect(self) -> None:
        self._connected = False
        log_event(LOGGER, logging.DEBUG, "adapter_disconnected", adapter="MockAdapter")

    def fetch_frame(self) -> DataPacket:
        if not self._connected:
            raise RuntimeError("Adapter not connected. Call connect() first.")
        raw = self._next_row()
        self._enforce_security(raw)
        packet = self._normalize(raw)
        log_event(
            LOGGER,
            logging.DEBUG,
            "replay_frame_accepted",
            adapter="MockAdapter",
            powertrain_type="ICE",
            protocol=packet.protocol,
            vin_hashed=packet.vin_hashed,
        )
        return packet
```

```python
    def _enforce_security(self, row: dict[str, Any]) -> None:
        service_id = row.get("__service_id__")
        if service_id is None:
            return
        service_value = self._parse_service_id(service_id)
        try:
            command_filter(service_value)
        except Exception as exc:
            formatted = f"0x{service_value:02X}"
            self._security_violations.append(formatted)
            log_event(
                LOGGER,
                logging.ERROR,
                "replay_security_violation",
                adapter="MockAdapter",
                service_id=formatted,
            )
            raise SecurityViolationError(
                "SECURITY_VIOLATION_RED_LINE: restricted service "
                f"{formatted}"
            ) from exc
```

### Existing security tests

`tests/test_us006_ev_adapter_security.py` covers UDS red lines:

```python
@pytest.mark.parametrize(
    "case_id,service_id,sub_function,expected_code",
    [
        ("SEC-001", "0x2E", None, "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-002", "0x31", "0x01", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-003", "0x31", "0x02", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-004", "0x2F", None, "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-005", "0x10", "0x02", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-006", "0x10", "0x03", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-008", "0x14", None, "SECURITY_VIOLATION_HIGH"),
        ("SEC-009", "0x27", "0x01", "SECURITY_VIOLATION_RED_LINE"),
        ("SEC-010", "0x27", "0x02", "SECURITY_VIOLATION_RED_LINE"),
    ],
)
def test_forbidden_services_blocked(case_id, service_id, sub_function, expected_code):
    guard = UDSCommandGuard()
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate(service_id, sub_function)
    assert exc.value.code == expected_code

def test_sec_011_tester_present_rate_limited():
    guard = UDSCommandGuard()
    guard.validate("0x3E", now=10.0)
    with pytest.raises(CommandBlockedException) as exc:
        guard.validate("0x3E", now=12.0)
    assert exc.value.code == "TESTER_PRESENT_RATE_LIMIT"

def test_sec_013_read_data_by_identifier_permitted():
    UDSCommandGuard().validate("0x22")

def test_sec_014_read_dtc_status_mask_permitted():
    UDSCommandGuard().validate("0x19", "0x02")

def test_sec_015_unapproved_dtc_subfunction_rejected():
    with pytest.raises(CommandBlockedException) as exc:
        UDSCommandGuard().validate("0x19", "0x04")
    assert exc.value.code == "SECURITY_VIOLATION_HIGH"
```

### Existing runtime logging tests

`tests/test_runtime_logging.py` covers no root mutation, explicit file logging, redaction, disabled levels, and no default file output:

```python
def test_configure_logging_adds_console_handler_without_root_mutation() -> None:
    root_logger = logging.getLogger()
    root_level = root_logger.level
    root_handlers = list(root_logger.handlers)

    logger = configure_logging(level=logging.DEBUG, console=True)

    assert logger is logging.getLogger("autopulse")
    assert logger.level == logging.DEBUG
    assert logging.getLogger().level == root_level
    assert logging.getLogger().handlers == root_handlers
    assert len(runtime_handlers()) == 1

def test_configure_logging_file_handler_writes_sanitized_json_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    logger = configure_logging(
        level=logging.DEBUG,
        console=False,
        file_path=log_path,
    )

    log_event(
        logger,
        logging.DEBUG,
        "runtime_test",
        raw_vin=RAW_VIN,
        vin_hashed=VIN_HASHED,
        payload_bytes="2E F4 B2 00",
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    assert payload["raw_vin"] == REDACTED
    assert payload["vin_hashed"] == VIN_HASHED
    assert payload["payload_bytes"] == REDACTED
    assert RAW_VIN not in lines[0]
    assert "2E F4 B2 00" not in lines[0]

def test_configure_logging_has_no_default_file_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    configure_logging(level=logging.DEBUG, console=True)
    assert not (tmp_path / "logs" / "autopulse.log").exists()
```

## Planning Notes

Areas where I expect adversarial pressure:

- Avoiding accidental writes from an adapter library that abstracts request mode/PID poorly.
- Whether VIN reading is itself acceptable. The safer default may be: do not request VIN; require user-provided `vin_hashed`.
- Whether the first harness should refuse to run if vehicle speed is non-zero.
- Ensuring sample cadence is enforced by code, not just docs.
- Ensuring unsupported protocols fail closed without scanning.
- Ensuring no raw payloads are written even when adapter exceptions include raw messages.
- Ensuring tests do not require hardware and still prove no write-capable calls are possible.
- Moving live interfaces out of the existing `tests.simulation` compatibility layer.

Do not assume any file not included here is safe. If a missing file matters, call that out as a blocker or requested context.
