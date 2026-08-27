# Codex handoff — Dependabot pip lockfile CI remediation

Resume AutoPulse's **Dependabot pip lockfile CI remediation** from current
`origin/main`. This is a gated maintenance task, not a release-candidate task.

## Current state (2026-08-27)

- Baseline: `origin/main` is
  `6232f651e4887eb84645fc285e744b9cbad458da` (PR #78 merged).
- Tracker: [Dependabot pip lockfile CI remediation](https://app.notion.com/p/3c9834a0c8a68160a6d8f61fb40f7fca).
- Existing planning artifacts on `main`:
  - `docs/prompts/claude-dependabot-pip-lockfile-ci-remediation-pre-audit.md`
  - `docs/prompts/codex-dependabot-pip-lockfile-ci-remediation.md`
- Open Dependabot PRs: #71 jsonschema, #72 pytest, #73 uv, #74 hatchling,
  and #75 twine.
- Each updates declarations but leaves `uv.lock` stale. Their docs jobs pass;
  all eight package cells fail at `python -m uv export --locked ...` with
  “The lockfile at `uv.lock` needs to be updated.”

## First actions

1. Read `AGENTS.md`, `CONTEXT.md`, the Notion task, both planning artifacts,
   current `pyproject.toml`, `requirements*.txt`, `uv.lock`, and CI workflow.
2. Fetch `origin`; inspect each open Dependabot PR and representative failed
   jobs. Reconfirm the cause before changing files.
3. Preserve dirty/untracked user files. Create a new maintainer-owned branch
   from the current `origin/main`; never edit or merge Dependabot branches.
4. Check whether Claude has issued a recorded **NO BLOCKERS** verdict for the
   pre-implementation prompt. If it has not, prepare the handoff and stop:
   implementation is not authorized.

## Implementation gate and scope

Only after a Claude `NO BLOCKERS` verdict:

- Consolidate the five exact dependency updates into one maintainer-owned PR.
- Keep `pyproject.toml` and corresponding requirements files consistent.
- Use the approved `uv 0.12.5` resolver in a clean environment to regenerate
  `uv.lock`; record the exact version and command. Never hand-edit lockfile
  records, URLs, markers, or hashes.
- Review the lock diff semantically; reject unrelated dependency/version,
  source, marker, platform, or integrity drift.
- Add focused stale-lock regression coverage if the current tests do not
  directly exercise locked export consistency.
- Run targeted local package/supply-chain checks, then the broader relevant
  suites. Retain concise sanitized outcomes only.
- Obtain a source-grounded Claude implementation audit before any merge claim.
- Push only after the audit gate; require one fresh exact-head hosted run with
  docs and all eight package cells passing.

## Hard stops

Do not remove `--locked`, generate a lockfile in CI, skip cells, weaken
archive/offline-install/SBOM/license/vulnerability gates, or treat local/docs
success as package evidence. Do not merge or close any PR, create a release,
tag, publication, deployment, or Windows 11 claim without explicit
active-session user authorization.

No runtime diagnostic, replay, telemetry, VIN, logging, CLI, or observability
change is in scope. Preserve the offline educational/replay-only and
`autopulse.live`-exclusion boundaries.

## Authorized merge sequence (only after separate user approval)

Merge the maintainer-owned consolidation PR only after Claude sign-off and the
exact-head hosted matrix passes. Then, with explicit authorization, close #71
through #75 as superseded with a concise reference to that merged PR; never
merge the stale individual Dependabot PRs. Synchronize the Notion task,
`CONTEXT.md`, and audit record with the exact SHA, evidence, and no-runtime
change result.
