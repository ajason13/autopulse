# AutoPulse Project Context

## Current Epic
**Epic 3: Documentation & Developer Experience**
*   **Status:** Building
*   **Active Story:** Setup and polishing of Starlight documentation site.

## Project Vitals
*   **Mission:** Detect statistical drift in read-only OBD-II telemetry before DTCs appear.
*   **Governance:** Multi-Agent SDLC (Gemini/Claude/Codex).
*   **Notion Hub:** [AutoPulse Project Hub](https://www.notion.so/353834a0c8a680cfaab3dd2750ff730d)

## Recent Progress (May 2026)
*   **US-001 (Data Contract):** ✅ **DONE**. Verified by Claude.
*   **US-002 (Replay Harness):** ✅ **DONE**. Verified by Claude.
*   **US-003 (PdM Algorithms):** ✅ **DONE**. 
    *   Implemented core analysis engine (HDF/OSF/CircularBuffer) in `src/analysis/`.
    *   Statistical monitoring (Z-score/IQR) integrated into window summaries.
    *   Technically reviewed by Codex and adversarial sign-off provided by Claude.
    *   101/101 tests passing.

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.

## Team Roster (2026)
*   **Lead Architect:** Gemini CLI (Gemini 3.1 Flash Lite)
*   **Lead Developer:** Codex (GPT-5.5)
*   **Lead Auditor:** Claude (Sonnet 4.6)
