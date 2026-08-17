# Claude — Adversarial QA Plan: PR-003 CI Release Gates and Documentation Assurance

You are AutoPulse’s independent Lead Auditor. This is a **pre-implementation contract review**. No CI workflow, dependency, runtime, schema, release, or publication change is authorized by this review. The project is an educational offline/replay package: do not authorize live capture, adapter discovery, VIN reads/storage, telemetry upload, diagnostic writes/control, UDS session/security access, or road/unattended operation.

Claude Chat has no repository, GitHub, or filesystem access for this request. Assess the exact supplied files below. Separate sourced GitHub facts from AutoPulse policy decisions. Challenge ways an implementer could satisfy a job name or green check while bypassing the intended offline, privacy, reproducibility, and least-privilege boundaries.

## Required review questions

1. Is the eight-cell plan technically coherent with GitHub-hosted runner labels and the CPython 3.13/3.14 support profile?
2. Does it avoid silently treating Windows Server runner evidence as Windows 11 desktop proof?
3. Are event triggers, permissions, action pinning, cache use, artifacts/logs, and shell failure behavior fail-closed for untrusted PRs?
4. Does every required PR-002 evidence step actually have a credible CI enforcement path, including wheel-only installs, negative hash/missing-wheel probes, and sanitization?
5. Does the docs job validate the `/autopulse/` deployed base path without deployment credentials on pull requests?
6. Name the most important adversarial workflow/static tests that must exist before implementation.

## Required verdict

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. For each finding give severity, exact contract/file reference, realistic bypass/failure mode, and a concrete correction. State whether PR-003 implementation may begin. Do not claim a public-release approval or a Windows 11 validation.

## Exact current `docs/specs/pr-003-ci-release-gates-and-docs-assurance.md`

```markdown
# PR-003: CI Release Gates and Documentation Deployment Assurance

**Status:** Codex-owned pre-implementation contract.  
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
- GitHub's built-in `bash` and `pwsh` shells propagate failures with their
  documented fail-fast defaults; a workflow should still avoid masking failures
  with `continue-on-error` in a required gate. [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
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
sanitized summary. It must never upload a wheelhouse, raw fixture, raw test log,
private path, environment dump, credential, VIN-like value, or telemetry.

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
   incomplete-wheelhouse probes. No step may turn a failed probe into success.
5. Run the schema-resource, public-CLI/offline-boundary, packaging-policy, and
   complete Python test suites. A failure stops the job.
6. Generate and validate the CycloneDX 1.6 SBOM, license reports, and strict
   vulnerability report from the exact installed environment; run privacy scans
   before creating any retained summary.
7. Emit only the approved sanitized summary. It may be a job summary or a
   short retained text artifact only after a PR-004 retention decision; no
   release artifact is published in PR-003.

Cache use is optional and may improve download speed only. A cache hit is never
accepted as proof of dependency integrity: hash verification and artifact
validation run on every cell.

### Documentation assurance

PR-003 must add a non-deploying documentation job on pull requests and pushes.
It uses `npm ci` from the committed `package-lock.json`, builds the Starlight
site with `site=https://ajason13.github.io` and `base=/autopulse/`, and runs the
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
3. Matrix summaries are sanitized and accurately label the Windows x64 runner
   as compatibility evidence rather than Windows 11 desktop validation.
4. The docs verification job runs `npm ci`, build, smoke, and regression tests
   at `/autopulse/` without Pages write permissions; a broken base-path link or
   build fails the job.
5. The Pages workflow keeps deployment permissions restricted to deployment,
   pins external actions, and builds with `configure-pages` output.
6. Workflow-focused adversarial tests or static checks prove pins, permissions,
   forbidden triggers, expected matrix cells, required gate commands, and the
   docs base-path invocation cannot be silently removed.
7. Claude reviews the implementation and CI results. Passing CI on hosted
   Windows does not close the separate Windows 11 release-evidence gap.

## Implementation sequence

