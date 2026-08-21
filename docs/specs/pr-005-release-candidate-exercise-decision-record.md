# PR-005: Release-candidate exercise and independent audit

**Status:** Final audit not approved — `v0.1.0-rc.1` is retired.
**Parent decisions:** PR-001 through PR-004.
**Checked:** 2026-08-19.

**Pre-audit status:** Claude's 2026-08-19 second focused re-review returned
`NO BLOCKERS`; MF-01–MF-09 and OQ-01/OQ-02 are resolved. This approves the
planning stage only, not an RC action or release-readiness claim.

**Execution state (2026-08-19):** The user authorized label `v0.1.0-rc.1` at
`81a157927fcacf4ae47716326885d12477e0002d`, expressly without creating a tag
or release. The label was descriptive only; the full SHA was the candidate
identity. Exact-commit hosted run `32222492770` passed, but final audit did not
approve release readiness because of the `sharp` advisory and source-grounded
audit-input gap described below. Windows 11 and retention were not decisive
blockers.

**Final audit (2026-08-20):** Claude returned `NOT APPROVED`. The label
`v0.1.0-rc.1` is permanently retired and must not be reused. The deciding
blocker is the unexcepted high-severity `sharp <0.35.0` advisory. The Windows
and retention items were correctly disclosed but not independently blocking.
The release-note draft and this decision record were untracked working-tree
artifacts rather than files in the authorized SHA, so they could not serve as
source-grounded final-audit inputs. A later RC must include reviewed, committed
PR-005 artifacts and a fresh full hosted run.

## Remediation decision (new candidate required)

**Pre-implementation audit (2026-08-20):** Claude's final focused plan
re-review returned `NO BLOCKERS`. This authorizes only the remediation scope
below. It does not authorize a tag, RC identifier, release, publication,
deployment, runtime change, or reuse of `v0.1.0-rc.1`. A separate
source-grounded implementation audit is mandatory against the actual diff.

The retired candidate will not be amended, retagged, or re-audited. A new
candidate may be considered only after a narrowly scoped docs supply-chain
remediation, independently reviewed before implementation:

1. Update the direct `sharp` production dependency to `^0.35.3` and its
   lockfile resolution to `0.35.3`, using npm rather than hand-editing
   integrity data. GitHub Advisory `GHSA-f88m-g3jw-g9cj`, checked 2026-08-20,
   affects `<0.35.0`, lists `0.35.0` as patched, and recommends `0.35.3`.
2. Add a fail-closed production dependency vulnerability gate to the `docs`
   CI job immediately after `npm ci`, before browser installation/build/tests.
   The intended command is `npm audit --omit=dev --audit-level=high`; a
   critical or high production finding must fail the job. The audit must be a
   standalone `run` step with no `continue-on-error` (or an explicit `false`)
   and no `||`, `;`, or `&&` shell continuation after the command that could
   turn an audit failure into success. Its `run` body must not disable Bash
   error handling (`set +e`, `set +o errexit`, or an equivalent) and the step
   must not define `shell:` or `if:`; the job's default GitHub Actions Bash
   invocation is the required fail-closed shell contract. The `docs` job must
   also omit `continue-on-error` (or set it explicitly to `false`).
3. Extend the CI workflow-contract test to require that exact command and its
   placement in the docs job. It must reject removal, a lower audit level,
   loss of `--omit=dev`, placement after browser/build/test work,
   `continue-on-error: true`, shell success overrides, Bash error suppression,
   a step-level shell override, a step-level `if:`, and job-level
   `continue-on-error: true`. This makes future removal or weakening a tested
   regression.
4. Commit this decision record, the release-note template, remediation changes,
   and their tests together before any later final audit. No local untracked
   document is an exact-commit audit input.

This is a documentation build/CI supply-chain control only. It must not change
AutoPulse runtime diagnostic, replay, telemetry, VIN, logging, observability,
or offline-package behavior. No exception is proposed: an exception would need
an independent Claude approval, owner, rationale, mitigation, and expiry.

`--audit-level=high` is deliberate: it closes the high-severity production
dependency failure that retired the candidate while avoiding a new release gate
on lower-severity build-tool churn. `--omit=dev` deliberately scopes this gate
to installed production dependencies. A high-severity development-dependency
finding remains a documented residual risk; consider a separate future,
non-blocking all-dependency audit/report rather than silently treating this
production gate as exhaustive.

Primary sources for the remediation are GitHub's advisory
`https://github.com/advisories/GHSA-f88m-g3jw-g9cj` and npm's `npm audit`
documentation at `https://docs.npmjs.com/cli/v11/commands/npm-audit/`.

**License/platform spot-check (2026-08-21):** after `npm ci` on macOS x64,
the installed sharp package set reported `Apache-2.0` (`sharp` and
`@img/sharp-darwin-x64`), `MIT` (`@img/colour`), and `LGPL-3.0-or-later`
(`@img/sharp-libvips-darwin-x64`). This is the same license-family mix as the
prior sharp native package path; it is a targeted check, not an all-platform
Node SBOM/license gate.

