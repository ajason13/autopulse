# Claude adversarial-QA planning prompt — PR-002

You are AutoPulse’s independent Lead Auditor. This is a **pre-implementation QA-plan review**, not an implementation audit or release approval.

Claude Chat may inspect the public GitHub files below. The PR-002 decision record is a local draft and may not yet be visible on GitHub, so this prompt contains every proposed decision you must assess.

## Public repository baseline

Review these files in GitHub:

- [requirements.txt](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/requirements.txt)
- [current CI workflow](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/.github/workflows/ci.yml)
- [package source tree](https://github.com/ajason13/autopulse/tree/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse)
- [validator and root-schema lookup](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse/data/validator.py)
- [offline debug/replay CLI](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse/debug.py)
- [live-capture CLI, deliberately out of profile](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse/live/cli.py)
- [current package initializer](https://github.com/ajason13/autopulse/blob/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/src/autopulse/__init__.py)
- [current schemas](https://github.com/ajason13/autopulse/tree/22cd59b973f65fd22bcdf8b5f40d2b331fefcd4c/schemas)

Current facts to verify from those files: there is no pyproject metadata, lockfile, SBOM, or build configuration; requirements are unpinned; jsonschema is the only observed third-party runtime import; pytest is test-only; and recursively packaging src/autopulse would include the real live-capture capability.

## Proposed PR-002 implementation contract

This contract implements the approved educational offline/replay profile only:

- Use PEP 621 metadata with Hatchling, static PEP 440 versioning, and requires-python >=3.13,<3.15. Build a pure-Python wheel through the sdist path.
- Package offline modules and canonical-equivalent schema resources only. Explicitly exclude autopulse/live/** and all live-only modules from both wheel and sdist; installed-wheel import of autopulse.live must fail. Expose only the sanitized offline debug CLI as autopulse-debug.
- Runtime metadata must include only dependencies supported by actual source/import and installed-workflow evidence. Do not migrate pandas, numpy, or python-dotenv from requirements.txt unless a documented runtime need is found and tested.
- Commit a universal uv.lock as exact resolution authority, then generate a fully pinned SHA-256-hashed requirements view and local wheelhouse per supported Python/OS/architecture cell. Native clean installation must use only prebuilt wheels, pip --require-hashes, --only-binary=:all:, --no-index, and --find-links. A missing wheel/hash or any network access must fail.
- Preserve root schemas as repository source of truth, stage byte-identical package resources, load installed schemas with importlib.resources, and test source/resource checksum equality.
- Generate one reproducible, validated CycloneDX JSON SBOM from each distinct clean runtime environment; bind it to the commit, AutoPulse wheel SHA-256, and dependency-wheel-manifest SHA-256. Scan it for absolute local paths and private URLs; a match fails closed.
- Run pinned pip-audit against the exact resolved environment and emit JSON. Run pinned pip-licenses for inventory, then use an AutoPulse-owned SPDX-expression policy validator that rejects UNKNOWN, LicenseRef, unparseable, and non-allowlisted expressions. Do not treat pip-licenses --allow-only alone as a fail-closed license decision.
- Run twine check --strict, check-wheel-contents, and an AutoPulse-owned exact archive inventory validator for both sdist and wheel. It must reject absolute/parent/link/duplicate archive members, .env files, VCS metadata, caches/bytecode, tests, fixtures, raw telemetry, private artifacts, and autopulse/live/**.
- Test CSV output escaping for values that begin with =, +, -, or @.

No CI workflow change, dependency implementation, artifact publication, telemetry, live adapter/capture, VIN access, or diagnostic write/control behavior is authorized at this stage.

## Required review

Assess whether this contract is sufficient and coherent against the GitHub baseline, especially:

1. whether the proposed package exclusion can be verified robustly;
2. schema resource staging and installed-wheel behavior;
3. wheel/hash/offline evidence across CPython 3.13/3.14 supported cells;
4. supply-chain, SBOM, license, privacy, and archive fail-closed controls; and
5. test gaps or ways an implementer could satisfy the wording while shipping an unsafe/off-profile artifact.

Security red lines: no live adapter/capture, VIN reads, raw telemetry/support artifacts, online activity after offline installation, or write/control diagnostics.

Return:

1. prioritized adversarial test/evidence plan with concrete test file or script names;
2. blockers and minor fixes tied to a proposed-contract bullet above; and
3. exactly one verdict: BLOCKER, MINOR FIXES, or NO BLOCKERS, followed by whether PR-002 implementation may begin.

Do not claim an implementation audit, merge approval, or release approval.
