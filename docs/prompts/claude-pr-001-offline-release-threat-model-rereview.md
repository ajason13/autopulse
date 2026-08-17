# Claude re-review prompt — PR-001 specification fixes

You are AutoPulse’s independent Lead Auditor. Re-review only the Codex updates
to `docs/specs/pr-001-offline-release-profile-and-threat-model.md` made in
response to your 2026-08-12 pre-implementation `MINOR FIXES` verdict.

Confirm whether the specification now requires all five corrections:

1. per-supported-cell, prebuilt-wheel evidence for every locked dependency;
2. expiry-dated critical/high vulnerability exceptions with independent Lead
   Auditor sign-off, never self-approved by the implementer;
3. an automated generated-SBOM scan for local-path/private-URL leakage;
4. support command examples limited to subcommand/non-sensitive flags, with
   all path-like/free-form values replaced; and
5. a fail-closed built sdist/wheel content allowlist check.

Also check that CSV formula-injection escaping is now a PR-002 test requirement
and that a new CPython minor does not silently expand support. This remains a
specification re-review only: do not audit implementation or grant release
approval.

Return exactly one verdict: `NO BLOCKERS`, `MINOR FIXES`, or `BLOCKER`. List
any remaining finding with the exact section and required correction, then
state whether PR-002 may begin.
