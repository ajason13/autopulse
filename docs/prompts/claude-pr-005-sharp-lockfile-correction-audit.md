# Claude Chat prompt — PR-005 sharp cross-platform lock correction audit

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). Audit the
pushed PR-005 branch after a hosted CI correction. Return exactly one:
**APPROVED FOR COMMIT**, **APPROVED WITH MINOR FIXES**, or **NOT APPROVED**.
Do not authorize a tag, RC identifier, release, publication, deployment,
runtime change, or reuse of retired `v0.1.0-rc.1`.

## Why this re-audit is needed

The previously audited PR branch failed hosted run `32553311457` at docs
`npm ci`. All eight Python release cells passed, but the docs job reported
missing optional sharp package-lock records for Linux ppc64/riscv64 and Windows
arm64. The audit step was skipped because install failed. That run is invalid
and must not be treated as evidence.

## Exact correction to inspect from real source

Read the full remote diff from the prior approved tip
`52966c0465eec3af799452ea8083248bb1f49e2d` to the current branch tip. The
only dependency-content change must be five added `package-lock.json`
`packages` records:

- `node_modules/@img/sharp-libvips-linux-ppc64` 1.3.2
- `node_modules/@img/sharp-libvips-linux-riscv64` 1.3.2
- `node_modules/@img/sharp-linux-ppc64` 0.35.3
- `node_modules/@img/sharp-linux-riscv64` 0.35.3
- `node_modules/@img/sharp-win32-arm64` 0.35.3

Their resolved URLs and integrity values must be npm-generated. They came from
a clean `npm 10.9.2 install --package-lock-only --include=optional
--ignore-scripts` generation from `package.json`, not hand-authored values.
The correction must retain direct `sharp ^0.35.3`, exact `sharp` 0.35.3,
immutable Actions pins, the unconditional `npm audit --omit=dev
--audit-level=high` gate, and the audited contract test. It must not accept the
fresh generator's unrelated allowed-range dependency upgrades.

## Verification already observed locally

With Node 24/npm 11, `npm ci` passes against the corrected lock and
`npm audit --omit=dev --audit-level=high` reports zero vulnerabilities. A
fresh hosted PR run is still mandatory after the correction.

## Audit questions

1. Does source contain exactly the stated package-lock additions and no
   unrelated dependency/version drift?
2. Are the optional platform records legitimate npm-generated sharp 0.35.3
   dependencies and sufficient to resolve the hosted `npm ci` error?
3. Did the correction preserve the approved CI gate, contract-test behavior,
   documentation boundaries, and no-runtime-change scope?
4. Identify any blocker before the branch is rerun and considered for ordinary
   PR review. This is not an RC or release-readiness audit.
