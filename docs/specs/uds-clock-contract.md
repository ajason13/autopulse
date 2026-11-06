# UDS guard clock input

`UDSCommandGuard.validate()` uses `time.monotonic()` when `now` is omitted or
`None`. An injected `now` supplies seconds in the same monotonic clock domain
for the existing TesterPresent four-second policy in
[US-006](us-006-ev-telemetry-data-contract.md#uds-safety-policy).
This is a local software convention for deterministic replay, not a new
diagnostic capability or a claim of protocol conformance.

Clock values must be integers or floats representable as finite Python floats.
Booleans, strings (including numeric strings), other types, non-finite values
and integer conversion overflow raise `ValueError` with a fixed message that
does not include the supplied value. Rejection leaves the last accepted
TesterPresent time unchanged and adds no guard event. The same validation
applies to the default clock result.

The first finite time is accepted in DefaultSession. Zero and negative clock
origins work. Subsequent times less than four seconds after the last accepted
time, including backward times, retain `TESTER_PRESENT_RATE_LIMIT` and leave
the last accepted time unchanged. Exactly four seconds is accepted. Values
must come from one clock domain; callers must not switch between injected and
default clocks within a guard session. Non-default-session rejection remains
unchanged and takes precedence over clock validation.

EV replay passes its synthetic `__now__` marker to this guard. The debug replay
CLI counts malformed clock input once as a rejected row, reports the existing
sanitized validation diagnostic, and continues. A rate-limit rejection retains
its existing guard-event classification. No input value is added to logs or
output. This does not change policy-state handling for rows rejected later by
other validation stages.

Regression coverage in
[`test_us006_ev_adapter_security.py`](../../tests/test_us006_ev_adapter_security.py)
and [`test_debug_cli_replay.py`](../../tests/test_debug_cli_replay.py) checks
rejection before/after an accepted time, subsequent rate enforcement, exact
boundary recovery, default-clock validation and safe CLI output.
