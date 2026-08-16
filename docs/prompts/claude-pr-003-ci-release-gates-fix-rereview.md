# Claude — PR-003 corrected-contract fix re-review

You are AutoPulse's independent Lead Auditor. This is a **pre-implementation
fix re-review** of PR-003, following your 2026-08-14 `MINOR FIXES` verdict.
No workflow, dependency, runtime, schema, release, or publication change has
been made or is authorized by this review.

Claude Chat has **no repository, GitHub, or filesystem access** for this
request. Treat every statement and excerpt below as the complete review packet;
do not request local files or infer facts not supplied here. You may check
fast-changing public GitHub facts on the web, but keep those findings separate
from AutoPulse policy decisions.

AutoPulse is an educational offline/replay package. Do not authorize live
capture, adapter discovery, VIN reads/storage, telemetry upload, diagnostic
writes/control, UDS session/security access, or road/unattended operation.
Passing this review would authorize PR-003 CI/documentation implementation
only. It is neither release approval nor Windows 11 desktop validation.

## Prior verdict and corrections to review

Your prior findings were:

1. **MF-01 (High):** Linux/macOS required gates could omit `pipefail`.
2. **MF-02 (High):** Windows native-command failure propagation depended on
   runner PowerShell defaults.
3. **MF-03 (Medium):** summary sanitization could devolve into unsafe
   raw-output redaction.
4. **MF-04 (Low/Medium):** nothing enforced the Windows Server / Windows 11
   evidence disclaimer.
5. **MF-05 (Low):** the docs verification base path was hardcoded separately
   from the committed docs configuration.

The revised contract resolves them as follows:

- Every Linux/macOS matrix job must set `defaults.run.shell: bash`; required
  gates may not override it with a shell that omits `-o pipefail`.
- Every Windows matrix gate step that invokes a native command must begin with
  `$ErrorActionPreference = 'Stop'` and
  `$PSNativeCommandUseErrorActionPreference = $true`. Required gates may not
  use `continue-on-error` or convert a non-zero native exit status to success.
- The sanitized summary must be constructed by a CI helper from an explicit
  allowlist only: Python/OS/architecture, selected wheel filenames and
  SHA-256s, package wheel/sdist SHA-256s, commit SHA, and per-gate pass/fail.
  It must never scrape, copy, or redact raw stdout/stderr. Inputs are validated
  before summary creation.
- The Windows summary and job name must contain the literal statement that the
  server-runner result is compatibility evidence, **not Windows 11 desktop
  validation**. A static test must prove that it cannot silently disappear.
- The non-deploying docs verification job must run `npm ci` and the normal
  Starlight build with no CLI `site` or `base` overrides. The committed
  `grubby-galaxy/astro.config.mjs` is its source of truth and sets
  `site: 'https://ajason13.github.io'` and `base: '/autopulse/'`.
- Each matrix cell must run an offline-install test with its package index
  unreachable/disabled and succeed only from the staged local wheelhouse.
- Build-time network access for pinned tooling is distinct from the offline
  runtime/replay guarantee; the requirement concerns the installed product's
  staged-wheelhouse installation.

## Complete corrected contract

### Scope and boundaries

PR-003 converts PR-002 packaging controls into deterministic, fail-closed
GitHub Actions evidence and validates public documentation under `/autopulse/`.
It may modify GitHub Actions workflows, CI-only scripts/tests, documentation
checks, and sanitized CI summaries. It must not publish packages or a release
candidate, widen the support matrix, add self-hosted runners, create a
networked runtime, or change any live-vehicle, privacy, or diagnostic boundary.

The support profile is CPython 3.13/3.14 on Ubuntu 24.04 x86_64, macOS 15 Intel,
macOS 15 Apple Silicon, and Windows 11 x86_64. No release-ready claim is
allowed until every applicable gate has evidence. Hosted Windows Server runner
results can never prove the Windows 11 desktop promise.

### Untrusted-PR workflow rules

- Trigger verification only on `pull_request` and ordinary pushes; prohibit
  `pull_request_target`, `workflow_run`, secrets, environments, deployment
  credentials, repository-write tokens, self-hosted runners, publish, and
  deploy steps.
