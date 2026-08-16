# PR-003: CI Release Gates and Documentation Deployment Assurance

**Status:** Claude-approved pre-implementation contract; CI/documentation implementation authorized.  
**Parent decisions:** PR-001 offline release profile and PR-002 packaging/supply-chain contract.  
**Checked:** 2026-08-14.

## Purpose and scope

PR-003 converts the PR-002 packaging controls into deterministic, fail-closed
GitHub Actions evidence and validates the public documentation at its deployed
`/autopulse/` base path. It may modify GitHub Actions workflows, CI-only helper
scripts/tests, documentation checks, and sanitized CI evidence summaries.

It does not publish packages, deploy a release candidate, widen the supported
matrix, add a self-hosted runner, create a networked runtime, or authorize any
live vehicle/adapter workflow, VIN read, capture, upload, diagnostic write, or
UDS control operation. GitHub Pages deployment remains limited to the existing
documentation workflow; PR-003 does not make a production/release claim.

## Current baseline

- `.github/workflows/ci.yml` runs only CPython 3.11 on `ubuntu-latest`, uses
  mutable major action tags, and installs the un-hashed development
  `requirements.txt` from the network.
- `deploy-docs.yml` uses mutable action tags, correctly scopes Pages write and
  ID-token permissions to its deployment workflow, and builds with the Pages
  origin/base-path outputs.
- PR-002 now supplies PEP 621/Hatchling packaging, `uv.lock`, archive/privacy
  checks, clean wheelhouse installation verification, and macOS x86_64 local
  evidence for CPython 3.13 and 3.14. It does not supply all native cells.
- The intended profile is CPython 3.13/3.14 on Ubuntu 24.04 x86_64, macOS 15
  Intel and Apple Silicon, and Windows 11 x86_64. No release-ready claim is
  permitted until every applicable gate has evidence.

## External findings, checked 2026-08-14

