# PR-004: audited GitHub Actions v7 SHA-pin upgrade

**Status:** Claude-approved for PR-004 merge; local and hosted gates passed.
**Checked:** 2026-08-17.
**Scope:** GitHub Actions supply-chain references only; no AutoPulse runtime, diagnostic, telemetry, replay, VIN, or observability behavior changes.

## Decision

Replace the approved v6 pins for `actions/checkout`, `actions/setup-python`,
and `actions/setup-node` with the following full Git object IDs. Each target
was resolved directly from the official `refs/tags/v7*` namespace with
`git ls-remote` on 2026-08-17. The workflow comments must name the specific
release; no `@v7`, branch, tag-only, or abbreviated reference is permitted.

| Action | Selected upstream release | Immutable commit SHA | Replaces reviewed pin |
| --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `d23441a48e516b6c34aea4fa41551a30e30af803` (`v6`) |
| `actions/setup-python` | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | `ece7cb06caefa5fff74198d8649806c4678c61a1` (`v6`) |
| `actions/setup-node` | `v7.0.0` | `820762786026740c76f36085b0efc47a31fe5020` | `249970729cb0ef3589644e2896645e5dc5ba9c38` (`v6`) |

The GitHub action repositories are the provenance source, not Dependabot PRs
#39, #42, or #45. The full commit SHA makes the workflow reference immutable
even if an upstream major tag is later changed.

## Compatibility and security assumptions

Claude source verification on 2026-08-17 established that the current reviewed
v6 pins already use Node 24 (checkout since v6.0.0; setup-python and setup-node
at their current v6 pins). V7's ESM migration therefore introduces no new
runner-runtime prerequisite for AutoPulse. The eight hosted release-gate cells
and docs job remain the authoritative compatibility evidence for this exact
upgrade.

No action inputs, event triggers, runner labels, shell settings, permissions,
cache policy, packaging gates, summaries, or Pages build configuration change.
CI remains `pull_request`/ordinary `push` with `contents: read`, no secrets or
privileged trigger, and no self-hosted runner. The Pages workflow retains its
narrow `pages: write` and `id-token: write` credentials and its
`configure-pages` origin/base-path outputs.

## Required static and adversarial checks

`tests/packaging/test_ci_workflow_contract.py` uses a positive approved mapping
for every PR-004 target occurrence in both workflows: checkout exactly three
times, setup-python exactly once, and setup-node exactly twice. Each occurrence
must be exactly `action@<approved 40-hex SHA> # v7.0.x`; a mutable tag,
abbreviated SHA, missing/wrong comment, old SHA, unapproved SHA, missing
occurrence, or extra occurrence fails the test. The setup-python step must not
contain the removed v7 `pip-install` input. The test retains PR-003 coverage
for:

1. forbidden `pull_request_target` and `workflow_run`, read-only CI
   permission, fixed runner labels, and exactly eight release matrix cells;
2. explicit Bash and PowerShell semantics, including `pipefail`, `pwsh`, and
   native PowerShell failure handling;
3. release/offline gates, allowlist-built summaries, and the literal Windows
   server compatibility disclaimer;
4. docs CI's committed base-path build and no Pages write permission; and
5. deploy workflow full-SHA pins, Pages permission scope, and
   `configure-pages`-derived origin/base path.

Verification before PR creation is `git diff --check`, targeted workflow
contract tests, the relevant complete Python suite, and Starlight build plus
smoke/regression suites. A green local run does not replace the required eight
hosted release cells and docs job.

## Rollback

If a v7 action fails an approved hosted cell or introduces an action-specific
regression, restore only the immediately previous reviewed full-SHA pin from
the table above in the affected workflow(s), retain its adjacent `# v6` comment,
rerun static checks and the affected hosted jobs, and record the reason in the
PR/Notion task. Do not fall back to a mutable reference.

## Observability and scope boundary

This changes workflow dependency provenance only. It creates no runtime
execution path, operator action, diagnostic interaction, data collection, or
failure mode inside AutoPulse; therefore no runtime-observability change is
needed. Hosted Actions logs remain the existing CI observability surface.

## Audit gate

Claude's 2026-08-17 pre-implementation review returned `MINOR FIXES`, with no
blocker and explicit authority for the six approved pin changes and associated
tests. MF-01 (exhaustive occurrence coverage) and MF-02 (`pip-install` guard)
are incorporated above; MF-03 is confirmed by the existing literal
`pull_request_target` and `workflow_run` assertions. The self-contained packet
is `docs/prompts/claude-pr-004-actions-v7-preimplementation-audit.md`.

Claude also disclosed a pre-existing, out-of-scope Pages deployment concern:
`deploy-docs.yml` uses floating `ubuntu-latest` runner labels. PR-004 must not
change runner labels; track it as a separate infrastructure decision before a
future runner-image migration.

## Hosted verification

GitHub Actions run `32108791619`, tied to PR head
`dc2fe632a535a4d4bedc7aacc0f17e7db5bf53ca`, passed the docs job and all eight
required release-gate cells: Ubuntu 24.04 x64 (CPython 3.13/3.14), macOS 15
ARM64 (3.13/3.14), macOS 15 Intel (3.13/3.14), and Windows Server x64
(3.13/3.14). The Windows results remain compatibility evidence only, not
Windows 11 desktop validation.

## Final audit

Claude's final source-grounded implementation audit returned
`APPROVED FOR PR-004 MERGE`, contingent on independently confirming hosted
evidence. The auditor verified the six permitted workflow-line changes,
adversarially exercised the MF-01/MF-02/MF-03 negative paths, and found no
out-of-scope source changes. Codex independently confirmed the current-head
run and its nine successful job conclusions above, satisfying that contingency.
