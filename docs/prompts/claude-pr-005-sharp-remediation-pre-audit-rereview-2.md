# Claude Chat prompt — PR-005 docs supply-chain remediation final plan re-review

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). You returned
`MINOR FIXES` on the first plan and focused re-review. Re-review only the
remaining MF-01 correction below. This is still planning only: it authorizes
no implementation, tag, RC identifier, release, publication, deployment,
runtime change, or reuse of retired `v0.1.0-rc.1`.

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. State
whether MF-01 is now fully resolved. Do not authorize implementation unless
the verdict is `NO BLOCKERS`.

## MF-01: complete fail-open prevention contract

The proposed docs audit remains one standalone step immediately after `npm ci`:

```yaml
- run: npm audit --omit=dev --audit-level=high
```

Its contract test must reject each of the following, in addition to missing,
weakened, or reordered audit commands:

- `continue-on-error` unless it is explicitly `false`;
- `||`, `;`, or `&&` after the audit command in the step's `run` value;
- Bash error suppression anywhere in the audit step's `run` body, including
  `set +e`, `set +o errexit`, and equivalent forms that turn off `errexit`; and
- any step-level `shell:` key. The audit step must use the job's default GitHub
  Actions Bash invocation rather than a custom command that can omit `-e`.

The eventual contract test will extract the docs audit-step block and make
these negative controls explicit; it will not merely find a global substring.
The remediation remains otherwise unchanged: sharp `^0.35.3` with an
npm-generated lockfile, committed PR-005 source artifacts, and no runtime,
diagnostic, telemetry/VIN, logging/observability, release, or deployment
change. The threshold rationale and dev-dependency residual are already
resolved and need no further review.