- Set top-level `permissions: { contents: read }`; jobs receive no more.
- Pin every third-party action to a verified 40-character commit SHA with an
  adjacent readable release/tag comment. Dependabot may propose, never approve,
  workflow updates.
- Use explicit runner labels, never `*-latest`. Concurrency may cancel obsolete
  pull-request runs but must not blend, overwrite, or publish evidence from a
  different commit SHA.
- Cache is optional download acceleration only and never integrity evidence;
  hash and artifact validation run on every cell.

### Required eight-cell matrix

| Runner | Python | Meaning |
| --- | --- | --- |
| `ubuntu-24.04` | 3.13, 3.14 | Native supported Linux evidence |
| `macos-15-intel` | 3.13, 3.14 | Native supported Intel macOS evidence |
| `macos-15` | 3.13, 3.14 | Native supported Apple-Silicon evidence |
| Exact current Windows x64 server label, never `*-latest` | 3.13, 3.14 | Python-wheel/workflow compatibility evidence only; not Windows 11 validation |

Every cell must, in order:

1. check out the tested commit using an immutable action pin and install the
   exact CPython minor and PR-002 pinned build/tooling environment;
2. validate the committed lock and produce a fully pinned SHA-256-hashed
   requirements view without direct URLs, editable dependencies, or sdists;
3. build sdist and wheel twice under controlled `SOURCE_DATE_EPOCH`; run
   `twine check --strict`, `check-wheel-contents`, and the AutoPulse archive
   validator on actual artifacts;
4. create a prebuilt-wheel-only wheelhouse; run positive clean installation,
   tampered-hash, incomplete-wheelhouse, and unreachable/disabled-index offline
   probes through `verify_release_cell.py`; and fail on every failed probe;
5. run schema-resource, public-CLI/offline-boundary, packaging-policy, and full
   Python tests, failing the job on any failure;
6. generate and validate CycloneDX 1.6 SBOM, license reports, and strict
   vulnerability evidence from the installed environment; and
7. emit only the allowlist-built summary, with no raw logs, fixtures,
   wheelhouse, paths, environment dump, credentials, VIN-like values, or
   telemetry. No release artifact is published.

### Documentation and Pages rules

The non-deploying docs job runs on PRs and ordinary pushes with `npm ci`, the
normal committed-config Starlight build, and existing smoke plus regression
Playwright suites against the built preview. It checks that generated output
and internal routes remain under `/autopulse/`; it has neither Pages-write nor
deployment credentials and does not deploy a preview.

The existing Pages deployment workflow is hardened in this task by SHA-pinning
actions, but retains `pages: write` and `id-token: write` only for deployment.
It continues to use `configure-pages` output for its production origin/base
path and must not substitute a hardcoded production URL.

### Required implementation-time static/adversarial tests

Tests must fail if they cannot prove all of the following: 40-hex action pins
with readable version comments; read-only permissions and forbidden triggers;
exactly the eight named non-`*-latest` cells; Bash pipefail; Windows native
error handling; all positive/negative/offline probes in every cell; allowlist
summary construction; cache non-evidence; concurrency SHA isolation; retained
Windows disclaimer; and config-derived docs build/base-path validation.

## Required re-review questions

1. Are MF-01 through MF-05 genuinely closed by explicit, implementable,
   fail-closed requirements and required tests?
2. Does the new offline-index probe cover an important bypass without wrongly
   claiming CI itself is network-free?
3. Is the split between committed docs config for verification and
   `configure-pages` output for deployment coherent and free of a source-of-
   truth drift gap?
4. Do any remaining requirements allow an implementer to obtain a green check
   while masking a shell/native failure, leaking raw content in a summary, or
   treating Windows Server evidence as Windows 11 proof?
5. Identify only genuinely new blockers or minor fixes, with an exact section,
   bypass/failure mode, and correction.

## Required response format

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**.
For every finding, include severity, exact contract section, realistic bypass,
and concrete correction. State explicitly whether PR-003 implementation may
begin. Do not claim a public-release approval or Windows 11 validation.
