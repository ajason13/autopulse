# AutoPulse Project Context

## Current Epic
**Runtime Hardening & Observability**
*   **Status:** In development.
*   **Active Story:** **Runtime Logging Hardening** - define and implement structured runtime logging policy before real-vehicle work.
*   **Tracking Epic:** AutoPulse Project Hub / Tasks.
*   **Tracking Task:** Runtime logging hardening.

## Project Vitals
*   **Mission:** Detect statistical drift in read-only OBD-II telemetry before DTCs appear.
*   **Governance:** Multi-Agent SDLC (Gemini/Claude/Codex).
*   **Project Tracker:** AutoPulse Project Hub.

## Recent Progress (May 2026)
*   **US-001 (Data Contract):** ✅ **DONE**. Verified by Claude.
*   **US-002 (Replay Harness):** ✅ **DONE**. Verified by Claude.
*   **US-003 (PdM Algorithms):** ✅ **DONE**. 
*   **US-004 (Windowed Analysis):** ✅ **DONE**.
    *   Implemented hybrid Median(3) → EWMA smoothing pipeline.
    *   Refactored project to `src/autopulse/` package structure.
    *   Specs moved to `docs/specs/` and synced with Starlight.
    *   397/397 tests passing (including adversarial smoothing suite).
*   **US-005 (Alerting Engine):** ✅ **DONE**.
    *   Implemented JSON-LD serialization in `src/autopulse/alert_exporter.py`.
    *   Security red lines (VIN hashing, RFC 8259 finite numbers) enforced.
    *   Verified against 81/81 adversarial tests by Codex and Claude.
    *   Final adversarial audit sign-off received from Claude.
*   **US-006 (EV Telemetry Data Contract):** ✅ **DONE**.
    *   Implemented isolated EV schema, envelope routing, UDS adapter guardrails, EV replay/noise support, and EV JSON-LD safety events.
    *   US-001 protocol enum patched to canonical `SAE_J1979-2`; replay aliases still normalize old underscore inputs.
    *   EV anomaly analysis remains out of scope: no EV-HDF, EV-OSF, or EV statistical drift scoring was added.
    *   Added public Starlight US-006 spec page.
    *   Verification: US-006 targeted suite `212 passed`; full suite `531 passed`; Starlight build passed with Node 24.
    *   Claude final audit passed with no blockers; US-006 is approved for merge.
    *   Follow-up branch `us-006-audit-followup` addressed documentation/test-harness observations and records future work.
    *   Future EV work: ReplayMode enum, bounded UDS event buffers, sustained SOCE-cliff helper, low-temperature charging anomaly research, and separate EV-HDF/EV-OSF story.
*   **Future Debugging Ergonomics:** ✅ **DONE**.
    *   Merged via PR #31.
    *   Added robust `replay-ev`/`replay-ice` summaries, `preview-alerts`, `inspect-guards`, and shared VS Code launch profiles.
    *   Verification: targeted debug/replay/PdM/alert suites `274 passed`; full suite `555 passed`.
    *   Claude re-review passed on 2026-05-26 with no blockers; approved for merge.

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.
*   **EV Implementation Boundary:** US-006 is complete within schema/routing/adapter/replay/JSON-LD safety scope. Do not backfill EV-HDF, EV-OSF, or EV anomaly scoring into US-006; those require a separate story and QA plan.
*   **Debugging Safety:** Debug logs and CLI output must preserve `vin_hashed` only; raw VINs, raw diagnostic payload bytes, seed-key material, tokens, and private workspace links must be redacted or omitted.
*   **Live Vehicle Boundary:** Do not start real-vehicle polling or road tests until a read-only smoke harness, runtime logging policy, safe PID allowlist, and operator safety checklist exist.

