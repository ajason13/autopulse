# AutoPulse Project Context

## Current Epic
**Runtime Hardening & Observability**
*   **Status:** Ready for supervised stationary smoke test.
*   **Active Story:** **Stationary Vehicle Smoke Test Execution** - run the first read-only vehicle check under the approved checklist.
*   **Tracking Epic:** AutoPulse Project Hub / Tasks.
*   **Tracking Task:** First stationary read-only vehicle smoke test.

## Project Vitals
*   **Mission:** Detect statistical drift in read-only OBD-II telemetry before DTCs appear.
*   **Governance:** Multi-Agent SDLC (Codex/Claude). Codex now owns architecture, coordination, implementation, repository memory, and Notion sync; Claude remains the independent auditor.
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
*   **Runtime Logging Hardening:** ✅ **DONE**.
    *   Merged via PR #32.
    *   Added `autopulse.logging_config.configure_logging()` for explicit console/file runtime logging on the `autopulse` logger only.
    *   Hardened `log_event()` with `vin_hashed` shape validation, non-finite number rejection, and `allow_nan=False` serialization.
    *   Added `docs/runtime-logging-policy.md`.
    *   Verification: focused logging/debug CLI suite `40 passed`; expanded security/replay/exporter suite `153 passed`; full suite `571 passed`.
    *   Claude implementation audit passed on 2026-05-27 with no blockers; approved for merge.
*   **Real Vehicle Read-Only Smoke Harness:** ✅ **DONE**.
    *   Merged via PR #33.
    *   Added `src/autopulse/live/` with an ICE-only stationary read-only smoke harness, live adapter boundary, and CLI.
    *   Requires explicit adapter port, precomputed `vin_hashed`, output path, finite capture limit, and stationary confirmation.
    *   Enforces exact six-PID Mode 01 allowlist, request-side `command_filter()`, max 1 Hz cadence, `vehicle_speed > 0` safety abort, sanitized runtime logging, and replay-compatible JSONL output.
    *   Added `docs/operator-checklists/real-vehicle-smoke-harness.md`.
    *   Verification: `tests/live` -> `27 passed`; targeted live/logging/debug/security suite -> `70 passed`; full suite -> `598 passed`.
    *   Claude re-review passed on 2026-05-28 with no blockers; approved for merge.
*   **Live Adapter Safe Connection Settings:** ✅ **DONE**.
    *   Merged via PR #36 on 2026-06-03.
    *   Forces the stationary live OBD adapter to use explicit `python-obd` connection settings: protocol `6`, baud rate `115200`, `fast=False`, `check_voltage=False`, and timeout `5.0` seconds.
    *   Adds regression coverage against adapter auto-discovery, fast mode, voltage polling, and implicit constructor defaults.
    *   Verification: `PYTHONPATH=src python3 -m pytest tests/live -q` -> `28 passed`; full suite produced one transient US-002 timing failure, and the focused rerun passed.

## Governance Update (June 2026)
*   Codex has taken over the Lead Architect & Coordinator role formerly held by Antigravity CLI / Gemini because Gemini CLI rate limits made it unreliable for day-to-day coordination.
*   Codex now owns research framing, standards assumptions, architecture decisions, implementation, repo hygiene, `CONTEXT.md`, and Notion synchronization.
*   Claude remains the Lead Auditor and required adversarial QA/sign-off owner for material changes.
*   Historical Gemini research and prompts remain provenance for completed work unless a new Codex-owned spec supersedes them.

## Active Constraints
*   **Read-Only Only:** Any write-access logic is a P0 security violation.
*   **Physics-Based Validation:** RPM must be rejected if > 9,500; Temp rejected if > 140C.
*   **Sliding Window:** US-003 alerts must use a 60s window (circular buffer) to prevent flicker.
*   **EV Implementation Boundary:** US-006 is complete within schema/routing/adapter/replay/JSON-LD safety scope. Do not backfill EV-HDF, EV-OSF, or EV anomaly scoring into US-006; those require a separate story and QA plan.
*   **Debugging Safety:** Debug logs and CLI output must preserve `vin_hashed` only; raw VINs, raw diagnostic payload bytes, seed-key material, tokens, and private workspace links must be redacted or omitted.
*   **Live Vehicle Boundary:** Only the approved stationary ICE smoke test is conditionally allowed after dry-run and checklist completion. Road testing, unattended operation, EV DID capture, ambient-temp PID `0x46`, VIN reads, DTC clearing, UDS writes, routines, security access, and session escalation remain prohibited.

