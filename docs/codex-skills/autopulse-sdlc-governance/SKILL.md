---
name: autopulse-sdlc-governance
description: Use for AutoPulse user-story work, Multi-Agent SDLC coordination, Codex-owned architecture/implementation handoffs, Claude audit gates, story status updates, or determining what project artifacts must change before implementation, review, merge, or release.
metadata:
  short-description: Follow AutoPulse SDLC governance
---

# AutoPulse SDLC Governance

Use this skill when work touches AutoPulse story lifecycle, agent roles, audit gates, Notion/project memory, or merge readiness.

## Role Boundaries

- Codex owns research direction, standards interpretation, architecture intent, Notion coordination, implementation prompts, implementation, terminal operations, repo hygiene, tests, CI, docs edits, and PR preparation.
- Claude owns adversarial QA, edge-case tests, regression review, and final sign-off.

Historical Antigravity/Gemini research artifacts remain provenance for completed work unless a newer Codex-owned specification supersedes them.

## Required Flow

1. Confirm the current branch, uncommitted changes, and relevant story context.
2. Read local source-of-truth files before editing: `AGENTS.md`, `CONTEXT.md`, story docs, schemas, tests, and affected implementation files.
3. Keep implementation scoped to the approved story or audit feedback.
4. Run the auditor-specified tests first when they exist, then broader regression tests proportional to risk.
5. Update project memory and documentation when status, scope, or future work changes.
6. Prepare PR notes with summary, verification, risk, and audit status.

## Merge Gates

- Tests in `tests/` are merge gates, not optional checks.
- Schema files in `schemas/` are data-contract source of truth.
- Security red lines around read-only OBD-II behavior override feature delivery.
- Material changes need Claude review/sign-off before landing on `main`.
- Do not claim sign-off unless the user supplied it or it is recorded in project artifacts.

## Common Artifact Updates

- `CONTEXT.md`: active memory, branch/task state, verification evidence, audit status.
- `docs/`: architecture, standards notes, QA plans, implementation records.
- `grubby-galaxy/`: public Starlight docs for user-visible docs changes.
- Notion: story/task status, epic/hub summary, engineering wiki notes, future work.
- PR body: summary, verification, risk/notes, reviewer/audit status.

## Handoff Prompts

For Claude prompts, include:

- Role and scope.
- Authoritative context in plain language, not private URLs.
- Exact files or areas to review if the tool has repo access; otherwise summarize contents.
- Acceptance criteria and known constraints.
- Specific output requested: pass/fail, blocker findings, non-blocking recommendations, test additions.

For Codex-owned architecture/specification notes, include:

- Research objective and decision needed.
- Standards or regulatory assumptions to verify.
- Known project constraints.
- Expected deliverables: spec, open questions, implementation scope, verification plan, Notion updates.
