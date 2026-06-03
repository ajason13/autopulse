# Claude Audit Prompt: Live Adapter Safe Connection Settings

Claude, act as AutoPulse Lead Auditor for a safety-sensitive live-vehicle patch.

## Scope

This is an implementation audit for branch `live-adapter-safe-connection-settings`.

Codex changed the stationary ICE smoke harness so the live `python-obd` connection no longer relies on python-obd/adapter defaults for first-run connection behavior.

## Authoritative Context

AutoPulse is read-only OBD-II telemetry tooling. The current live-vehicle scope is limited to a supervised stationary ICE smoke test. Road testing, unattended operation, VIN reads, DTC clearing, UDS writes, routines, SecurityAccess, non-default diagnostic sessions, EV DID capture, and adapter/protocol auto-discovery during a live run remain prohibited.

The first vehicle run is constrained to ISO 15765-4 CAN protocol `6` (11-bit ID, 500 kbps). If the target vehicle is not compatible with protocol `6`, the operator must stop and open a separate reviewed change rather than falling back to auto-discovery.

## Changed Files

- `src/autopulse/live/adapter.py`
  - Added fixed live connection constants:
    - `LIVE_OBD_BAUDRATE = 115200`
    - `LIVE_OBD_PROTOCOL = "6"`
    - `LIVE_OBD_FAST = False`
    - `LIVE_OBD_CHECK_VOLTAGE = False`
    - `LIVE_OBD_TIMEOUT_SECONDS = 5.0`
  - `LiveOBDAdapter.connect()` now calls:
    - `self._obd.OBD(self.port, baudrate=..., protocol=..., fast=False, timeout=..., check_voltage=False)`
- `tests/live/test_smoke_harness_security.py`
  - Added a fake `python-obd` module and regression test asserting the exact constructor kwargs.
- `docs/specs/real-vehicle-read-only-smoke-harness.md`
  - Added the fixed connection-settings contract and no-auto-discovery stop rule.
- `docs/operator-checklists/real-vehicle-smoke-harness.md`
  - Added protocol `6` compatibility confirmation and a stop condition if compatibility is uncertain.
- `CONTEXT.md`
  - Marked the live-vehicle run blocked pending this patch's Claude review/sign-off and merge.

## Review Questions

1. Does this patch reduce live-vehicle risk without introducing a new unsafe path?
2. Is forcing protocol `6`, `fast=False`, `check_voltage=False`, baud rate `115200`, and timeout `5.0` the right first-run behavior for this constrained smoke test?
3. Should `LIVE_OBD_PROTOCOL` be a string `"6"` or an integer `6` for python-obd compatibility?
4. Are the tests sufficient to prevent future drift back to protocol auto-discovery, fast mode, voltage polling, or unsafe constructor defaults?
5. Are the operator checklist and spec updates clear enough to stop execution when protocol compatibility is unknown?

## Security Red Lines

Block the patch if it permits or weakens any of:

- write-capable OBD-II/UDS services;
- DTC clearing;
- VIN reads or raw VIN storage/logging;
- adapter protocol auto-discovery during live vehicle execution;
- non-default diagnostic sessions;
- SecurityAccess;
- road testing or unattended operation;
- unsanitized runtime logs or raw diagnostic payload leakage.

## Verification Already Run

- `PYTHONPATH=src python3 -m pytest tests/live -q` -> `28 passed`
- `PYTHONPATH=src python3 -m pytest -q` -> `1 failed, 598 passed`
  - Failure: `tests/test_us002_virtual_replay_harness.py::TestLogReplayer10Hz::test_10hz_no_interval_exceeds_tolerance`
  - Failure showed timing jitter around a 0.1s replay interval and is outside the changed live adapter area.
- `PYTHONPATH=src python3 -m pytest tests/test_us002_virtual_replay_harness.py::TestLogReplayer10Hz::test_10hz_no_interval_exceeds_tolerance -q` -> `1 passed`
- `git diff --check` -> passed

## Required Output

Return:

- PASS/FAIL verdict.
- Blocker findings first, with file/function references.
- Non-blocking recommendations.
- Missing tests or documentation gaps.
- Explicit statement whether this is approved for merge and whether a real stationary vehicle run may proceed after merge.
