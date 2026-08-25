# Claude Chat prompt — Dependabot pip lockfile CI remediation and merge plan

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). Review this
**pre-implementation** plan to repair the failing CI on the five open
Dependabot pip pull requests and to merge their dependency updates safely.

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKED**.
This review authorizes no code change, lockfile rewrite, workflow relaxation,
Dependabot-PR merge, closure, tag, release, publication, deployment, or
runtime behavior change.

## Current primary-source state (checked 2026-08-25)

`main` is `66d36623e44d649d7206a2998a7f41aa79fd5a1f`. PR #77 is merged.
The following Dependabot PRs are open, and their `docs` jobs pass but all eight
package/release cells fail:

| PR | Proposed update | Files changed by Dependabot |
| --- | --- | --- |
| #71 | `jsonschema >=4.23,<5` → `>=4.26.0,<5` | `pyproject.toml`, `requirements.txt` |
| #72 | `pytest >=9,<10` → `>=9.1.1,<10` | `pyproject.toml`, `requirements-dev.txt` |
| #73 | `uv ==0.11.32` → `==0.12.5` | `pyproject.toml`, `requirements-release.txt` |
| #74 | `hatchling ==1.31.0` → `==1.32.0` | `pyproject.toml`, `requirements-release.txt` |
| #75 | `twine ==6.2.0` → `==7.0.0` | `pyproject.toml`, `requirements-release.txt` |

Representative failure, independently read from PR #71's Ubuntu 24.04 /
CPython 3.13 job `32443226831`:

```text
error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.
hint: To update the lockfile, run `uv lock`.
Process completed with exit code 2.
```

Every package cell executes this fail-closed sequence after installing the
release and development requirements:

```yaml
python -m uv export --locked --all-extras --no-emit-project \
  --format requirements-txt --output-file .ci-requirements.txt
python -m pip download --only-binary=:all: --dest .ci-wheelhouse \
  -r .ci-requirements.txt
# deterministic build, archive validation, offline install, supply-chain
# evidence, and complete pytest suite follow
```

The current workflow uses read-only `contents: read` permissions, pinned action
SHAs, the eight supported release cells (Ubuntu x64, macOS Intel/ARM64, and
Windows Server x64; CPython 3.13/3.14), and a separate docs job. Windows Server
evidence is compatibility evidence only, not Windows 11 validation.

## Proposed maintainer-owned remediation and merge strategy

Do **not** merge any of PRs #71–#75 as currently constituted, and do not make
CI pass by removing `--locked`, generating a lockfile during CI, skipping
release cells, weakening package/SBOM/license/vulnerability/archive checks, or
using `continue-on-error`.

Instead, after this review returns `NO BLOCKERS`:

1. Create one maintainer-owned consolidation branch from the then-current
   `origin/main`. Apply the five exact intended Dependabot updates together,
   preserving the matching `requirements*.txt`/`pyproject.toml` declarations.
   Do not add unrelated dependency upgrades.
2. Regenerate `uv.lock` with the approved resolved `uv` tool version in a clean
   environment. Record the exact resolver command/tool version and inspect the
   resulting lock diff for unrelated version, marker, source, or integrity
   drift. Do not hand-edit hashes or lock records.
3. Add focused regression coverage for declaration/lock consistency if the
   existing tests do not already make this stale-lock failure explicit. The
   test must fail if any declared dependency update leaves `uv.lock` stale;
   it must not merely test that CI contains the `--locked` token.
4. Run the approved local dependency/package checks and obtain one fresh
   GitHub-hosted, single-trigger run in which docs and all eight package cells
   pass at the exact consolidation commit. Local success is not a substitute
   for hosted evidence.
5. Obtain a source-grounded Claude implementation audit covering the exact
   diff, resolver evidence, lockfile scope, local/hosted results, and all
   release-gate invariants.
6. Only after that audit and all hosted checks pass, merge the maintainer-owned
   consolidation PR. Then close the five Dependabot PRs as superseded with a
   concise reference to the merged consolidation PR. Do not merge the stale
   individual Dependabot PRs afterwards.

If `main` moves before consolidation, rebase/recreate from the new `main`,
re-resolve the lock, and rerun the full hosted matrix. Do not reuse evidence
from a different commit.

## Scope and security boundaries

This is dependency/lockfile/CI evidence work only. It must not alter AutoPulse
runtime diagnostic behavior, OBD-II/UDS service permissions, replay semantics,
telemetry handling, VIN handling, logging, CLI behavior, or observability.
Preserve the offline educational/replay-only package boundary, the exclusion of
`autopulse.live`, and the prohibition on raw VIN-like values, payload bytes,
private paths, secrets, seed/key material, or security access in retained
evidence. No tag, release, publication, deployment, or Windows 11 claim is in
scope.

## Questions for review

1. Is a single maintainer-owned consolidation PR the safe merge path, or is
   there a concrete reason to retain a different ordering? Identify any
   dependency compatibility or resolver-bootstrap concern, especially around
   upgrading `uv` while regenerating `uv.lock`.
2. Does this plan preserve the intended fail-closed meaning of `uv export
   --locked` and the inherited PR-001 through PR-005 package/supply-chain
   controls? Identify any way the consolidation could make CI green while
   weakening reproducibility or offline-install evidence.
3. What exact lock-diff allowlist and local checks are necessary to distinguish
   expected resolver changes from accidental broad churn or a manual lock edit?
4. What focused regression test(s), if any, should be required for the
   declaration-to-lock consistency failure?
5. Are the proposed hosted matrix, exact-SHA binding, audit, and closure steps
   sufficient before merging and superseding the individual Dependabot PRs?
6. Identify blockers, required test cases, and any documentation/Notion status
   updates that must accompany implementation.

Do not treat a green docs job, a local check, or the previously merged PR-005
remediation as sufficient evidence for any package cell. Return a
severity-ranked rationale and an explicit statement whether the plan is ready
for implementation.
