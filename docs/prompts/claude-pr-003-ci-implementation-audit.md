# Claude — PR-003 CI and documentation implementation audit

You are AutoPulse's independent Lead Auditor. Review the **implementation** of
PR-003 against its previously Claude-approved pre-implementation contract. This
is not public-release approval and does not establish Windows 11 desktop
validation. Hosted Windows evidence remains only wheel/workflow compatibility
evidence.

Claude Chat has **no filesystem, GitHub, or Notion access**. Everything needed
for this audit is included below. Do not assume unprovided files exist.

## Scope and non-negotiable boundaries

This educational offline/replay project must not add live capture, VIN handling,
telemetry upload, diagnostic control, UDS access, self-hosted runners, secrets,
privileged workflow triggers, publish steps, or deployment from untrusted PRs.
The release-gate workflow must use read-only `contents` permission, full-SHA
action pins, explicit runners, prebuilt-wheel/offline install evidence,
sanitized allowlist-only evidence, and fail-closed shells. A separate Pages
workflow may retain narrowly scoped deployment permissions.

## Implemented `ci.yml` summary

- `pull_request` and `push` to `main` only; `permissions: contents: read`.
- Eight matrix cells: `ubuntu-24.04`, `macos-15-intel`, `macos-15`, and
  `windows-2025`, each on CPython 3.13 and 3.14. Windows job names carry the
  literal “compatibility evidence, not Windows 11 desktop validation”.
- `actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803` and
  `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1` are pinned
  as v6 full SHAs; docs uses pinned checkout and setup-node.
- Linux/macOS gates use `shell: bash`; Windows gates use `shell: pwsh` plus
  `$ErrorActionPreference = 'Stop'` and
  `$PSNativeCommandUseErrorActionPreference = $true`.
- Each gate installs release/dev tooling, performs `uv export --locked` with
  hashes, downloads prebuilt wheels only, builds two artifact sets, invokes
  `verify_release_cell.py`, installs the local package, invokes
  `generate_supply_chain_evidence.py`, then runs `pytest -q`.
- Docs runs `npm ci`, `npm run build`, `npm run test:smoke`, and
  `npm run test:e2e` from `grubby-galaxy`; it does not pass `--site`/`--base`
  overrides and has no Pages permission.

## New allowlist summary helper

`scripts/emit_ci_summary.py` accepts a source summary, exact 40-hex commit,
and output path. It accepts only lines matching these named fields: cell,
CPython, install/probe/archive/schema/CLI/live-absence results, AutoPulse
wheel/sdist hashes, wheelhouse manifest hash, and wheel filename/hash lines.
It rejects the entire source if any bullet is outside that allowlist, then emits
only the commit and selected lines. It never reads command stdout/stderr.

## Static regression tests

`tests/packaging/test_ci_workflow_contract.py` asserts forbidden privileged
triggers are absent; read-only permissions; exactly eight runners; `pwsh` and
absence of `cmd`/`bat`; summary/verifier helpers; full-SHA checkout pin; Windows
disclaimer; docs build without `--base`; pinned configure-pages; and no
floating deploy action tags.

## Pages hardening

`deploy-docs.yml` preserves its existing `contents: read`, `pages: write`, and
`id-token: write` deployment permission boundary, but pins checkout/setup-node,
configure-pages, upload-pages-artifact, and deploy-pages to full SHAs. Its
production build continues to consume `configure-pages` origin/base output.

## Local verification evidence

- `python3 -m pytest tests/packaging/test_ci_workflow_contract.py
  tests/packaging/test_release_cell_verifier.py
  tests/packaging/test_packaging_policy.py -q` → **35 passed**.
- `npm run build` in `grubby-galaxy/` → passed.
- `git diff --check` → passed.
- The full suite could not receive a single final result in this execution
  environment: the command session repeatedly stopped around 38–39% while
  executing timing-heavy US-002 replay tests. Independent coverage did pass:
  all non-US-002 tests (**402 passed**), all US-006 tests (**134 passed**), and
  the isolated apparent interruption point
  `TestLogReplayer1Hz::test_1hz_no_interval_exceeds_tolerance` (**1 passed in
  8.13s**). Treat the remainder of US-002 and all hosted matrix evidence as
  outstanding, not passed.

## Required audit response

Return exactly one verdict: **APPROVED FOR PR-003 MERGE**,
**APPROVED WITH MINOR FIXES**, or **NOT APPROVED**. Rank findings by severity
with exact affected behavior. Explicitly assess: shell semantics on both OS
families, source-of-truth/base-path correctness, action pinning, offline probe
coverage, summary allowlist adequacy, full-suite evidence gap, and whether the
workflow can accidentally retain raw/private artifacts. State whether the
implementation may advance to hosted CI evidence. Do not authorize a release
or claim Windows 11 validation.
