# AutoPulse Agentic Governance Framework

## Purpose

AutoPulse is governed by a 2026 Multi-LLM engineering team model. Each agent has a bounded role, explicit ownership, and a required handoff protocol before code can be merged into `main`.

## Team Structure

### Lead Architect & Coordinator: Antigravity CLI

Model: `Gemini 3.5 Flash` (Medium)

Primary ownership:

- Research direction and technical feasibility.
- Standards alignment, including SAE J1979-2 OBD-II and related diagnostic constraints.
- Architecture decisions, system boundaries, and technical specifications.
- Data contract intent for OBD-II ingestion, replay, anomaly scoring, and reporting.
- Workflow coordination, managing `CONTEXT.md` active memory, and Notion automation.

Required outputs:

- Technical design notes in `docs/`.
- Standards compliance notes for any PID, service, or protocol assumption.
- Architecture review before implementation begins on new subsystems.
- Handoff prompts and verification coordination.

### Lead Developer: Codex / GPT-5.5

Model: `Codex/GPT-5.5`

Primary ownership:

- Implementation across `src/`, `schemas/`, and test-support code.
- Terminal operations, local tooling, package management, and repository hygiene.
- Docker, infrastructure, CI, developer setup, and reproducible execution.
- Translating approved specifications into working, tested code.

Required outputs:

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

The transition from research/QA to implementation is automated via the Antigravity CLI (Gemini 3.5 Flash) to eliminate "clipboard lag."

1. **Automated Handoff:** Antigravity CLI packages the Lead Auditor's test suite and the architectural specifications into a structured prompt.
2. **Direct Execution:** Antigravity CLI triggers Codex implementation using `codex exec "[PROMPT]"`.
3. **Verification:** 
    - Codex runs the full auditor-generated test suite.
    - The test run must report a 100% pass rate.
    - Codex records the verification command and result in the implementation summary.
4. **Final Sign-off:** Any failing test must be fixed or escalated back to the Lead Architect/Coordinator and Lead Auditor.

No exception is allowed for convenience or partial local confidence. If the auditor test suite cannot be executed via `codex exec` or fails, Codex must not commit to `main`.

## Operating Rules

- The Lead Architect defines what should be built and why.
- The Lead Developer defines how approved work is implemented and operated.
- The Lead Auditor defines how the implementation is challenged and whether it is fit to merge.
- Security red lines around read-only OBD-II behavior take precedence over feature delivery.
- Data contracts in `schemas/` are the source of truth for ingestion and validation.
- Tests in `tests/` are merge gates, not optional checks.

## Local Codex Skills

Codex may use reusable local skills from `~/.codex/skills/` to improve consistency and token efficiency.

Recommended skills for this repository:

- `model-routing`: Choose the smallest safe model and reasoning effort for each task.
- `pr-prep`: Prepare PR summaries, verification notes, and risk sections.
- `audit-response`: Handle Claude/auditor findings with reproduction, focused fixes, and verification.
- `docs-publishing`: Convert specs and research notes into public documentation.
- `local-dev-handoff`: Document setup, build, test, preview, and environment commands.

Repository governance in this `AGENTS.md` takes precedence over any reusable skill. Security red lines, source-of-truth rules, and the `main` merge handshake cannot be relaxed by a skill.

## Repository Ownership Map

- `src/autopulse/data/`: OBD-II ingestion, normalization, and validation logic.
- `tests/simulation/`: Virtual replay harness and deterministic scenario playback.
- `src/autopulse/analysis/`: Statistical anomaly scoring and drift detection.
- `schemas/`: JSON Schema data contracts.
- `tests/`: Adversarial and regression test suites.
- `docs/`: Architecture, standards, and design records.