1. Claude reviews this contract and supplies adversarial QA findings.
2. Codex resolves any blockers in this contract; Claude re-reviews if needed.
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
```

## Exact current `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: Python tests
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r requirements.txt

      - name: Syntax check
        run: |
          python -m py_compile \
            src/autopulse/data/validator.py \
            src/autopulse/analysis/circular_buffer.py \
            src/autopulse/analysis/hdf_detector.py \
            src/autopulse/analysis/osf_detector.py \
            src/autopulse/analysis/pdm_processor.py \
            src/autopulse/analysis/utils.py \
            tests/simulation/virtual_replay.py \
            tests/simulation/__init__.py \
            src/autopulse/adapters.py \
            src/autopulse/providers.py \
            src/autopulse/noise.py \
            src/autopulse/replayer.py \
            src/autopulse/__init__.py \
            src/autopulse/alert_exporter.py

      - name: Run US-001 tests
        run: python -m pytest tests/test_engine_data_contract.py -q

      - name: Run US-002 tests
        run: python -m pytest tests/test_us002_virtual_replay_harness.py -q

      - name: Run US-003 tests
        run: python -m pytest tests/test_us003_pdm_algorithms.py -q

      - name: Run US-004 tests
        run: python -m pytest tests/test_us004_smoothing.py -q

      - name: Run US-005 tests
        run: python -m pytest tests/test_us005_alert_exporter.py -q
```

## Exact current `.github/workflows/deploy-docs.yml`

```yaml
name: Deploy Starlight to Pages

on:
  # Trigger the workflow on push to the main branch
  push:
    branches: [main]
    # Only run if files in the docs directory change
    paths:
      - 'grubby-galaxy/**'
      - '.github/workflows/deploy-docs.yml'

  # Allows you to run this workflow manually from the Actions tab
  workflow_dispatch:

# Sets permissions of the GITHUB_TOKEN to allow deployment to GitHub Pages
permissions:
  contents: read
  pages: write
  id-token: write

# Allow only one concurrent deployment, skipping runs queued between the run in-progress and latest queued.
# However, do NOT cancel in-progress runs as we want to allow these production deployments to complete.
concurrency:
  group: 'pages'
  cancel-in-progress: false

env:
  BUILD_PATH: './grubby-galaxy' # default value when not using subfolders

jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v6
      - name: Detect package manager
        id: detect-package-manager
        run: |
          if [ -f "${{ github.workspace }}/grubby-galaxy/package-lock.json" ]; then
            echo "manager=npm" >> $GITHUB_OUTPUT
            echo "command=ci" >> $GITHUB_OUTPUT
            echo "runner=npx --no-install" >> $GITHUB_OUTPUT
            exit 0
          else
            echo "Unable to determine package manager"
            exit 1
          fi
      - name: Setup Node
        uses: actions/setup-node@v6
        with:
          node-version-file: ${{ env.BUILD_PATH }}/.nvmrc
          cache: ${{ steps.detect-package-manager.outputs.manager }}
          cache-dependency-path: ${{ env.BUILD_PATH }}/package-lock.json
      - name: Setup Pages
        id: pages
        uses: actions/configure-pages@v6
      - name: Install dependencies
        run: ${{ steps.detect-package-manager.outputs.manager }} ${{ steps.detect-package-manager.outputs.command }}
        working-directory: ${{ env.BUILD_PATH }}
      - name: Build with Astro
        run: |
          ${{ steps.detect-package-manager.outputs.runner }} astro build \
            --site "${{ steps.pages.outputs.origin }}" \
            --base "${{ steps.pages.outputs.base_path }}"
        working-directory: ${{ env.BUILD_PATH }}
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v5
        with:
          path: ${{ env.BUILD_PATH }}/dist

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v5
```

## Exact current `grubby-galaxy/astro.config.mjs`

```javascript
// @ts-check
import { defineConfig } from 'astro/config';
import mermaid from 'astro-mermaid';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://ajason13.github.io',
	base: '/autopulse/',
	integrations: [
		mermaid({
			autoTheme: true,
		}),
		starlight({
			title: 'AutoPulse Docs',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/ajason13/autopulse' }],
			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting Started', slug: 'guides/getting-started' },
						{ label: 'Stationary Smoke Test', slug: 'guides/stationary-smoke-test' },
						{ label: 'Example Guide', slug: 'guides/example' },
					],
				},
				{
					label: 'Specs',
					items: [{ autogenerate: { directory: 'specs' } }],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Architecture Overview', slug: 'reference/architecture' },
						{ label: 'Anomaly Detection', slug: 'reference/anomaly-detection' },
						{ label: 'Empirical Validation', slug: 'reference/empirical-validation' },
					],
				},
			],
		}),
	],
});
```


