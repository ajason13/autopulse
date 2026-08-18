# Claude Chat prompt — PR-004 GitHub Actions v7 pre-implementation audit

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). Perform a
**pre-implementation adversarial review**. Claude Chat has no filesystem,
GitHub, or Notion access: treat this prompt as the complete authoritative
review packet.

## Required verdict

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**.
For every finding provide severity, affected requirement/file, realistic bypass
or failure mode, and a concrete correction. Explicitly state whether Codex may
edit the workflows. Challenge SHA provenance, v7 runner compatibility,
shell/permission regressions, test adequacy, and interaction with PR-003.
Do not claim hosted evidence or final merge approval at this stage.

## Proposed mapping and provenance

On 2026-08-17 Codex resolved official GitHub repository tags with:
`git ls-remote https://github.com/actions/<repository>.git 'refs/tags/v7*'`.
The selected exact release commits are:

| Action | Release | Proposed immutable SHA | Previous reviewed SHA |
| --- | --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` | `d23441a48e516b6c34aea4fa41551a30e30af803` (`v6`) |
| `actions/setup-python` | `v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | `ece7cb06caefa5fff74198d8649806c4678c61a1` (`v6`) |
| `actions/setup-node` | `v7.0.0` | `820762786026740c76f36085b0efc47a31fe5020` | `249970729cb0ef3589644e2896645e5dc5ba9c38` (`v6`) |

Only these pins and adjacent readable comments would change, after this audit.
Dependabot PRs #39/#42/#45 are not a provenance source and their mutable tags
will not be merged or copied.

## Non-negotiable contract

- Every `uses:` must remain a 40-character SHA plus adjacent release comment;
  no `@v7`, `@main`, tag-only, or shortened SHA.
- CI stays `pull_request`/ordinary push only, `contents: read`, no secrets,
  privileged trigger, deployment, or self-hosted runner.
- Retain explicit fixed runner labels, Bash `pipefail`, Windows `pwsh` and
  native-error handling, offline packaging gates, allowlist-built summaries,
  Windows disclaimer, and docs base-path verification.
- Pages retains only its existing Pages-specific credentials and must keep
  `configure-pages` origin/base-path output wiring.
- No OBD/UDS/replay/telemetry/VIN/runtime behavior changes and no
  runtime-observability change.

## Relevant current workflow excerpts

`ci.yml` currently has `on: pull_request` and `push` to main, top-level
`permissions: contents: read`, eight explicit runner matrix entries
(`ubuntu-24.04`, `macos-15-intel`, `macos-15`, `windows-2025` for Python 3.13
and 3.14), and these pins:

```yaml
- uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
- uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
# docs job
- uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
- uses: actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38 # v6
```

Linux/macOS release gates use `shell: bash`; Windows gates use `shell: pwsh`
and begin with `$ErrorActionPreference = 'Stop'` and
`$PSNativeCommandUseErrorActionPreference = $true`. The docs job runs `npm ci`,
`npx playwright install --with-deps chromium`, `npm run build`,
`npm run test:smoke`, and `npm run test:e2e` from `grubby-galaxy`.

`deploy-docs.yml` has `permissions: contents: read`, `pages: write`, and
`id-token: write`; currently pins checkout/setup-node to the v6 SHAs above;
retains full-SHA configure/upload/deploy Pages actions; and builds with:

```yaml
npx --no-install astro build \
  --site "${{ steps.pages.outputs.origin }}" \
  --base "${{ steps.pages.outputs.base_path }}"
```

## Proposed test rule

Replace the current checkout-only assertion
`actions/checkout@[0-9a-f]{40} # v6` with a positive mapping that demands the
exact proposed 40-hex SHA and exact adjacent `# v7.0.x` comment for every
relevant use in both workflow files. Preserve assertions for forbidden
privileged events, least privilege, fixed runners/eight cells, Bash/pwsh
semantics, release/offline gates, allowlist summary, Windows disclaimer,
deploy full-SHA pins, and committed/docs Pages base-path wiring. The test must
fail for mutable tags, a shortened SHA, missing/wrong comment, and any other
full SHA.

## Rollback

Restore only the immediate previous full SHA in the mapping table with its
`# v6` comment, rerun static checks and affected hosted jobs, and never use a
mutable reference.
