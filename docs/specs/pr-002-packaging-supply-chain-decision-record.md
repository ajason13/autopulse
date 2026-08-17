# PR-002: Packaging and Supply-Chain Implementation Decision Record

**Status:** Codex-owned implementation contract; Claude's 2026-08-13 re-review returned `NO BLOCKERS` and authorized PR-002 implementation.  
**Parent policy:** docs/specs/pr-001-offline-release-profile-and-threat-model.md.  
**Checked:** 2026-08-13.

## Scope and boundary

PR-002 will make AutoPulse installable as a local, educational offline/replay package. It may change Python package metadata, dependency installation inputs, schema-resource loading required by an installed package, build/support scripts, tests, and documentation. It must not add live adapters, vehicle capture, VIN reads, uploads, analytics, write-capable diagnostics, CI workflow changes, or release publication.

The repository has a src package but no pyproject metadata, lock, package build, SBOM, or release artifact. requirements.txt is unpinned and lists pandas, numpy, and python-dotenv even though source imports do not currently use them. Their removal or reclassification requires tested evidence; they are not carried into runtime metadata without a documented use.

## Approved design

| Concern | Decision |
| --- | --- |
| Build backend | PEP 621 pyproject metadata with Hatchling, static PEP 440 version, Python >=3.13,<3.15, and reproducible builds. Use python -m build so the wheel is built from the sdist. |
| Package contents | Explicitly include the offline autopulse modules and exclude autopulse/live/** plus any live-only module from the wheel and sdist. The installed offline wheel must make import autopulse.live fail. Build exactly one pure-Python wheel and one sdist. Root schemas remain canonical; the build stages byte-identical copies as package resources. |
| Installed schema loader | Rewrite autopulse.data.validator to remove its repository-relative SCHEMA_PATH/EV_SCHEMA_PATH lookup and eager file opening. Its only production schema source is packaged data loaded through importlib.resources; it must construct both Draft7Validator instances successfully in an installed wheel with the repository absent from sys.path. |
| Public CLI | autopulse-debug maps only to the existing sanitized offline debug CLI. The live CLI receives no public console entry point. |
| Dependency groups | Runtime metadata lists only dependencies proven necessary by source/import and installed-workflow tests. pytest and package/security tools are isolated development/tooling groups. |
| Resolution authority | Commit one universal uv.lock. It locks exact versions across allowed markers, but is not wheel evidence. Pin/hash build frontend/backend and tooling separately. |
| Per-cell installation proof | Export a fully pinned, SHA-256-hashed requirements view per supported Python/OS/architecture cell. Native clean jobs use pip --require-hashes --only-binary=:all: with matching local wheelhouse. Cross-platform download is only early validation, never final support proof. |
| Offline install | Build and verify one wheelhouse per supported cell; clean install uses --no-index and --find-links, followed by installed-wheel replay/validation. |
| SBOM | CycloneDX JSON 1.6 via pinned cyclonedx-py from the exact clean installed release environment, schema-validated and reproducibly generated. Bind each SBOM to commit, AutoPulse wheel SHA-256, and selected dependency-wheel manifest SHA-256; build twice under controlled inputs and compare the canonicalized result. |
| Vulnerability and license evidence | Pinned pip-audit performs strict JSON known-vulnerability checks. Pinned pip-licenses produces a normative JSON expression/license inventory and a CSV support inventory whose cells are formula-neutralized. An AutoPulse-owned validator, not pip-licenses --allow-only alone, rejects UNKNOWN, LicenseRef, unparseable, or non-allowlisted expressions. Findings or license failures fail closed unless PR-001's independent, expiry-dated exception procedure applies. |
| Artifact gates | Run twine check --strict, check-wheel-contents as a supplemental check, and an AutoPulse-owned deterministic inventory validator for both wheel and sdist. The validator normalizes POSIX paths, rejects absolute/parent/link/duplicate members, and compares all members with the approved allowlist. Hatchling's unavoidable root `.gitignore` is the sole VCS-named exception: it is allowed only in an sdist at its exact root, never in a wheel; `.git/`, `.github/`, and every other `.git*` member remain prohibited. |
| Privacy gates | Scan generated SBOMs and evidence for absolute-local paths and private URLs. Inventory checks deny env files, VCS metadata, caches/bytecode, tests/test-only modules, fixture data, secrets, raw telemetry, and private operational artifacts by both normalized member path and a lightweight raw-identifier/content scan. The content scan is intentionally suppression-free: new sanctioned examples must avoid raw identifiers or be excluded from the release artifact, so no label can weaken this fail-closed gate. |

## Required implementation artifacts

- pyproject metadata with package/resource configuration and the offline-only CLI;
- universal uv.lock; per-cell hashed requirements exports; wheelhouse manifests containing filenames and SHA-256 values;
- deterministic build, wheelhouse, resource-integrity, archive-inventory, SBOM/privacy, license, and vulnerability scripts;
- a documented local matrix-evidence runner that produces a sanitized, reviewable `docs/qa/` summary of commands, supported-cell results, selected wheel names, and SHA-256 values. It is the PR-002 evidence mechanism until PR-003 moves the matrix into CI; no wheelhouse or binary artifact is committed;
- a CycloneDX JSON SBOM for each distinct resolved supported environment, unless equality is demonstrated;
- tests for installed-wheel import of `autopulse.data.validator` with no checkout on `sys.path`, installed-wheel replay/validation, canonical-to-packaged schema checksum equality including a drift-detection mutation, absence and import failure of autopulse.live and any live-only module, no public live CLI, wheel-only hash-checked install, artifact allowlist and content-scan rejection, SBOM privacy rejection, deterministic SBOM/build comparison, and formula escaping in the generated pip-licenses CSV inventory for values beginning =, +, -, or @;
- user documentation that states supported cells, offline installation, and live/use prohibitions.

No generated wheelhouse, release artifact, scan output, or environment-specific evidence is committed until the PR-004/PR-005 retention/publication decision permits it.

## Acceptance criteria

1. Every supported cell performs native clean installation from only prebuilt wheels, exact hashes, and a matching local wheelhouse. Missing wheel, hash, or attempted network access fails. The documented local matrix-evidence runner produces the sanitized `docs/qa/` summary for the implementation audit.
2. With the repository absent from `sys.path`, the installed wheel imports `autopulse.data.validator`, constructs both schema validators from `importlib.resources`, and completes documented replay/validation. A source/resource byte comparison and deliberate one-byte source-schema mutation prove drift detection works.
3. The sdist, wheel archive listing, and wheel `RECORD` contain no live-capture path; `import autopulse.live` and `import autopulse.live.cli` fail after installation. Both artifacts pass the explicit content allowlist and content scan.
4. SBOM, normative JSON license report, formula-neutralized CSV license inventory, and vulnerability report are generated from the exact resolved clean environment. SBOM validation, privacy scans, and a controlled build-twice/canonicalized-SBOM comparison fail closed.
5. A critical/high vulnerability exception names owner, rationale, mitigation, expiry, and independent Claude approval. No implementer self-approval is accepted.
6. Claude-selected tests and the existing suite pass. CI workflow changes and release publication are deferred to PR-003 and PR-005.

## Verification plan

Run focused package tests; build sdist and wheel twice from clean trees; install the wheel without network from each matching wheelhouse and without the checkout on `sys.path`; execute replay smoke checks; validate packaged schemas and a deliberate drift mutation; inspect wheel, sdist, and `RECORD` inventories; generate and scan SBOM/license/vulnerability evidence; write the sanitized local matrix summary; then run the complete suite and git diff --check.

## Primary-source basis and caveats

Sources checked 2026-08-13:

- Hatch, build configuration: https://hatch.pypa.io/1.10/config/build/
- PyPA build CLI: https://build.pypa.io/en/latest/reference/cli.html
- uv project layout and universal lock: https://docs.astral.sh/uv/concepts/projects/layout/
- uv resolver caveat: https://docs.astral.sh/uv/reference/internals/resolver/
- pip secure installs: https://pip.pypa.io/en/stable/topics/secure-installs/
- pip download: https://pip.pypa.io/en/stable/cli/pip_download/
- CycloneDX Python tool: https://cyclonedx-bom-tool.readthedocs.io/en/latest/usage.html
- pip-audit: https://pypi.org/project/pip-audit/
- pip-licenses: https://pypi.org/project/pip-licenses/
- check-wheel-contents: https://github.com/jwodder/check-wheel-contents

The exact package name, public import surface, jsonschema lower bound, license allowlist, retention policy, attestation mechanism, and Linux/macOS wheel-tag policy remain maintainer decisions or implementation evidence. A universal lock does not prove wheel availability, and scanner success is not a guarantee that dependencies are benign.
