# Claude Chat prompt — PR-005 docs supply-chain remediation final plan re-review

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). You returned
`MINOR FIXES` in round 3 only because two GitHub Actions fail-open mechanisms
remained outside the audit step's command body. Re-review these corrections
only. This is planning only: it authorizes no implementation, tag, RC label,
release, publication, deployment, runtime change, or reuse of retired
`v0.1.0-rc.1`.

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. State
whether MF-01 is fully resolved. Do not authorize implementation unless the
verdict is `NO BLOCKERS`.

## Added no-bypass requirements

The eventual audit-step contract is exactly one unconditional standalone step
between docs `npm ci` and Playwright/browser installation:

```yaml
- run: npm audit --omit=dev --audit-level=high
```

The static contract test must extract the `docs` job and its audit-step block,
then reject:

1. a step-level `if:` on the audit step (the intended step has no `if:`);
2. `continue-on-error: true` at the `docs` job level (the intended job omits
   the key entirely); and
3. every previously specified bypass: missing/weakened/reordered command,
   loss of `--omit=dev`, step-level `continue-on-error`, trailing `||`/`;`/
   `&&`, Bash error suppression (`set +e`, `set +o errexit`, or equivalent),
   and a step-level `shell:` override.

The remediation remains direct sharp `^0.35.3`/npm-generated lockfile,
unmodified immutable action pins/read-only permissions/docs job trigger,
committed PR-005 source artifacts, and no Python package, live diagnostic,
replay, telemetry/VIN, logging/observability, release, or deployment change.
MF-02 threshold rationale and MF-03 development-dependency residual are
already resolved and do not need reconsideration.
