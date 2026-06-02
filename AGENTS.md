# AutoPulse Agentic Governance Framework

## Purpose

AutoPulse is governed by a 2026 Multi-LLM engineering team model. Each agent has a bounded role, explicit ownership, and a required handoff protocol before code can be merged into `main`.

## Team Structure

### Lead Architect, Coordinator & Developer: Codex / GPT-5.5

Model: `Codex/GPT-5.5`

Primary ownership:

- Research direction and technical feasibility.
- Standards alignment, including SAE J1979-2 OBD-II and related diagnostic constraints.
- Architecture decisions, system boundaries, and technical specifications.
- Data contract intent for OBD-II ingestion, replay, anomaly scoring, and reporting.
- Workflow coordination, managing `CONTEXT.md` active memory, and Notion automation.
- Implementation across `src/`, `schemas/`, and test-support code.
- Terminal operations, local tooling, package management, and repository hygiene.
- Docker, infrastructure, CI, developer setup, and reproducible execution.
- Translating approved specifications into working, tested code.

Required outputs:

- Technical design notes in `docs/`.
- Standards compliance notes for any PID, service, or protocol assumption.
- Architecture review before implementation begins on new subsystems.
- Handoff prompts and verification coordination.
- Focused implementation commits.
- Local verification evidence from the required test suites.
- Clear operational notes for environment, Docker, and automation changes.

### Lead Auditor: Claude Sonnet 4.6

Model: `Claude Sonnet 4.6`

Primary ownership:

- Adversarial QA strategy.
- Edge-case generation for schemas, OBD-II frames, replay harnesses, and anomaly scoring.
- Regression tests for failure modes, malformed data, boundary values, and security red lines.
- Final code sign-off before changes land on `main`.

Required outputs:

- Auditor-owned tests under `tests/`.
- Explicit pass/fail review notes for material changes.
- Final sign-off summary for release or merge candidates.

## Handshake Protocol

The transition from research/QA to implementation is now coordinated by Codex. Gemini/Antigravity is no longer the active coordinator because of rate-limit instability; historical Gemini research artifacts remain valid as provenance unless superseded by new Codex-owned specifications.

1. **Codex-Owned Specification:** Codex records the architecture intent, standards assumptions, security boundaries, and implementation scope in repository artifacts before material implementation begins.
2. **Auditor Challenge:** Claude produces or reviews the adversarial QA plan and identifies blockers for material schema, replay, analysis, live-vehicle, exporter, or security-sensitive changes.
3. **Verification:** 
    - Codex runs the full auditor-generated test suite.
    - The test run must report a 100% pass rate.
    - Codex records the verification command and result in the implementation summary.
4. **Final Sign-off:** Any failing test must be fixed or escalated back to the Lead Architect/Coordinator/Developer and Lead Auditor.

No exception is allowed for convenience or partial local confidence. If the auditor test suite cannot be executed or fails, Codex must not commit to `main`.

## Operating Rules

- Codex defines what should be built and why, then implements and operates the approved work.
- The Lead Auditor defines how the implementation is challenged and whether it is fit to merge.
- Security red lines around read-only OBD-II behavior take precedence over feature delivery.
- Data contracts in `schemas/` are the source of truth for ingestion and validation.
- Tests in `tests/` are merge gates, not optional checks.

## Local Codex Skills

Codex may use reusable local skills from `~/.codex/skills/` to improve consistency and token efficiency.

Reviewable source copies for AutoPulse-specific and reusable SDLC skills live under `docs/codex-skills/`. To activate or refresh them for local Codex sessions, copy the desired skill directories into `~/.codex/skills/`.

Public-vs-local AI artifact rules are defined in `docs/ai-artifacts-policy.md`. Keep durable, sanitized governance and prompts in git; keep local agent state, private workspace links, scratch prompts, and raw transcripts out of the repository.

Recommended skills for this repository:

- `model-routing`: Choose the smallest safe model and reasoning effort for each task.
- `pr-prep`: Prepare PR summaries, verification notes, and risk sections.
- `audit-response`: Handle Claude/auditor findings with reproduction, focused fixes, and verification.
- `docs-publishing`: Convert specs and research notes into public documentation.
- `local-dev-handoff`: Document setup, build, test, preview, and environment commands.
- `autopulse-sdlc-governance`: Follow AutoPulse story, audit, handoff, and merge-gate protocol.
- `autopulse-obd-schema-security`: Enforce read-only OBD-II/UDS schema, adapter, replay, and exporter rules.
- `autopulse-starlight-docs-qa`: Verify Starlight docs, GitHub Pages base-path behavior, and Playwright docs checks.
- `autopulse-notion-sync`: Keep Notion story, hub, wiki, and future-work pages aligned with repo state.
- `autopulse-pr-release-checklist`: Prepare AutoPulse PR summaries, verification notes, and risk sections.

Repository governance in this `AGENTS.md` takes precedence over any reusable skill. Security red lines, source-of-truth rules, and the `main` merge handshake cannot be relaxed by a skill.

## Repository Ownership Map

- `src/autopulse/data/`: OBD-II ingestion, normalization, and validation logic.
- `tests/simulation/`: Virtual replay harness and deterministic scenario playback.
- `src/autopulse/analysis/`: Statistical anomaly scoring and drift detection.
- `schemas/`: JSON Schema data contracts.
- `tests/`: Adversarial and regression test suites.
- `docs/`: Architecture, standards, and design records.
