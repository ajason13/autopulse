# Codex prompt — repair Dependabot pip CI and prepare safe consolidation

You are Codex, the accountable AutoPulse builder and release-gate operator.
Address the shared CI failure on the currently open Dependabot pip pull
requests and prepare the safe path to merge their updates. This is dependency,
lockfile, CI-evidence, and governance work only.

## Verified starting facts (2026-08-25)

Start from current `origin/main` and re-verify every mutable fact before
changing files. The following Dependabot PRs are open:

| PR | Intended update |
| --- | --- |
| #71 | `jsonschema >=4.23,<5` → `>=4.26.0,<5` |
| #72 | `pytest >=9,<10` → `>=9.1.1,<10` |
| #73 | `uv ==0.11.32` → `==0.12.5` |
| #74 | `hatchling ==1.31.0` → `==1.32.0` |
| #75 | `twine ==6.2.0` → `==7.0.0` |

Each Dependabot PR updates its matching project/requirements declaration but
does not update `uv.lock`. Docs CI passes, while all eight package cells fail
at the fail-closed command:

```text
python -m uv export --locked --all-extras --no-emit-project \
  --format requirements-txt --output-file .ci-requirements.txt
error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.
```

The failure is expected evidence of declaration/lock inconsistency. It is not
permission to remove `--locked`, create the lock in CI, skip package cells, or
weaken any offline-install, archive, SBOM/license/vulnerability, or test gate.

## Authority and hard boundaries

- Do **not** merge, close, rebase, label, or comment on Dependabot PRs unless
  the active-session user explicitly authorizes that external action.
- Do **not** create a tag, release, publication, deployment, or Windows 11
  claim. `v0.1.0-rc.1` remains retired.
- Do **not** change AutoPulse runtime diagnostics, OBD-II/UDS permissions,
  replay semantics, telemetry/VIN handling, logging, CLI behavior, or
  observability. Preserve offline educational/replay-only and `autopulse.live`
  exclusion boundaries.
- Never retain raw logs, private paths, tokens, VIN-like values, payload bytes,
  or seed/key/security-access material in committed evidence.
- Preserve unrelated dirty and untracked files. Work on a branch from current
  `origin/main`; do not reset or restore user work.

## Mandatory audit gate

Before implementation, locate a recorded independent Claude `NO BLOCKERS`
verdict for the plan in
`docs/prompts/claude-dependabot-pip-lockfile-ci-remediation-pre-audit.md` or
obtain one through the user. If no such verdict exists, stop after preparing
the complete pre-audit packet and report the gate as blocked. Do not infer
approval from this prompt or from passing docs CI.

## Approved implementation scope after that gate

1. Create one maintainer-owned consolidation branch from current `origin/main`.
   Reproduce the five exact intended Dependabot declaration updates together:
   `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, and
   `requirements-release.txt` must remain mutually consistent.
2. Bootstrap the resolver deliberately: install/use the intended `uv 0.12.5`
   in a clean environment, record the exact tool version and command, then
   regenerate `uv.lock`. Never hand-edit lock entries, URLs, markers, or
   hashes.
3. Inspect the lock diff semantically. Allow only changes explained by the five
   declared updates and their resolver-required transitive/metadata changes.
   Investigate and reject unrelated version upgrades, source changes, removed
   packages, unexpected marker/platform changes, or manually fabricated
   integrity data.
4. Add focused regression coverage if existing tests do not directly fail when
   declared dependency inputs and `uv.lock` disagree. The test must exercise
   the real locked export/check behavior, not merely assert that CI text
   contains `--locked`.
5. Run targeted local checks first, including the real locked export plus the
   appropriate package/supply-chain checks. Then run broader tests in
   proportion to the lockfile/toolchain blast radius. Retain only concise,
   allowlist-built results.
6. Create a self-contained Claude implementation-audit prompt with the exact
   commit, complete diff manifest, resolver version/command, lock-diff
   explanation, test outcomes, and security boundaries. Do not claim merge
   readiness before its source-grounded verdict.
7. After Claude sign-off, push the consolidation branch and collect one fresh,
   single-trigger GitHub-hosted run tied to its exact head SHA. All eight
   package cells and docs must pass; Windows Server is compatibility evidence
   only, not Windows 11 evidence. A cancelled, partial, retried, or
   mixed-commit run is invalid.

## Safe merge sequence (requires separate user authority)

When every preceding gate passes and the active-session user explicitly says
to merge:

1. Reconfirm the consolidation PR head SHA and its full hosted run are exact.
2. Reconfirm Claude's final source-grounded verdict and all required checks.
3. Merge **only** the maintainer-owned consolidation PR.
4. Recheck `main` and the merge commit.
5. Only with explicit user authorization, close Dependabot PRs #71–#75 as
   superseded, each with a concise reference to the consolidation PR. Do not
   merge the stale individual Dependabot PRs after consolidation.
6. Update `CONTEXT.md`, the relevant decision/audit record, and Notion with
   the merged SHA, hosted evidence, audit verdict, and no-runtime-change
   confirmation.

## Required handoff

Report:

- current Dependabot PR IDs, SHAs, and exact failure cause;
- whether the independent pre-audit gate exists, or the precise blocker;
- changed files and a semantic lock-diff summary;
- resolver tool/version/command and local verification results;
- exact hosted run URL/SHA and its nine-job matrix state;
- Claude audit locations/verdicts;
- whether any external merge/closure authority is still missing; and
- explicit confirmation of no runtime/observability change.
