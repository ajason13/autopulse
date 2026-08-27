# Claude re-review — Dependabot pip lockfile CI remediation plan

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). This is a
**pre-implementation follow-up review**. The prior review returned `MINOR
FIXES`; this packet incorporates every finding. Review the amended plan and
return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKED**.

This review authorizes no dependency or lockfile change, CI change, branch
push, pull-request merge/closure/comment, tag, release, publication,
deployment, Windows 11 claim, or runtime behavior change. Implementation may
start only after your explicit `NO BLOCKERS` verdict is recorded.

## Authoritative current state

On 2026-08-27, `origin/main` is
`6232f651e4887eb84645fc285e744b9cbad458da` (PR #78, docs-only). The earlier
planning baseline `66d36623...` is stale by this documentation-only commit;
all implementation work must instead begin from the then-current `origin/main`
and re-verify it before editing.

Open Dependabot PRs #71–#75 each change only `pyproject.toml` and its matching
requirements file:

| PR | Declared update | Declaration file besides `pyproject.toml` |
| --- | --- | --- |
| #71 | `jsonschema >=4.23,<5` → `>=4.26.0,<5` | `requirements.txt` |
| #72 | `pytest >=9,<10` → `>=9.1.1,<10` | `requirements-dev.txt` |
| #73 | `uv ==0.11.32` → `==0.12.5` | `requirements-release.txt` |
| #74 | `hatchling ==1.31.0` → `==1.32.0` | `requirements-release.txt` |
| #75 | `twine ==6.2.0` → `==7.0.0` | `requirements-release.txt` |

The workflow's eight supported package cells retain the fail-closed sequence
`python -m uv export --locked --all-extras --no-emit-project ...`,
`pip download --only-binary=:all:`, deterministic archive construction,
archive/offline-install/supply-chain checks, and full pytest. Its docs job is
separate. Do not relax or bypass any of those gates.

`uv.lock` has no `hatchling` package record because `hatchling` is only in
`[build-system].requires`; it also currently contains no `.tar.bz2`,
`.tar.xz`, or MD5-only integrity references. The existing CI workflow-contract
tests do not run a real declaration-to-lock consistency check.

## Prior audit findings and incorporated corrections

1. **Baseline correction:** The plan uses the current SHA above and requires a
   fresh branch from current `origin/main`, never a Dependabot branch. The
   individual Dependabot branches are stale and must not be rebased/merged.
2. **uv 0.12 bootstrap/format boundary:** Use a clean environment containing
   exactly `uv 0.12.5`; record `python -m uv --version` and the exact resolver
   command. Regenerate only by `python -m uv lock` (no manual lock edits).
   After regeneration, explicitly fail the local evidence checklist if the
   lock contains `.tar.bz2`, `.tar.xz`, or non-SHA-256-or-stronger hashes.
   Confirm `requirements-release.txt` makes the CI-side `python -m uv export
   --locked` invoke `uv 0.12.5`, then run that actual command twice to prove
   locked-export success and idempotency.
3. **Per-PR cause verification and test design:** Before choosing the focused
   regression coverage, obtain authenticated GitHub Actions evidence (or retain
   a sanitized, complete job table) for each of #71–#75. Record the first
   failing step and its exact category. Do not assert that every PR failed at
   locked export: #74 can validly bypass that check because its build-system
   requirement is not tracked in `uv.lock`. If #74 has a downstream failure,
   identify it before implementation and add only the narrow coverage needed
   for that mechanism. For lock-managed declarations, add a real subprocess
   test of the committed `pyproject.toml`/`uv.lock` pair using `uv export
   --locked` (or `uv lock --check`), not a text assertion about workflow YAML.
   Separately verify the build backend actually used by the package build is
   the updated exact `hatchling==1.32.0` value.
4. **Twine 7 validation:** Because `twine==7.0.0` changes metadata validation
   implementation, the local and hosted evidence must explicitly report a
   clean `twine check --strict` for the constructed wheel and sdist. Green
   status alone is insufficient.

## Approved plan if and only if this re-review is `NO BLOCKERS`

1. Create one maintainer-owned consolidation branch from current `origin/main`.
   Apply exactly the five declared updates while preserving parity among
   `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, and
   `requirements-release.txt`.
2. Prepare a concise decision record under `docs/specs/` that records the
   fresh baseline, the five updates, the separate build-system-versus-lockfile
   treatment, the resolver command/version, semantic lock allowlist, and all
   security boundaries. Do not include raw logs, local paths, secrets,
   VIN-like values, diagnostic payloads, or security-access material.
3. Regenerate `uv.lock` only with `uv 0.12.5` as above. Semantically review the
   diff: permit direct changes for `jsonschema`, `pytest`, `uv`, and `twine`,
   plus named transitive changes directly forced by a documented upstream
   constraint. Treat `hatchling` as outside the lock allowlist and validate it
   through the build-backend evidence. Reject unexplained package version,
   source, marker/platform, removal, URL, or integrity drift.
4. Run the focused declaration-lock test, real locked export twice, build
   backend verification, strict Twine archive validation, and retained
   package/supply-chain checks; then run the broader relevant suite. No
   runtime diagnostic, replay, telemetry, VIN, logging, CLI, or observability
   change is in scope. Preserve the offline educational/replay-only and
   `autopulse.live`-exclusion boundaries.
5. Prepare an implementation-audit packet with exact head SHA, full changed
   file manifest, resolver evidence, per-PR failure table, semantic lock diff,
   local outcomes, and all scope/security constraints. Obtain source-grounded
   Claude approval before pushing or claiming merge readiness.
6. Only after audit approval, push and require one fresh, single-trigger
   exact-head hosted run with docs plus all eight package cells passing.
   Windows Server is compatibility-only evidence, never a Windows 11 claim.
   Merge and closure require separate active-session user authorization.

## Review questions

1. Do the corrections completely resolve the uv 0.12 format/integrity,
   build-system-versus-lockfile, and Twine 7 validation concerns?
2. Is the requirement to classify each PR's actual first failing CI step before
   test design sufficiently precise and fail-closed?
3. Is the semantic lock-diff allowlist appropriately narrow without making
   normal resolver-required metadata changes impossible to review?
4. Are the focused checks, implementation audit, exact-head hosted matrix,
   and authorization boundaries sufficient before a consolidation PR can be
   proposed?
5. Identify any remaining blocker, required negative test, or documentation
   requirement. State explicitly whether implementation may begin.