- GitHub requires `runs-on` to choose a runner, and a strategy matrix is the
  supported mechanism for running a job on multiple machines. GitHub-hosted
  jobs receive fresh runner instances. The published standard labels include
  `ubuntu-24.04`, `macos-15-intel`, `macos-15` (arm64), and Windows x64
  `windows-2025`/`windows-2022`. [GitHub runner selection](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
- GitHub says a full-length commit SHA is currently the only immutable action
  reference and recommends minimum `GITHUB_TOKEN` permissions. It warns against
  combining untrusted checkout with privileged `pull_request_target` or
  `workflow_run`. [GitHub secure use](https://docs.github.com/en/actions/reference/security/secure-use)
- An unspecified Linux/macOS shell uses `bash -e`, which does not enable
  `pipefail`; an explicit `shell: bash` uses `bash --noprofile --norc -eo
  pipefail`. Windows native-command failure propagation depends on PowerShell
  configuration and version, so the workflow must set it explicitly rather
  than rely on runner defaults. [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- Cache restoration is not release integrity evidence: cache keys may use
  prefix/restore-key matching, and cache content must remain untrusted input.
  [GitHub dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)

These are external facts. The following requirements are AutoPulse policy
decisions.

## Approved CI architecture

### Workflow separation and events

1. Keep untrusted-code verification on `pull_request` and ordinary pushes only;
   do not use `pull_request_target`, `workflow_run`, repository-write tokens,
   secrets, environments, or deployment credentials in the release-gate
   workflow.
2. Set top-level `permissions: { contents: read }`; every job inherits no more
   than that. Retain the existing Pages deployment workflow as the sole workflow
   needing `pages: write` and `id-token: write`, scoped to deployment jobs.
3. Pin every third-party action to a verified 40-character commit SHA with an
   adjacent readable release/tag comment. Dependabot may update those pins by
   pull request; it never self-approves a workflow change.
4. Use explicit runner labels, never `*-latest`, for release-quality matrix
   evidence. Workflow `concurrency` may cancel obsolete pull-request runs but
   must not blur, overwrite, or publish evidence from a different commit.
5. Every Linux/macOS matrix job must set `defaults.run.shell: bash`; required
   gate steps may not override it with a shell that omits `-o pipefail`.
   Every Windows matrix gate step must explicitly use `shell: pwsh`, must not
   switch to `shell: cmd` or `shell: bat`, and must begin with
   `$ErrorActionPreference = 'Stop'` and
   `$PSNativeCommandUseErrorActionPreference = $true`. Required gates may not
   use `continue-on-error` or convert a non-zero native exit status to success.
   This prevents multi-line `cmd`/`bat` blocks from reporting only their last
   command's exit status.

### Matrix and evidence tiers

The matrix has eight required compatibility cells:

| OS/architecture | CI runner label | Python minors | Evidence meaning |
| --- | --- | --- | --- |
| Ubuntu 24.04 x86_64 | `ubuntu-24.04` | 3.13, 3.14 | Native supported Linux evidence |
| macOS 15 Intel | `macos-15-intel` | 3.13, 3.14 | Native supported Intel macOS evidence |
| macOS 15 Apple Silicon | `macos-15` | 3.13, 3.14 | Native supported Apple-Silicon evidence |
| Windows x64 | `windows-2025` or the exact current supported x64 label selected at implementation | 3.13, 3.14 | Python-wheel and workflow compatibility evidence only; it is **not** proof of the Windows 11 desktop support promise |

The Windows distinction is intentional. GitHub's listed standard Windows x64
labels are server images, while the profile promises Windows 11. PR-003 must
not relabel server evidence as Windows 11 validation. The lead must either
obtain separate native Windows 11 evidence under a later approved mechanism or
change the public profile through a new policy decision. Self-hosted runners
are out of scope because PR execution on persistent runners changes the threat
model.

Each matrix job must expose the exact Python/OS/architecture, selected wheel
filenames and SHA-256s, package wheel/sdist SHA-256s, and commit SHA in a
sanitized summary. The summary must be assembled from an explicit allowlist of
those fields by the CI helper, not by copying, scraping, or redacting command
stdout/stderr. It must never upload a wheelhouse, raw fixture, raw test log,
private path, environment dump, credential, VIN-like value, or telemetry.
The Windows summary and job name must include the literal statement that its
server-runner result is compatibility evidence, **not Windows 11 desktop
validation**.

### Required job stages

Every matrix cell fails closed and performs, in this order:

1. Check out the tested commit using an immutable action pin; install the exact
   CPython minor and the PR-002 pinned build/tooling environment.
2. Validate the committed lock and produce the cell's fully pinned,
   SHA-256-hashed requirements view without permitting direct URLs, editable
   dependencies, or source distributions.
3. Build the sdist and wheel twice under controlled `SOURCE_DATE_EPOCH`; run
   `twine check --strict`, `check-wheel-contents`, and the AutoPulse archive
   validator on the actual artifacts.
4. Create a matching wheelhouse from only prebuilt wheels. Run the PR-002
   `verify_release_cell.py` positive clean install and its tampered-hash and
   incomplete-wheelhouse probes, plus an offline-install probe with the package
   index unreachable/disabled to prove the install uses only the local
   wheelhouse. No step may turn a failed probe into success.
5. Run the schema-resource, public-CLI/offline-boundary, packaging-policy, and
   complete Python test suites. A failure stops the job.
6. Generate and validate the CycloneDX 1.6 SBOM, license reports, and strict
   vulnerability report from the exact installed environment. Validate every
   value selected for the sanitized-summary allowlist before summary creation;
   do not use privacy scanning/redaction of raw command output as the mechanism
   that makes a summary safe.
7. Emit only the approved allowlist-built summary. It may be a job summary or a
   short retained text artifact only after a PR-004 retention decision; no
   release artifact is published in PR-003.

Cache use is optional and may improve download speed only. A cache hit is never
accepted as proof of dependency integrity: hash verification and artifact
validation run on every cell.

### Documentation assurance

PR-003 must add a non-deploying documentation job on pull requests and pushes.
It uses `npm ci` from the committed `package-lock.json`, then invokes the normal
Starlight build without CLI `site` or `base` overrides. The committed
`grubby-galaxy/astro.config.mjs` is the verification job's single source of
truth for `site=https://ajason13.github.io` and `base=/autopulse/`. It runs the
existing smoke and regression Playwright suites against the built preview.
The job checks generated output and internal routes remain beneath
`/autopulse/`. It does not require Pages write permissions or deploy a preview.

The existing Pages workflow is hardened separately in this task by SHA-pinning
its actions and retaining its narrowly scoped deployment permissions. Its build
must continue to use `configure-pages` output for origin/base path; PR-003 must
not replace it with a hard-coded production URL.

## Acceptance criteria

1. The untrusted PR workflow has read-only contents permission, no secrets,
   no privileged trigger, no self-hosted runners, no publish/deploy step, and
   every external action is pinned to a reviewed full SHA.
2. Eight matrix jobs run the required PR-002 build, wheel-only/offline install,
   archive, hash-negative, schema, privacy, SBOM, license, vulnerability, and
   full-test gates. Missing prebuilt wheels, lock/hash mismatch, attempted
   network during offline install, or missing required evidence fails the cell.
3. Matrix summaries are allowlist-built and accurately label the Windows x64
   runner as compatibility evidence rather than Windows 11 desktop validation;
   a static test asserts that literal disclaimer is retained in the summary and
   job-name construction.
4. The docs verification job runs `npm ci`, build, smoke, and regression tests
   at `/autopulse/` without Pages write permissions; a broken base-path link or
   build fails the job.
5. The Pages workflow keeps deployment permissions restricted to deployment,
   pins external actions, and builds with `configure-pages` output.
6. Workflow-focused adversarial tests or static checks prove: full-SHA action
   pins plus readable version comments; read-only permissions and forbidden
   triggers; exactly the eight named non-`*-latest` cells; explicit Bash
   pipefail and explicit `pwsh` (with no `cmd`/`bat`) Windows native-error
   handling; every required/negative/offline probe; allowlist-only summary
   generation; cache non-evidence; concurrency
   SHA isolation; the Windows disclaimer; and the config-derived docs build.
   They must fail if any required property is silently removed.
7. Claude reviews the implementation and CI results. Passing CI on hosted
   Windows does not close the separate Windows 11 release-evidence gap.

## Implementation sequence

1. Claude reviews this contract and supplies adversarial QA findings.
2. Codex resolves audit findings in this contract; Claude re-reviews the
   corrected, self-contained contract before implementation begins.
3. Implement CI-only scripts/tests and workflows, pinning SHAs only after
   verifying their repositories and releases at implementation time.
4. Run local workflow/static validation plus targeted Python/docs tests; open a
   pull request and collect the real hosted matrix evidence.
5. Claude performs implementation audit. Record results and deferred native
   Windows 11 evidence in Notion/CONTEXT. PR-005, not PR-003, decides release
   candidate exercise and publication readiness.

## Weak claims and unresolved decisions

- GitHub-hosted runner availability, image contents, action SHAs, and Python
  patch versions change; resolve and record their exact values at implementation
  time, not in this planning document.
- The repository's visibility/billing and availability of the macOS Intel/ARM
  labels must be confirmed before enabling all eight jobs.
- A hosted Windows server runner cannot prove Windows 11 behavior. The safe
  evidence mechanism for that remaining desktop claim needs a later approved
  decision; self-hosted PR runners are expressly not the default answer.
- Retention/upload of sanitized CI summaries awaits PR-004. The default is job
  summaries only, with no binary or raw-log publication.
- Exact workflow linter and dependency-export command remain implementation
  choices, provided they enforce this contract and add no unreviewed runtime
  dependency.
- Build-time network access for pinned tooling/dependencies is distinct from
  the offline runtime/replay product boundary. The required offline-install
  probe must prove that the installed package works from its staged wheelhouse,
  not that CI itself runs without network access.
