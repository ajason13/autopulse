# Codex prompt — PR-005 release-candidate exercise and independent audit

> Historical prompt retained for provenance. Its task state and external-auditor,
> tracker, and context-file instructions are superseded by current `AGENTS.md`.

You are Codex, the accountable lead architect and builder for AutoPulse
**PR-005 — Release-candidate exercise and independent audit**.

## Objective

Plan, obtain the required independent Claude audit for, execute, and document
the end-to-end release-candidate readiness exercise for the approved offline
educational package profile. This is evidence work, not a change to AutoPulse
runtime diagnostic behavior.

PR-001 through PR-004 are merged. PR-004's audited immutable GitHub Actions v7
pins are on `main`; Dependabot PRs #39, #42, and #45 are closed as superseded.
The tracker task is PR-005 — Release-candidate exercise and independent audit (historical tracker).

## Start safely

1. Read `AGENTS.md`, `CONTEXT.md`, PR-001 through PR-004 decision records, the
   PR-005 Notion page, and current `main` before changing files.
2. Fetch `origin`, confirm PR-004 is merged and the three superseded Dependabot
   PRs are closed; start `pr-005-release-candidate-exercise` from `origin/main`.
3. Preserve dirty/untracked working-tree changes; never reset, restore, or
   include unrelated files.
4. Update Notion to the current planning status and state that Codex owns
   coordination when Gemini is unavailable.

## Authority boundary

Do **not** create a Git tag, GitHub Release, package publication, deployment,
or public release unless the active-session user explicitly authorizes that
external action and supplies or approves the exact release-candidate identifier.
Without an authorized existing RC tag, document the blocker and prepare only
the complete evidence/audit plan.

No live vehicle, OBD-II/UDS, VIN, telemetry capture, diagnostic write, replay
semantics, or runtime behavior changes are in scope. Preserve read-only and
privacy red lines. Hosted Windows Server evidence is not Windows 11 evidence.

## Required delivery process

### 1. Specification

Create a concise PR-005 decision record under `docs/specs/` covering:

- exact RC identifier/commit and provenance, or the authority blocker;
- every inherited clean-install, package, replay, docs, security,
  SBOM/license/vulnerability, and artifact gate from PR-001–PR-004;
- evidence matrix: command/job, OS/Python cell, sanitized retained evidence,
  pass/fail condition, and owner;
- release-note limitations/prohibited use, including offline/replay-only scope
  and the unresolved Windows 11 evidence boundary;
- artifact retention: never commit wheelhouses, artifacts, raw logs, private
  paths, telemetry, VIN-like values, or secrets;
- rollback/stop conditions and no-runtime-observability-change rationale.

Verify mutable facts from primary sources at implementation time.

### 2. Pre-implementation audit

Create a self-contained Claude Chat prompt under `docs/prompts/` with the plan,
workflow/test excerpts, evidence matrix, authority boundary, and questions on
provenance, tag authority, artifact leakage, matrix adequacy, Windows wording,
and PR-001–PR-004 regressions.

Do not execute the RC exercise, alter release workflows, create a tag, or make
a release-readiness claim until Claude returns `NO BLOCKERS`. Address findings
and obtain re-review when necessary.

### 3. Approved execution

After pre-audit approval and explicit release-action authority:

1. Run approved local release/package and documentation checks; retain concise,
   sanitized evidence only.
2. Collect GitHub-hosted evidence for every release cell and docs job; local
   success never substitutes for hosted evidence.
3. Confirm every item belongs to the exact RC commit/identifier.
4. Draft/update release notes with limitations and prohibited use; do not
   publish without separate authorization.
5. Update `CONTEXT.md`, decision record, and Notion with evidence/audit state.

### 4. Final audit and handoff

Create a second source-grounded Claude prompt containing exact commit/RC ID,
diff, local/hosted evidence, artifact evidence, release-note text, limitations,
and finding resolutions.

Do not say "release ready", merge, tag, publish, deploy, or close the tracker
until final Claude sign-off and every required hosted job passes. Record missing
mandatory evidence as a blocker, never as local-confidence equivalence.

## Required final response

Report decision/audit locations and verdicts; RC ID or authority blocker;
changed files and no-runtime-observability confirmation; local/hosted matrix
evidence; release-note coverage; Notion/CONTEXT status; blockers/deferred work;
and PR URL if opened.
