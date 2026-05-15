# AutoPulse Project Context

## Current Epic
**Epic 2: Predictive Maintenance (PdM) Logic**
*   **Status:** Building
*   **Active Story:** **US-003 (PdM Algorithms)** - Development Started.

**Epic 3: Documentation & Developer Experience**
*   **Status:** Designing
*   **Active Story:** Setup and polishing of Starlight documentation site.

## Project Vitals
*   **Mission:** Detect statistical drift in read-only OBD-II telemetry before DTCs appear.
*   **Governance:** Multi-Agent SDLC (Gemini/Claude/ChatGPT/Codex).
*   **Notion Hub:** [AutoPulse Project Hub](https://www.notion.so/353834a0c8a680cfaab3dd2750ff730d)

## Recent Progress (May 2026)
*   **US-001 (Data Contract):** ✅ **DONE**. Verified by Claude.
*   **US-002 (Replay Harness):** ✅ **DONE**. Verified by Claude.
*   **US-003 (PdM Algorithms):** 🏗️ **IN PROGRESS**. 
    *   Adversarial test suite finalized by Claude at `tests/test_us003_pdm_algorithms.py`.
    *   Technical thresholds (HDF/OSF) and 60s sliding window logic are ready for implementation.

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.

## Team Roster (2026)
*   **PM/Architect:** Gemini CLI
*   **Researcher:** Gemini Chat
*   **Builder:** ChatGPT Plus (GPT-5.5)
*   **Auditor/QA:** Claude (Sonnet 4.6)
