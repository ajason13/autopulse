# Claude Chat prompt — PR-005 release-candidate pre-implementation audit

You are AutoPulse’s independent Lead Auditor (Claude Sonnet 4.6). Perform a
**pre-implementation audit** of the proposed release-candidate evidence
exercise. This is a planning review: no RC tag, GitHub Release, publication,
deployment, package release, runtime change, or release-readiness claim is
authorized by this prompt. Claude Chat may not have repository, GitHub, or
Notion access; assess the complete context supplied here.

## Required verdict

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**.
For every finding, give severity, the exact section/table row below, the
realistic bypass or failure mode, and a concrete correction. State explicitly
whether the RC exercise may begin *only after* (a) your `NO BLOCKERS` verdict
and (b) an active-session user authorizes an exact RC identifier/tag. Do not
approve a public release, tag, deployment, or Windows 11 support claim.

## Authority and current state

- The active-session user has supplied **no** exact RC identifier/tag or
  release-action authorization. No execution may occur yet.
- Planning baseline only: `origin/main`
  `81a157927fcacf4ae47716326885d12477e0002d`, PR #70 (PR-004) merged.
  Dependabot PRs #39, #42, and #45 are closed. This baseline is not an RC.
- Before any execution, the approved RC ID must resolve to exactly one full
  commit. Every local check, hosted run, artifact binding, release-note draft,
  and final-audit input must identify that exact pair.

## Product and safety boundaries

AutoPulse’s release profile is an educational, local, offline/replay package
for previously supplied sanitized JSON/JSONL/CSV fixtures. It is read-only and
must not authorize live adapters, vehicle capture, VIN reads/storage,
telemetry upload, road testing, unattended monitoring, OBD-II/UDS writes or
control, DTC clearing, session escalation, security access, seed-key material,
or proprietary payload capture. The offline package deliberately excludes
`autopulse.live`; it has only the sanitized `autopulse-debug` console command.
No runtime diagnostic, replay, telemetry, VIN, logging, or observability
behavior changes are in scope.

Never retain or publish wheelhouses, wheels/sdists, raw logs, raw scan reports,
fixtures, absolute local paths, private URLs, VIN-like values, telemetry/raw
payloads, credentials, or secrets. Evidence must be concise and allowlist-built
rather than redacted raw output.

## Inherited controls that must remain intact

- PR-001 requires clean installation on every supported cell; full and
  Claude-selected tests; schema/security/privacy regression checks; locked,
  hash-verified dependencies; license, vulnerability, SBOM and privacy scans;
  artifact-content allowlisting; documentation/release limitations; and final
  independent audit.
- PR-002 requires a reproducible sdist/wheel, package-resource schema loading,
  absent `autopulse.live`, offline hashed/prebuilt-wheel installation, positive
  and negative install probes, deterministic archive policy, CycloneDX 1.6
  SBOM bound to commit/wheel/wheelhouse-manifest hashes, strict vulnerability
  scan, and fail-closed license policy.
- PR-003 requires eight hosted release cells: Ubuntu 24.04 x64, macOS 15
  Intel, macOS 15 ARM64, and Windows Server x64, each on CPython 3.13 and
  3.14; plus a non-deploying docs build/smoke/regression check at `/autopulse/`.
  CI is `pull_request`/ordinary `push` with `contents: read`, fixed runners,
  full-SHA action pins, explicit Bash/pwsh failure behavior, and no privileged
  trigger, secrets, self-hosted runner, publication, or deployment.
- PR-004 pins checkout v7.0.1 to
  `3d3c42e5aac5ba805825da76410c181273ba90b1`, setup-python v7.0.0 to
  `5fda3b95a4ea91299a34e894583c3862153e4b97`, and setup-node v7.0.0 to
  `820762786026740c76f36085b0efc47a31fe5020`. Its hosted evidence passed all
  eight release cells plus docs, but that evidence is not an RC exercise.

## Workflow/test excerpts

The current `ci.yml` `release-gates` job uses a fixed eight-cell matrix:

