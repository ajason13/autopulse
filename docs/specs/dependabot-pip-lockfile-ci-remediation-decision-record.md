# Dependabot pip lockfile CI remediation decision record

**Status:** Pre-implementation audit cleared on 2026-08-27; implementation audit pending.
**Baseline:** `6232f651e4887eb84645fc285e744b9cbad458da`.

## Decision

Apply the five open Dependabot declaration updates in one maintainer-owned
branch cut from current `origin/main`: jsonschema `>=4.26.0,<5`, pytest
`>=9.1.1,<10`, uv `0.12.5`, Hatchling `1.32.0`, and Twine `7.0.0`. Do not
rebase or merge the stale Dependabot branches.

Regenerate `uv.lock` only with a clean `uv 0.12.5` environment and `uv lock`.
The semantic lock-diff allowlist covers jsonschema, pytest, uv, Twine, and
named transitive changes directly required by them. Hatchling is a build-system
requirement, not a lockfile package; verify its installed build-environment
version separately. Reject unrelated version, source, marker/platform, URL,
removal, or integrity drift.

## Evidence requirements

The authenticated historical job logs classify #71, #72, #73, and #75 as
stale-lock failures at `uv export --locked`. PR #74 instead fails downstream:
Twine 6.2 rejects metadata 2.5 produced by Hatchling 1.32. The implementation
must test committed declaration/lock consistency with the real locked export,
build with the exact Hatchling version, and run `twine check --strict` on the
wheel and sdist. Post-resolution checks reject legacy `.tar.bz2`/`.tar.xz`
sdists and integrity hashes weaker than SHA-256.

No CI gate may be weakened. Before push, Claude must audit the exact source
diff and resolver evidence. Afterwards, one exact-head hosted run must pass the
eight package cells and docs. Merge or Dependabot-PR closure requires separate
active-session user authority.

## Scope boundary

This is dependency, lockfile, package-evidence, and governance work only. It
does not change runtime diagnostics, replay, telemetry, VIN handling, logging,
CLI behavior, observability, live-adapter boundaries, releases, deployments,
or Windows 11 support claims. The offline educational/replay-only profile and
`autopulse.live` exclusion remain intact.
