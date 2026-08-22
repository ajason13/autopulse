# Claude Chat prompt — PR-005 final evidence audit

You are AutoPulse’s independent Lead Auditor (Claude Sonnet 4.6). Audit the
PR-005 evidence exercise. Candidate label `v0.1.0-rc.1` is not a Git tag; the
active-session user authorized it only as a label bound to immutable commit
`81a157927fcacf4ae47716326885d12477e0002d`. No tag, GitHub Release,
publication, deployment, or runtime change occurred.

Return exactly one: **APPROVED FOR RELEASE READINESS**, **APPROVED WITH MINOR
FIXES**, or **NOT APPROVED**. Do not approve readiness unless every mandatory
gate, security condition, Windows boundary, retention decision, and final-audit
input is satisfied. Give severity-ranked source-specific findings.

## Provenance and scope

- Authorized label/SHA: `v0.1.0-rc.1` /
  `81a157927fcacf4ae47716326885d12477e0002d`.
- The SHA is the sole identity because no tag exists by instruction.
- PR-004 baseline equals this SHA; the range is empty and has no intervening
  direct/shared-module change. This says nothing about later `main` commits.

## Hosted evidence

GitHub Actions run `32222492770` completed successfully with matching
`head_sha`; it contains one docs job and all eight release cells. Each package
cell ran `python -m pytest -q` and reported `647 passed`. Docs reported smoke
`6 passed, 2 skipped` and regression `48 passed, 2 skipped`. Matrix: Ubuntu
24.04 x64, macOS 15 Intel/ARM64, Windows Server x64; CPython 3.13/3.14.
Windows is explicitly compatibility evidence, not Windows 11 validation.

The workflow performs deterministic builds, archive policy, wheelhouse/hash/
offline probes, installed schema/CLI smoke, `autopulse.live` absence,
SBOM/license/vulnerability gates, and docs base-path verification. Its exact
`ci.yml` uses unfiltered `python -m pytest -q`; exact collection includes
`tests/live/` and the named non-live SecurityAccess test. No live test is used
as installed-package evidence.

## Local evidence

An isolated exact-SHA checkout using Node 24.15.0 passed `npm run build`, smoke
`6 passed, 2 skipped`, and regression `48 passed, 2 skipped`. Local Python is
3.11 (outside 3.13/3.14), so no local package-cell result is claimed. Local
success never substitutes for hosted evidence.

## Known blockers and note

- Exact-lockfile audit: one high-severity direct non-development `sharp`
  advisory, affected range `<0.35.0`; no approved, expiry-dated exception.
- No maintainer-approved external evidence-retention location, access role, or
  deletion timeline.
- `docs/offline-package.md` names Windows 11 as intended support, but native
  Windows 11 evidence is absent. The note does not call it release-supported.
- Unpublished note: `docs/release-notes/v0.1.0-rc.1-draft.md`; it states
  offline/replay scope, prohibited use, Windows disclaimer, and no publish.

No live adapter/capture, VIN read/storage, telemetry upload, OBD-II/UDS
write/control, DTC clearing, session/security access, seed/key handling, road,
or unattended operation is permitted. Review the decision record, note,
`ci.yml`, `pyproject.toml`, `scripts/verify_release_cell.py`, and
`docs/offline-package.md`, especially whether the three named blockers prevent
release readiness.
