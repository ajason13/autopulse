# Claude Adversarial Planning Prompt: Future Debugging Ergonomics

You are Claude Sonnet 4.6 acting as the AutoPulse Lead Auditor.

Your task is to review the "Future Debugging Ergonomics" specification and produce an adversarial QA/verification plan before Codex implements the features.

## Current Project Context

AutoPulse is an educational, read-only OBD-II anomaly detection framework.
A sanitized debugging foundation was recently implemented (PR #29, PR #30) and signed off by you:
*   `src/autopulse/debugging.py` provides `sanitize_debug_value()`, `log_event()`, and `get_logger()`.
*   `src/autopulse/debug.py` has a minimal CLI supporting `validate-frame` and a simple `replay-ev`.
*   `tests/test_debugging.py` verifies that raw VINs, secrets, and payload bytes are redacted in stdout/logs.

We are now preparing to implement the deferred **Future Debugging Ergonomics** task in the backlog to expand developer-contributor tooling while strictly upholding our read-only, zero-leak privacy model.

## Proposed Subcommands & Ergonomics Architecture

The proposed enhancements are:
1.  **Robust Replay Diagnostic Loop:**
    Refactor `replay-ev` (and apply to new `replay-ice`) to process rows inside a robust, row-by-row loop. Instead of raising on the first error, catch:
    *   `ValidationError` -> Log using `LOGGER.warning`, increment `rejected_frames`.
    *   `SecurityViolationError` or `CommandBlockedException` -> Log using `LOGGER.error`, increment `security_violations`, and append the event name/code (e.g. `"SIGN_CONVENTION_UNDOCUMENTED"`, `"TESTER_PRESENT_RATE_LIMIT"`) to `guard_events`.
    *   Successfully accepted frames -> Increment `accepted_frames`.
    *   Output a sanitized JSON summary:
        ```json
        {
          "ok": true,
          "powertrain_type": "EV" | "ICE",
          "total_rows": 10,
          "accepted_frames": 8,
          "rejected_frames": 1,
          "security_violations": 1,
          "guard_events": ["SIGN_CONVENTION_UNDOCUMENTED"],
          "mode": "PASSIVE"
        }
        ```
2.  **`replay-ice` Subcommand:**
    *   Supports replaying ICE OBD-II frames from a JSONL file.
    *   Runs the robust diagnostic loop using `MockAdapter` and `JSONLProvider` from `tests.simulation.virtual_replay.py`.
    *   Produces an identical structured summary showing row tallies.
3.  **`preview-alerts` Subcommand:**
    *   Supports `preview-alerts --jsonl <path>`.
    *   Processes ICE frames through a dynamically initialized `PdMProcessor` per vehicle session (grouped by `vin_hashed` so sliding windows are independent).
    *   Outputs a sanitized JSON list of all generated `PdMAlert`s where `failure_type != "NONE"` or `failure_probability > 0.0`.
4.  **`inspect-guards` Subcommand:**
    *   Prints a structured JSON configuration of active physical bounds (RPM, Temp, Load limits) and restricted diagnostic services.
5.  **VS Code Launch Configuration (`.vscode/launch.json`):**
    *   Provides debugging profiles for validating single ICE/EV frames, replaying EV sequences, and previewing ICE alerts.

## Project Tech Stack And Layout

*   Language: Python
*   Test runner: pytest
*   Files involved:
    *   `src/autopulse/debug.py` (CLI entry point)
    *   `src/autopulse/debugging.py` (redaction logic)
    *   `tests/test_debugging.py` (where new tests will be added)
    *   `.vscode/launch.json` (new file)

## Your Required Output

Produce a Markdown QA plan with these sections:

1.  **Audit Verdict:** Technical review of the proposed subcommands and structured summary strategy.
2.  **Privacy & Redaction Constraints:** Specific requirements for preventing raw VIN or token leakage in all subcommands.
3.  **Positive Test Scenarios:** Successful execution traces for `replay-ice`, `replay-ev`, `preview-alerts`, and `inspect-guards`.
4.  **Negative and Adversarial Test Scenarios:**
    *   Schema Validation Failures: verifying that row-level validation errors are tallied and logged without terminating the replay.
    *   UDS Guard Violations: verifying that restricted service injection and rate limits are captured and categorized in the summary.
    *   Dynamic Session Partitioning: verifying that alerts grouped by `vin_hashed` in `preview-alerts` maintain completely isolated sliding-window histories.
    *   Raw VIN Leakage Checks: asserting that validation errors and command warnings never log or print raw VIN strings.
5.  **Recommended Test Assertions:** Scoped `caplog` logging assertions to ensure correct safety events and warning/error levels.
6.  **Codex Guidance:** Exact unit test structure and naming recommendations for `tests/test_debugging.py`.
7.  **Open Questions or Blockers:** Critical items that must be aligned on before implementation.

Do not write implementation code. This is an adversarial planning handoff for Codex.