## Active Work: Stationary Vehicle Smoke Test Execution
*   **Goal:** Execute the first real-vehicle check using the merged read-only smoke harness.
*   **Current status:** PR #36 is merged. Proceed only with the dry-run first, the operator checklist, explicit protocol `6` compatibility confirmation, and bounded stationary capture limits.
*   **Connection hardening scope:** `LiveOBDAdapter` now forces `python-obd` protocol `6`, baud rate `115200`, `fast=False`, `check_voltage=False`, and timeout `5.0` seconds to avoid adapter auto-discovery, command shortcuts, and background voltage checks during the first stationary run.
*   **Required order:**
    *   Install/confirm `python-obd` in the operator environment.
    *   Confirm the target vehicle supports ISO 15765-4 CAN protocol `6` (11-bit ID, 500 kbps); stop rather than falling back to protocol auto-discovery if uncertain.
    *   Precompute `vin_hashed` outside AutoPulse; do not read VIN from the vehicle.
    *   Run `PYTHONPATH=src python3 -m autopulse.live.cli ... --dry-run` and confirm exit code `0`.
    *   Confirm stationary setup from `docs/operator-checklists/real-vehicle-smoke-harness.md`.
    *   Run a bounded capture such as `--max-samples 60 --confirmed-stationary`.
    *   Monitor `stderr`; abort on unexpected warning/error events.
*   **Still prohibited:** road testing, unattended monitoring, write-capable services, DTC clearing, UDS active diagnostics, EV DID capture, ambient-temp PID `0x46`, VIN reads, performance claims, and production-grade adapter support.

## Runtime Logging Follow-Ups
*   Non-blocking items from Claude's PR #32 audit:
    *   Add comments documenting the sanitize-before-finite-validation order and debug CLI handler formatter interaction.
    *   Add follow-up tests for reverse handler configuration order, nested non-finite values, deeply nested file parent creation, append-mode multi-event file logging, and `console=False`/no-file no-op configuration.
    *   Consider making `JsonLineFormatter` private to reduce external coupling.
    *   Document the existing `_serialize_preview_alert()` defense-in-depth order: `_validate_vin_hash()` runs before `sanitize_debug_value()`.

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
*   **Lead Architect, Coordinator & Developer:** Codex (GPT-5.5)
*   **Lead Auditor:** Claude (Sonnet 4.6)

## PR-001 Decision Record (2026-08-11)
*   Codex owns the draft offline/replay release specification at `docs/specs/pr-001-offline-release-profile-and-threat-model.md`.
*   Scope is a local educational package profile only: CPython 3.13/3.14 on a deliberately narrow OS matrix, with no network required after installation and no fleet, road, unattended-live, VIN-read, capture, or write-capable diagnostic use.
*   Claude returned a pre-implementation `MINOR FIXES` verdict on 2026-08-12. Codex incorporated: per-cell prebuilt-wheel evidence, independently signed and expiring critical/high vulnerability exceptions, automated SBOM privacy/path-leak scanning, path-free support-command examples, and a fail-closed sdist/wheel content allowlist gate.
*   Claude's 2026-08-12 focused re-review returned `NO BLOCKERS`, closing MF-01 through MF-05 and both tracked observations. PR-002 may begin against this specification, but each subsequent PR remains separately gated. This is specification approval only; no implementation or release approval is claimed. PR-001 remains unclosed in the tracker per task instruction.

## PR-002 Architecture Kickoff (2026-08-13)
*   Codex created `docs/specs/pr-002-packaging-supply-chain-decision-record.md`: Hatchling/PEP 621, universal lock with per-cell wheel/hash proof, canonical schema resource staging, CycloneDX, pip-audit/pip-licenses, artifact allowlist, and offline-only public CLI boundaries. The planned offline distribution excludes `autopulse.live` and must prove its import fails after installation.
*   Claude's 2026-08-13 PR-002 contract re-review returned `NO BLOCKERS`, after the explicit `validator.py` installed-resource migration requirement and the matrix-evidence, license-CSV, determinism, archive/RECORD, and content-scan gates were added. PR-002 implementation may begin; no package metadata, dependencies, schemas, CI, release artifact, or runtime behavior has changed yet.
*   Implementation encountered a Hatchling format constraint: root `.gitignore` is unavoidable in its sdist. The only approved exception allows that exact root file in an sdist; wheels and all other VCS-named paths remain prohibited. The archive validator must enforce this distinction, and it requires Claude follow-up review.
+*   PR-002 implementation added Hatchling/PEP 621 metadata, the universal lock, packaged schema resources with `importlib.resources` loading, offline-only CLI packaging, hash/wheelhouse verification, supply-chain policy scripts, package documentation, and focused packaging tests.
*   Verified locally: 33 packaging-policy tests; 198 targeted schema/package tests; deterministic artifacts/SBOM; strict `pip-audit`, license policy, `twine check --strict`, and `check-wheel-contents`; one native CPython 3.14.6 macOS x86_64 offline install. Full-suite output was incomplete despite exit code `0`; remaining supported cells are unverified. Claude implementation audit is pending in `docs/prompts/claude-pr-002-packaging-supply-chain-implementation-audit.md`.
*   Claude's 2026-08-13 implementation audit returned `APPROVED WITH MINOR FIXES`: a complete captured full-suite result, direct archive-policy evidence, and negative hash/wheelhouse installation evidence were required before merge. Codex added those checks and clarified that raw-identifier scanning is intentionally suppression-free. Verification now records `643 passed in 57.54s`, 36 packaging tests, and native macOS x86_64 evidence for CPython 3.13.14 and 3.14.6. Claude's focused re-review then returned `NO BLOCKERS`: the full-suite gate, direct real-artifact validation, negative pip probes, and suppression-free decision are confirmed. Linux x86_64, Windows x86_64, and macOS arm64 native evidence remains unavailable locally. The PR-002 contract's literal every-supported-cell acceptance criterion remains a release-evidence gap to resolve in PR-003; no release is authorized.

