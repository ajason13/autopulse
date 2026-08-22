# AutoPulse release-candidate notes template

Use this template only after the active-session user authorizes a new release-
candidate identifier and its exact 40-character commit SHA. Replace every
bracketed placeholder with source-grounded information from that committed
candidate. A local or untracked draft is not a final-audit input.

Do not reuse `v0.1.0-rc.1`. That evidence label is permanently retired after
its final audit was not approved. This template does not assign, authorize, or
imply a new RC identifier, release, publication, deployment, or readiness.

**Candidate label:** `[new authorized RC identifier]`
**Authorized commit:** `[40-character commit SHA]`
**Publication status:** Draft for source-grounded final audit; do not publish.

## Scope and prohibited use

[Describe the committed candidate's educational, offline/replay-only,
read-only scope and exact public API/CLI changes, or state that there are none.]

[Restate prohibited live vehicle, capture, VIN, telemetry, road, unattended,
write/control/session/security-access, seed/key, deployment, and other uses.]

## Evidence and platform boundary

[List only evidence tied to the authorized commit. State supported and
compatibility-only platform tiers, known limitations, and any missing hosted
evidence. Never infer Windows 11 support from Windows Server evidence.]

## Dependency remediation and security

- The direct production docs dependency is `sharp ^0.35.3`, with its exact
  npm-generated lockfile committed in this candidate.
- Docs CI runs the fail-closed production dependency gate
  `npm audit --omit=dev --audit-level=high` immediately after `npm ci` and
  before browser installation, build, and tests.
- No vulnerability exception was approved or used for this remediation. Any
  future exception requires independent approval, an owner, rationale,
  mitigation, and expiry.
- The production audit deliberately omits development dependencies; do not
  describe it as an exhaustive all-dependency audit.

[Record security reporting, upgrade/downgrade implications, and remaining
candidate-specific risks without including raw logs or private data.]

## Source-grounded audit status

[Confirm that this note, the PR-005 decision record, dependency/lockfile
remediation, CI control, and contract test are committed at the authorized SHA.
List the new candidate's fresh hosted evidence and independent final-audit
verdict. Do not reuse evidence or approval from the retired label.]

A later candidate must use a new authorized label and SHA, collect a fresh
complete hosted run, and receive a new source-grounded final audit before any
release action. Do not tag, publish, deploy, or create a GitHub Release from
this template.
