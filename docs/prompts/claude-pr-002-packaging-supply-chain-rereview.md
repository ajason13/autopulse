# Claude re-review prompt — PR-002 contract fixes

You are AutoPulse's independent Lead Auditor. Re-review the PR-002 packaging
contract after your 2026-08-13 `BLOCKER` and MF-01 through MF-05 findings.
This is a specification review only; no packaging implementation has started.

Confirm that the revised contract now explicitly requires:

1. rewriting `autopulse.data.validator` away from repository-relative,
   import-time schema paths, with installed-wheel import and validator
   construction tested while the checkout is absent from `sys.path`;
2. a local, sanitized `docs/qa/` matrix-evidence mechanism until PR-003 CI;
3. formula-neutralization testing against the actual generated pip-licenses CSV
   inventory, not a standalone helper;
4. deterministic build/SBOM evidence; and
5. archive listings, wheel `RECORD`, import failure, and content scanning that
   together prove `autopulse.live/**` and prohibited artifact data are absent.

Review `docs/specs/pr-002-packaging-supply-chain-decision-record.md`. Return
exactly one verdict: `NO BLOCKERS`, `MINOR FIXES`, or `BLOCKER`, identify any
remaining issue by exact section, and state whether PR-002 implementation may
begin. Do not grant implementation, merge, or release approval beyond that
scope.