## PR-003 CI Architecture Kickoff (2026-08-14)
*   Codex created `docs/specs/pr-003-ci-release-gates-and-docs-assurance.md` and the self-contained Claude Chat QA prompt `docs/prompts/claude-pr-003-ci-release-gates-qa-plan.md`. PR-003 is still pre-implementation: it proposes eight explicit CPython 3.13/3.14 matrix cells, pinned Actions, read-only untrusted-PR checks, PR-002 fail-closed packaging evidence, and non-deploying `/autopulse/` documentation verification.
*   The contract records a material evidence boundary: GitHub's available x64 Windows hosted runners are server images, not Windows 11 desktop proof. PR-003 must label them only as compatibility evidence and must not add a self-hosted runner or silently claim the Windows 11 profile is validated.
*   Claude's 2026-08-15 focused NF-01 re-review returned `NO BLOCKERS`. PR-003 CI/documentation implementation is authorized against the approved contract. Implement its Windows static test as a positive allowlist: each required Windows gate's `shell` value must equal `pwsh`, rather than only blocking `cmd`/`bat` spellings. This is CI/documentation authorization only—no public release or Windows 11 validation is approved. No live diagnostic, telemetry, VIN, or write-capable scope is authorized.
*   PR-003 implementation now replaces the legacy CI with the approved eight-cell release-gate matrix, immutable action pins, explicit Bash/PowerShell failure handling, wheelhouse/offline/package/supply-chain gates, sanitized summary emission, and a non-deploying committed-config docs job. `deploy-docs.yml` action pins are hardened. New workflow-contract tests pass with targeted packaging tests (`35 passed`), and the Starlight build passed. A complete final full-suite capture and Claude implementation audit remain required before merge.

## PR-004 GitHub Actions v7 SHA-pin upgrade (2026-08-17)
*   Codex created branch `pr-004-actions-v7-sha-pins` and began the Codex-owned specification because Gemini is unavailable. The Notion task is at `1. Spec Drafting (Gemini)` with the branch recorded.
*   `docs/specs/pr-004-actions-v7-sha-pin-decision-record.md` records official upstream resolution on 2026-08-17: checkout `v7.0.1` `3d3c42e5aac5ba805825da76410c181273ba90b1`; setup-python `v7.0.0` `5fda3b95a4ea91299a34e894583c3862153e4b97`; setup-node `v7.0.0` `820762786026740c76f36085b0efc47a31fe5020`.
*   Claude's source-verified 2026-08-17 pre-implementation review returned `MINOR FIXES`, with no blocker. Codex incorporated required exhaustive six-occurrence pin coverage and a `setup-python` `pip-install` regression guard; literal privileged-trigger assertions already confirm MF-03.
*   Claude disclosed a pre-existing floating `ubuntu-latest` runner in `deploy-docs.yml`; it is intentionally out of PR-004 scope and requires a separate infrastructure decision.
*   Local implementation verification: workflow contract `2 passed`; full Python suite `647 passed`; Starlight build passed; smoke `6 passed, 2 skipped`; docs regression `48 passed, 2 skipped`. GitHub Actions run `32108791619` is tied to PR head `dc2fe632a535a4d4bedc7aacc0f17e7db5bf53ca` and passed all eight release cells plus docs. Claude's final audit approved PR-004 for merge contingent on this independent hosted-evidence confirmation; that condition is satisfied. No runtime observability change was needed.