## Active Work: Runtime Logging Hardening
*   **Goal:** Promote current debug logging into a documented runtime observability layer that is safe for future live capture and useful for replay/debug operations.
*   **Current status:** Claude returned a conditional adversarial QA plan on 2026-05-27 and approved implementation after resolving the non-finite-number and malformed-`vin_hashed` logging blockers.
*   **Current scope:**
    *   Define log event taxonomy for validation, replay, guard, alert preview, adapter lifecycle, and future live-capture events.
    *   Add logging configuration helpers for console/file handlers without changing root logger behavior.
    *   Preserve existing `sanitize_debug_value()` and `log_event()` privacy guarantees across all new output paths.
    *   Add tests for log redaction, RFC 8259-safe payloads, level filtering, optional file output, and no rejected-frame leakage.
    *   Document retention/rotation expectations and local operator guidance.
*   **Implementation notes:**
    *   `log_event()` now rejects `NaN`, `Infinity`, and `-Infinity` before emission and serializes with `allow_nan=False`.
    *   Runtime logging validates `vin_hashed` shape before preserving it; malformed values are redacted.
    *   `autopulse.logging_config.configure_logging()` provides explicit console/file handler setup on the `autopulse` logger only, with no root logger mutation and no default file path.
    *   Rotation is deferred pending an explicit retention policy.
    *   Policy document: `docs/runtime-logging-policy.md`.
*   **Out of scope for this task:** direct vehicle polling, physical adapter integration, road testing, new OBD/UDS services, and EV anomaly scoring.

## Deferred: Real Vehicle Read-Only Smoke Harness
*   Defer until there is vehicle access and logging hardening is complete.
*   Future scope should be stationary-only, read-only, max 1 Hz, known safe PID allowlist, no raw VIN storage, replay-compatible JSONL capture, and explicit stop/failure behavior.

## Future Debugging Work
*   Claude signed off on the first debugging layer on 2026-05-25: approved to remain on `main` with no blockers.
*   Claude signed off on the debugging audit follow-up on 2026-05-26: PR #30 is approved to remain on `main` with no blockers.
    *   Completed follow-up scope: precise VIN-key redaction, scoped verbose logging, and adversarial debug-output tests.
*   Future Debugging Ergonomics merged via PR #31.
    *   Implemented robust row-by-row `replay-ev` and `replay-ice` summaries with accepted/rejected/security tallies and sanitized guard events.
    *   Implemented `preview-alerts` with per-`vin_hashed` ICE `PdMProcessor` sessions and sanitized alert output.
    *   Implemented `inspect-guards` JSON output for ICE bounds, EV bounds, restricted service IDs, and supported protocol constants.
    *   Added shared `.vscode/launch.json` debug profiles for contributor CLI workflows.
    *   Verification: targeted debug/replay/PdM/alert suites `274 passed`; full suite `555 passed`.
    *   Claude implementation audit returned a conditional pass on 2026-05-26 with one required pre-merge fix: replace broad hex-prefix security counting with an explicit restricted-service allowlist. Codex applied the fix and added focused regression coverage.
    *   Claude re-review passed on 2026-05-26: BLOCKER-01 fixed, all missing tests present, no new blockers, approved for merge to `main`.
    *   Tracked follow-ups: move replay adapter classes/constants out of `tests.simulation` into a source package; promote alert exporter sanitization/VIN helpers to public API; clarify committed `.vscode/launch.json` as shared contributor convenience using local `tmp/` sample files.
*   Track forward-looking validation-error logging risk if future schemas add string-valued fields.
*   Debugging PR audit requires a file-grounded Claude response. Off-topic ideation or unrelated project recommendations are not accepted as merge sign-off; use `docs/prompts/claude-debugging-foundation-audit.md` for the hardened audit prompt.

## Team Roster (2026)
*   **Lead Architect & Coordinator:** Antigravity CLI (Gemini 3.5 Flash Medium); Gemini Chat Deep Research for standards-heavy architecture.
*   **Lead Developer:** Codex (GPT-5.5)
*   **Lead Auditor:** Claude (Sonnet 4.6)
