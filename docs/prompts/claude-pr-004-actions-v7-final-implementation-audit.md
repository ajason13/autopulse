# Claude Chat prompt — PR-004 GitHub Actions v7 final implementation audit

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). Perform a
**source-grounded final implementation audit** for this narrow CI supply-chain
change. Claude Chat has shell/network access in this session: verify the pinned
commit provenance and inspect the listed files at the provided commit SHA when
available. Do not rely only on this summary.

## Required verdict

Return exactly one verdict: **APPROVED FOR PR-004 MERGE**,
**APPROVED WITH MINOR FIXES**, or **NOT APPROVED**. Give severity-ranked,
file-specific findings; confirm whether MF-01 through MF-03 are resolved; and
separately state whether the remaining hosted evidence is sufficient. Do not
approve a production release or claim Windows 11 desktop validation.

## Authorized scope and immutable mapping

Only these workflow lines changed, together with `tests/packaging/test_ci_workflow_contract.py`, this decision/audit documentation, and project status
records:

| Action | Required release comment | Required SHA | Required occurrences |
| --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | 3 |
| `actions/setup-python` | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | 1 |
| `actions/setup-node` | `v7.0.0` | `820762786026740c76f36085b0efc47a31fe5020` | 2 |

The three commits were source-verified by the pre-implementation audit as the
respective lightweight official action v7 tags. No mutable `@v7`, branch,
tag-only, or shortened reference is allowed.

## Contract that must remain intact

- CI: `pull_request` and ordinary `push` only; `contents: read`; no secrets,
  `pull_request_target`, `workflow_run`, self-hosted runner, or deployment.
- Preserve fixed eight-cell CI runner matrix, Bash/pwsh failure behavior,
  offline packaging gates, allowlist-built summary, and literal Windows
  compatibility-not-Windows-11 wording.
- Preserve docs CI base-path verification and no Pages write permission.
- Preserve Pages action pins, scoped Pages credentials, and
  `configure-pages` origin/base-path output wiring.
- No runtime OBD/UDS/replay/telemetry/VIN behavior or observability changes.

## Required auditor findings and implementation response

- **MF-01:** The test now asserts exactly six total approved target-action
  occurrences: checkout 3, setup-python 1, setup-node 2. It verifies exact
  SHA plus exact adjacent v7 release comment and fails a missing, extra, old,
  mutable, abbreviated, wrong-comment, or unapproved occurrence.
- **MF-02:** The test isolates the setup-python step and rejects a
  `pip-install:` input, removed in setup-python v7.
- **MF-03:** The existing test still explicitly checks literal
  `pull_request_target` and `workflow_run` absence; verify this directly.

The pre-audit disclosed pre-existing `ubuntu-latest` in `deploy-docs.yml`; it
is intentionally out of PR-004 scope and must be recorded as deferred, not
silently fixed here.

## Local evidence

- `git diff --check` passed.
- `PYTHONPATH=src python3 -m pytest tests/packaging/test_ci_workflow_contract.py -q` -> `2 passed`.
- `PYTHONPATH=src python3 -m pytest -q` -> `647 passed in 18.31s`.
- In `grubby-galaxy`: `npm run build` passed; `npm run test:smoke` ->
  `6 passed, 2 skipped`; `npm run test:e2e` -> `48 passed, 2 skipped`.

Hosted evidence is still required: all eight `release-gates` cells and the
docs job must pass on the PR. A green local result is not a substitute.
