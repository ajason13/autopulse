# AutoPulse Project Context

## Current Epic
**Epic 4: Electric Vehicle Integration**
*   **Status:** Building
*   **Active Story:** **US-006 (EV Telemetry Data Contract)** - complete; Claude final audit signed off.
*   **Notion Epic:** [Epic 4: Electric Vehicle Integration](https://www.notion.so/36a834a0c8a681109147c59a919b4335)
*   **Notion Task:** [US-006 - EV Telemetry Data Contract Research (ZEVonUDS)](https://www.notion.so/36a834a0c8a681329c8ae05946ffae5b)

## Project Vitals
*   **Mission:** Detect statistical drift in read-only OBD-II telemetry before DTCs appear.
*   **Governance:** Multi-Agent SDLC (Gemini/Claude/Codex).
*   **Notion Hub:** [AutoPulse Project Hub](https://www.notion.so/353834a0c8a680cfaab3dd2750ff730d)

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

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.
*   **EV Implementation Boundary:** US-006 is complete within schema/routing/adapter/replay/JSON-LD safety scope. Do not backfill EV-HDF, EV-OSF, or EV anomaly scoring into US-006; those require a separate story and QA plan.

## Team Roster (2026)
*   **Lead Architect & Coordinator:** Antigravity CLI (Gemini 3.5 Flash Medium); Gemini Chat Deep Research for standards-heavy architecture.
*   **Lead Developer:** Codex (GPT-5.5)
*   **Lead Auditor:** Claude (Sonnet 4.6)