```yaml
- { runner: ubuntu-24.04, python: '3.13', label: ubuntu-x64, shell: bash }
- { runner: ubuntu-24.04, python: '3.14', label: ubuntu-x64, shell: bash }
- { runner: macos-15-intel, python: '3.13', label: macos-intel, shell: bash }
- { runner: macos-15-intel, python: '3.14', label: macos-intel, shell: bash }
- { runner: macos-15, python: '3.13', label: macos-arm64, shell: bash }
- { runner: macos-15, python: '3.14', label: macos-arm64, shell: bash }
- { runner: windows-2025, python: '3.13', label: windows-server-x64, shell: pwsh,
    windows_note: ' — compatibility evidence, not Windows 11 desktop validation' }
- { runner: windows-2025, python: '3.14', label: windows-server-x64, shell: pwsh,
    windows_note: ' — compatibility evidence, not Windows 11 desktop validation' }
```

Each cell installs pinned release/dev requirements, downloads only binary
wheels into a cell wheelhouse, builds twice with `SOURCE_DATE_EPOCH=0`, runs
`verify_release_cell.py` against the wheel/sdist/wheelhouse/hashed
requirements, runs the complete Python suite, and invokes
`generate_supply_chain_evidence.py` with `--commit ${{ github.sha }}`.
That verifier validates archive allowlists; clean `--no-index`,
`--require-hashes`, `--only-binary=:all:` installation; installed schema/CLI
smoke; `autopulse.live` absence; and tampered-hash/incomplete-wheelhouse
negative probes. Supply-chain generation validates CycloneDX 1.6, binds commit
and SHA-256 values, scans evidence for private paths/URLs, validates licenses,
runs strict `pip-audit`, `twine check --strict`, and `check-wheel-contents`.
The docs job runs committed Starlight configuration, build, smoke, and
regression checks at `/autopulse/` without Pages-write permission.

The workflow-contract test enforces full action SHA/comment mappings, read-only
permissions, permitted triggers, fixed matrix, shell error semantics, release
gates, allowlist summary construction, literal Windows disclaimer, and docs
base-path/permission boundaries.

## Proposed evidence and release-note plan

| Area | Required evidence and pass condition |
| --- | --- |
| RC provenance | Authorized ID resolves to one commit; all evidence belongs to it. |
| Hosted package gates | Every one of eight cells passes; retain IDs/URLs, conclusions, and allowlist summary only. |
| Hosted docs gate | The exact-commit docs job passes build, base-path, smoke, and regression. |
| Local checks | Run only after audit/authority; record sanitized aggregate outcome; never substitute for hosted evidence. |
| Supply chain/artifacts | Per cell all SBOM, license, vulnerability, archive, hash, and privacy gates pass; retain only allowed identifiers/checksums/outcomes. |
| Windows | State Windows Server compatibility only. Separate native Windows 11 evidence remains mandatory while Windows 11 is promised. |
| Release notes | Draft only; list exact RC, scope, supported/evidence status, known limits, public API/CLI changes or none, security/upgrade notes, and prohibited uses. |
| Final audit | After evidence exists, a second source-grounded packet must give exact RC/commit, diff, all local/hosted evidence, artifact identifiers, release-note text, limitations, and resolutions. |

## Audit questions

1. Is the provenance/RC-tag authority rule sufficient to prevent a stale,
   retagged, or mismatched commit from being treated as the candidate?
2. Does the evidence matrix cover every PR-001–PR-004 clean-install, package,
   replay-boundary, docs, security, SBOM/license/vulnerability, and artifact
   control without treating local evidence as hosted evidence?
3. Can a retained summary or release-note workflow leak artifacts, paths,
   telemetry, VIN-like identifiers, or secrets? What exact restriction is
   missing if so?
4. Is the eight-cell matrix adequate for its stated supported cells, and is
   the Windows Server versus Windows 11 limitation unambiguous and blocking?
5. Could the proposed process regress immutable action-pin, permissions,
   shell, offline-install, package-exclusion, docs base-path, or no-runtime-
   observability controls from PR-001–PR-004?
6. Identify any mandatory stop/rollback condition or final-audit input that is
   absent.
