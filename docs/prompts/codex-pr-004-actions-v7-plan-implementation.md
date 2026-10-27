# Codex Prompt — PR-004 audited GitHub Actions v7 SHA-pin upgrade

> Historical prompt retained for provenance. Its task state and external-auditor,
> tracker, and context-file instructions are superseded by current `AGENTS.md`.

You are Codex, the accountable lead architect and builder for AutoPulse PR-004.

## Objective

Plan, obtain the required adversarial audit for, implement, and verify a narrowly
scoped upgrade of the GitHub Actions used by AutoPulse CI and documentation
deployment. The target is v7 of `actions/checkout`, `actions/setup-python`, and
`actions/setup-node`, referenced only by immutable 40-character commit SHA with
an adjacent readable version comment.

The relevant tracker task is PR-004 — audited GitHub Actions v7 SHA-pin
upgrade (historical tracker).

## Current state

- `main` contains PR-003’s approved eight-cell release-gate workflow and docs
  verification job.
- `.github/workflows/ci.yml` currently pins `actions/checkout`,
  `actions/setup-python`, and `actions/setup-node` to reviewed v6 SHAs.
- `.github/workflows/deploy-docs.yml` pins checkout and setup-node to v6 SHAs
  and keeps the Pages actions on their reviewed majors.
- Dependabot PRs #39, #42, and #45 propose mutable v7 tags. Do **not** merge
  them or copy their mutable references.
- PR #39 correctly fails the current workflow-contract test because that test
  expects the checkout SHA comment to say `v6`. The replacement must update
  this test deliberately while preserving full-SHA and version-comment
  enforcement for every relevant action.
- CI remains untrusted-code verification: `pull_request`/ordinary push only,
  `contents: read`, no secrets, no privileged trigger, and no self-hosted
  runners. Docs deployment retains its narrowly scoped Pages credentials.

## Non-negotiable constraints

- Do not use `@v7`, `@main`, a tag-only reference, or a shortened SHA in any
  workflow.
- Do not weaken the PR-003 constraints on explicit runner labels, Bash
  `pipefail`, Windows `pwsh`, offline packaging gates, allowlist-built
  summaries, Windows evidence wording, Pages base-path verification, or
  least-privilege permissions.
- This is CI/deployment supply-chain work only. It does not alter runtime OBD,
  UDS, replay, telemetry, VIN, or diagnostic behavior.
- Preserve unrelated working-tree changes and do not merge, publish, release,
  or deploy production artifacts.

## Required delivery process

### 1. Plan before implementation

1. Inspect `AGENTS.md`, `CONTEXT.md`, the PR-003 contract, both workflows, and
   `tests/packaging/test_ci_workflow_contract.py`.
2. Verify the actual upstream v7 release commit SHA for each of the three
   actions at implementation time. Record the source/release and exact SHA in
   the plan or decision record; do not rely on Dependabot’s mutable tag.
3. Write a concise PR-004 design/decision record under `docs/specs/` covering:
   - action-to-SHA mapping and why each is an immutable release reference;
   - compatibility assumptions for GitHub-hosted runners;
   - exact static/adversarial tests;
   - rollback procedure (restore the immediately previous reviewed SHA pins);
   - scope boundary and observability rationale (no runtime-observability
     change is needed).
4. Update the Notion task to `1. Spec Drafting (Gemini)` or the project’s
   current equivalent coordination status, accurately noting that Codex owns
   the specification when Gemini is unavailable.

### 2. Independent auditor gate

1. Create a self-contained Claude Chat prompt with the proposed mapping and
   relevant workflow/test excerpts. Claude Chat has no filesystem access.
2. Ask Claude to challenge the upgrade’s SHA provenance, shell/permission
   regressions, test adequacy, and interaction with PR-003’s security
   contract.
3. Do not edit workflows until Claude returns a no-blocker pre-implementation
   verdict. Address any findings in the plan and obtain re-review when needed.

### 3. Implement the approved scope

1. Branch from current `main` using a focused name such as
   `pr-004-actions-v7-sha-pins`.
2. Update only the approved action pins and their adjacent version comments in
   `.github/workflows/ci.yml` and `.github/workflows/deploy-docs.yml`.
3. Strengthen the workflow-contract tests so they positively require each
   relevant `uses:` value to be an approved 40-hex SHA with an explicit v7
   comment. Do not merely blacklist `@v6` or `@v7` tags.
4. Ensure static tests also retain the PR-003 critical controls: no privileged
   events, minimal permissions, fixed runners, explicit Bash/pwsh semantics,
   Windows disclaimer, full-SHA pins in deploy workflow, and docs base-path
   rules.
5. Update `CONTEXT.md`, the decision record, and Notion with the exact scope
   and verification state.

### 4. Verification and handoff

1. Run `git diff --check` and the targeted workflow-contract tests.
2. Run the relevant full Python test suite and docs build/smoke suite in
   proportion to the touched workflows.
3. Open a PR with a clear action-to-SHA table, verification results, rollback
   pins, no-runtime-observability-change note, and audit status.
4. Collect all eight hosted release cells plus the docs job. A green local run
   does not substitute for hosted evidence.
5. Create a second self-contained Claude prompt for source-grounded final
   implementation audit. Do not claim merge readiness until Claude signs off
   and all required hosted checks pass.

## Required final response

Report:

- plan/contract location and Claude pre-implementation verdict;
- exact source files changed and pinned SHAs;
- local and hosted verification results;
- remaining blockers or deferred work;
- Notion and `CONTEXT.md` status;
- PR URL when opened.