**Implementation evidence (2026-08-21):** commit
`3b95c1623b6d526d76f76ef00028a91efa595f1f` updates `sharp` to `^0.35.3`,
adds the unconditional docs production audit gate, adds bypass-resistance
contract coverage, and adds committed PR-005 artifacts. Local Node 24.15.0 /
npm 11.17.0 checks passed: `npm ci`; production audit with zero findings; docs
build; smoke `6 passed, 2 skipped`; e2e `48 passed, 2 skipped`; and focused
CI-contract tests `3 passed`. The invalid nonfunctional `set -o +errexit`
matcher was removed before source audit. A remote source-grounded Claude audit
is still required; this evidence is not a new RC or release claim.

## Decision, provenance, and authority

This exercise validates the educational offline/replay package profile only;
it changes no runtime diagnostic, replay, telemetry, VIN, logging, or
observability behavior. The active-session user authorized this evidence-only
exercise, but not a tag, release, publication, deployment, or runtime change.
The planning baseline is
`origin/main` `81a157927fcacf4ae47716326885d12477e0002d` (PR #70 / PR-004),
not an RC. GitHub CLI verification also found Dependabot PRs #39, #42, and #45
closed. Re-check mutable GitHub/runner/advisory facts at execution time.

Before execution, record the user-authorized RC ID and its dereferenced,
immutable 40-character commit SHA (`git rev-parse "${RC_ID}^{commit}"`). The
SHA—not the mutable tag/ref—is the candidate identity. Immediately before the
hosted trigger, each local check, artifact/SBOM binder, release-note review,
and final audit, re-resolve the ID and fail closed unless it equals the
authorized SHA. Retained summaries name both; hosted `head_sha` must match.
Any mismatch halts the exercise and retires the RC ID under the failed-RC rule;
it is never a warning or a condition that local evidence may waive.

## Evidence matrix

| Gate | Required work | Sanitized retained evidence | Pass condition | Owner |
| --- | --- | --- | --- | --- |
| Provenance | Re-resolve `${RC_ID}^{commit}` before every consumer; inspect tag/ref and run | RC ID, authorized/re-resolved 40-hex SHA, workflow-run ID/URL, action SHA mapping | Each re-resolution and hosted `head_sha` equals authorized SHA | Codex |
| Package/replay boundary | One `release-gates` run: Ubuntu 24.04 x64, macOS 15 Intel/ARM64, Windows Server x64; CPython 3.13/3.14 | Allowlist summary and conclusion only | All eight cells build twice; archive validation, exact hashed prebuilt-wheel `--no-index` install, positive/negative probes, schema/CLI smoke, full tests, and `autopulse.live` absence pass | Actions/Codex |
| Privacy/red-line attestation | Named execution of `tests/test_debugging.py`, `tests/test_runtime_logging.py`, `tests/test_debug_cli_replay.py`, and `tests/test_us006_ev_adapter_security.py::test_forbidden_services_blocked` in every cell | Test IDs, pass/fail, aggregate count, exit status only | Every named test executes and passes; skips, collection/import failures, or absent attestations fail the cell. The last test blocks UDS SecurityAccess `0x27` in the offline validator surface. | Actions/Codex |
| Live seed-key/security-access exclusion | Existing `verify_release_cell.py` installed-wheel checks and archive allowlist | `autopulse.live` metadata/import absence and archive-policy result only | This is the sole intended offline-package control for live-adapter seed-key/security-access/capture paths: `autopulse.live` and its console entry point are absent, not skipped tests. Live-adapter tests are out of installed-package pytest scope. | Actions/Codex/Claude |
| Local reproduction | Approved native checks after re-review `NO BLOCKERS` and explicit RC authority | Fixed allowlist: check name, tool version, OS/Python major-minor, SHA, pass/fail, aggregate count, artifact hash where applicable, exit status | Diagnostic support only; never replaces hosted evidence or includes stdout/stderr | Codex |
| Supply chain | Per-cell SBOM/license/vulnerability/archive gates | CycloneDX binding values, approved license/vulnerability outcome, artifact checksums | Privacy scan, license policy, strict vulnerability and archive gates pass; critical/high finding blocks absent approved exception | Actions/Codex/Claude |
| CI security | Workflow-contract test and hosted release gates | Test conclusion and allowlist summary | Immutable pins, read-only permissions, fixed matrix, shell semantics, no privileged trigger/publish/deploy remain intact | Codex/Claude |
| Documentation | One `docs` job in the same run: `/autopulse/` build, smoke, regression, platform review | Conclusion, sanitized summary, platform-claim result | Build/base path/tests pass; no Pages write; docs claim no platform beyond evidence tier | Actions/Codex |
| Windows | Exact-commit public-doc/release-note review plus future native Windows 11 evidence | Claim result and required release-note sentence | Any Windows 11 claim blocks absent native evidence; note says: “Evidence covers Windows Server x64 only; this is not Windows 11 desktop validation.” | Maintainer/Codex/Claude |
| Release-note privacy | Prohibited-content scan/checklist over exact draft | Pass/fail and checklist version only | Reject private paths/URLs, VIN-like values, secrets, telemetry/payloads, fixture names, and raw commands | Codex/Claude |
| Scope certificate | Enumerate commits/diff from baseline `81a157927fcacf4ae47716326885d12477e0002d` through RC SHA; inspect imports/dependents of every changed module shared by offline and `autopulse.live` surfaces | Commit IDs/subjects, path categories, shared-module dependency result, scope certificate only | Final audit certifies no intervening direct or shared-module change alters runtime diagnostic, replay, telemetry, VIN, or logging/observability behavior | Codex/Claude |
| Independent audit | Claude pre-audit, then final source-grounded audit | Verdict, finding IDs/resolutions, scope statement | Re-audit `NO BLOCKERS` before execution; final sign-off after all mandatory hosted jobs pass | Claude |

The final source-grounded audit must additionally confirm the actual `ci.yml`
pytest invocation's treatment of `tests/live/` at the exact RC commit. This is
a non-blocking planning observation: no live-adapter assertion is relied upon
for installed-package evidence, but the final audit must not infer its scope
from a prior green CI run.

All eight cells and docs must be conclusions from one workflow run at the
authorized SHA. Any failure, cancellation, missing job, retry, flake, or
provenance mismatch invalidates the entire run; do not assemble piecemeal
results. A fresh full nine-job run is required. Any failed gate retires that RC
ID permanently: mark its sanitized status superseded; no binaries or raw logs
are retained in the repository. Issue a new RC ID and rerun from scratch.

## Release notes, retention, and stop conditions

The unpublished draft must name the RC ID/authorized SHA, support evidence
tier, offline local-fixture replay-only scope, no runtime network/telemetry,
prohibited live/capture/VIN/road/unattended/write/control/session/security/
deployment use, public API/CLI changes or none, security notes, limitations,
and upgrade/downgrade implications. It must include the exact Windows sentence
from the matrix and never claim Windows 11 without native evidence. Before
retention/circulation/final audit, apply the same prohibited-value patterns as
release evidence and a fixed no-raw-output checklist; matches or uncertainty
fail closed.

Retain only concise allowlist-built summaries, immutable IDs, checksums,
verdicts, and approved release-note text. Never commit wheelhouses, artifacts,
raw logs/reports, private paths/URLs, fixtures, telemetry, VIN-like values,
payloads, or secrets. Stop for missing authority, SHA mismatch, failed/missing
job, privacy/artifact failure, prohibited artifact, unexcepted critical/high
vulnerability, weakened Windows wording, audit blocker, or runtime-boundary
regression. Rollback is no release action and a recorded blocker; removal of a
later authorized tag/release needs separate user authorization. The repository
has no approved external evidence-retention policy: final audit must cite a
maintainer-approved location, access role, and deletion timeline, or external
retention remains blocked. No runtime observability change is warranted.

## Execution evidence (sanitized)

- Hosted run `32222492770` is a single successful push run at the authorized
  SHA. Eight release cells each report `647 passed`; docs reports smoke `6
  passed, 2 skipped` and regression `48 passed, 2 skipped`.
- Local isolated checkout: Node 24.15.0 build passed; smoke `6 passed, 2
  skipped`; regression `48 passed, 2 skipped`. Local CPython 3.11 is outside
  the support matrix, so no local package-cell result is claimed.
- Security blocker: exact-lockfile audit found one high-severity direct,
  non-development `sharp` advisory for `<0.35.0`; no approved exception exists.
- Windows wording: `docs/offline-package.md` correctly conditions Windows 11
  release support on native evidence. Hosted Windows Server results remain
  compatibility only; this did not independently block the audit.
- Retention: no maintainer-approved external evidence location, access role,
  and deletion timeline exists, so external retention remains fail-closed; this
  did not independently block the audit.

**Auditability lesson:** final-audit inputs must be committed in the candidate
commit (or otherwise made available through an approved immutable source
mechanism) before audit. Local untracked drafts are not evidence for an exact
commit.

The unpublished release-note draft is
`docs/release-notes/v0.1.0-rc.1-draft.md`; the final audit packet is
`docs/prompts/claude-pr-005-release-candidate-final-audit.md`.

## Required sequence

1. Planning audit is complete: Claude returned `NO BLOCKERS` for
   `docs/prompts/claude-pr-005-release-candidate-pre-audit-rereview-2.md`.
2. Obtain explicit user authority for an exact RC ID and 40-character SHA.
3. Re-verify provenance at every consumer; collect only one complete hosted
   run and approved local evidence for that SHA; draft but never publish notes.
4. Create a final-audit packet containing the exact ID/SHA, baseline-bounded
   diff certificate, evidence, hashes, note text, limitations, and resolutions.
   No readiness statement or external release action precedes final sign-off.
