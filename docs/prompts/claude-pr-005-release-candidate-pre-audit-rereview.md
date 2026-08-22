# Claude Chat prompt — PR-005 pre-audit focused re-review

You are AutoPulse’s independent Lead Auditor (Claude Sonnet 4.6). Re-review
the PR-005 evidence plan after your 2026-08-18 `MINOR FIXES` verdict. This is
planning only: it authorizes no tag, release, publication, deployment, runtime
change, release-readiness claim, or Windows 11 claim.

Return exactly one: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**. Confirm
each MF-01–MF-09 as resolved or give the remaining precise gap. Execution may
begin only after your `NO BLOCKERS` verdict and active-session authority for an
exact RC ID plus immutable 40-character commit SHA. Do not approve a release.

| Finding | Revised plan correction |
| --- | --- |
| MF-01 | Authorization captures RC ID and dereferenced 40-hex `RC_ID^{commit}` SHA. Re-resolve before hosted trigger, local checks, binding, note review, and final audit; each and hosted `head_sha` must equal it. |
| MF-02 | Final audit enumerates every commit/path category from baseline `81a157927fcacf4ae47716326885d12477e0002d` to RC SHA and certifies no runtime diagnostic/replay/telemetry/VIN/logging/observability change. |
| MF-03 | Every cell separately attests `tests/test_debugging.py`, `tests/test_runtime_logging.py`, and `tests/test_debug_cli_replay.py` executed/passed; retain IDs, count, and exit status only. |
| MF-04 | Exact release-note draft receives prohibited-value scan and fixed no-raw-output checklist before retention/circulation/final audit. |
| MF-05 | Local evidence is fixed-field allowlist only: check/tool/OS-Python/SHA/pass-fail/count/hash/exit; no stdout/stderr. |
| MF-06 | Exact-commit public-doc review blocks Windows 11 claims without native proof; notes must say: “Evidence covers Windows Server x64 only; this is not Windows 11 desktop validation.” |
| MF-07 | All eight cells and docs pass in one workflow run at the SHA. Failure/cancellation/missing job/retry/flake invalidates it; use a fresh complete nine-job run. |
| MF-08 | Any failure permanently retires its RC ID; evidence is superseded/deleted per retention policy, a new ID is required, and all gates rerun. |
| MF-09 | Local checks require both this `NO BLOCKERS` and explicit active-session RC authority. |

Preserved controls: educational offline/replay-only and read-only package; no
live adapter/capture/VIN read or storage/telemetry upload/OBD-II or UDS
write-control/session-security/road-unattended use; no runtime observability
change; no retained wheelhouse/artifact/raw log/path/private URL/VIN-like
value/payload/secret. Existing immutable Action pins, read-only CI, fixed
matrix, shell semantics, offline/hash installation, `autopulse.live`
exclusion, and `/autopulse/` docs verification remain mandatory.

Challenge tag dereferencing, run atomicity, named privacy attestations,
scope certificate, release-note scan, Windows wording, and stale-evidence
retirement. Identify any remaining leak or bypass.
