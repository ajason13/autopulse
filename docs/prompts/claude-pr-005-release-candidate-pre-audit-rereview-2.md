# Claude Chat prompt — PR-005 second focused pre-audit re-review

You are AutoPulse’s independent Lead Auditor (Claude Sonnet 4.6). Re-review
only the remaining MF-03 and the two acknowledged open questions from your
2026-08-19 `MINOR FIXES` response. This is planning only: no tag, release,
publication, deployment, runtime change, release-readiness claim, or Windows
11 claim is authorized.

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. State
whether these corrections close MF-03. Execution remains conditional on `NO
BLOCKERS` and active-session authority for an exact RC ID plus dereferenced
40-character SHA; do not approve a release.

## MF-03 resolution grounded in current source

The prior three privacy suites cover VIN/payload/token redaction. The revised
plan no longer implies they cover seed-key/security access. Instead, it has two
explicit controls:

1. `tests/test_us006_ev_adapter_security.py::test_forbidden_services_blocked`
   is an in-scope, non-`autopulse.live` importing test. It directly creates
   `autopulse.data.validator.UDSCommandGuard` and asserts SecurityAccess `0x27`
   subfunctions `0x01` and `0x02` raise `CommandBlockedException` with
   `SECURITY_VIOLATION_RED_LINE`. Every hosted cell must attest its execution,
   pass, aggregate count, and exit status; a skip/collection/import failure is
   a failed cell.
2. Structural exclusion is the sole intended control for live-adapter
   seed-key/security-access/capture paths. `verify_release_cell.py` runs in an
   isolated installed wheel, asserts `find_spec("autopulse.live") is None`,
   no `autopulse/live/` distribution file exists, and only `autopulse-debug`
   is installed. Archive allowlists exclude `src/autopulse/live/**`. No
   live-adapter test is claimed to execute in the installed offline package.

## Additional corrections

- Any re-resolved RC ID/SHA or hosted `head_sha` mismatch halts and retires the
  RC ID; it is never a warning.
- Scope certification now reviews imports/dependents for every changed module,
  specifically identifying modules shared by offline and excluded live
  surfaces, rather than relying only on changed paths.
- The repository has no approved external evidence-retention policy. No binary
  or raw evidence is retained in git. The final audit must cite a
  maintainer-approved retention location, access role, and deletion timeline,
  or external retention remains blocked; failed-RC records retain only a
  sanitized superseded status.

Preserved boundaries: educational offline/replay-only, read-only, no live
adapter/capture/VIN/telemetry/write-control/session-security/road-unattended
use, and no runtime observability change. Evidence has no raw logs, paths,
private URLs, VIN-like values, payloads, wheelhouses, artifacts, or secrets.
