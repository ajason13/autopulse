# Claude Chat prompt — PR-005 docs supply-chain remediation focused re-review

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). You returned
`MINOR FIXES` for `docs/prompts/claude-pr-005-sharp-remediation-pre-audit.md`.
Re-review only the three corrections below. This remains planning only: it
authorizes no implementation, tag, RC label, release, publication, deployment,
runtime change, or reuse of retired `v0.1.0-rc.1`.

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. State
whether MF-01 through MF-03 are resolved. Do not authorize implementation
unless the verdict is `NO BLOCKERS`.

## MF-01: fail-open bypass prevention

The proposed docs CI command remains the standalone step
`npm audit --omit=dev --audit-level=high`, immediately after `npm ci` and
before Playwright/browser installation, build, smoke, and e2e work. The plan
now requires its contract test to reject all of the following:

- missing command, lower audit level, missing `--omit=dev`, or reordering;
- a `continue-on-error` key unless it is explicitly `false`; and
- `||`, `;`, or `&&` trailing after the audit command in the step's `run`
  value, including shell-success overrides such as `|| true` or `; exit 0`.

The intended production implementation uses no `continue-on-error` key and no
trailing shell continuation. This relies on GitHub Actions' normal Bash
nonzero-step behavior, so an audit failure fails the job.

## MF-02: intended threshold

The record now explains that `--audit-level=high` deliberately addresses the
high/critical production dependency risk that retired the RC while avoiding a
new release gate on lower-severity build-tool churn. It is not presented as a
replacement for Python's stricter supply-chain policy.

## MF-03: explicit residual gap

The record now explicitly states that `--omit=dev` excludes development
dependencies, including CI-only tools. This is an accepted residual risk for
this narrowly scoped remediation. A future all-dependency audit/report is
not part of PR-005 and must not be implied by this production gate.

All prior scope/red-line conditions remain unchanged: docs dependency,
lockfile, docs CI, focused workflow-contract test, and committed PR-005
documentation only; no Python packaging, live adapter, OBD-II/UDS/replay,
telemetry/VIN/logging/observability, deployment, release, or new RC action.
