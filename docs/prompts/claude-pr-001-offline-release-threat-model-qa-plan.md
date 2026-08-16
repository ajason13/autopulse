# Claude adversarial-QA planning prompt — PR-001

You are AutoPulse’s independent Lead Auditor. Review the pre-implementation specification at `docs/specs/pr-001-offline-release-profile-and-threat-model.md`.

This is a Gated Delivery policy/specification review only: no runtime feature, dependency, CI, schema, or release change has been authorized. The release profile is educational, local/offline replay after installation; it must not authorize fleet deployment, road testing, unattended monitoring, VIN reads, live capture, adapter discovery, or any write/control-capable diagnostics.

Challenge the supported Python/OS matrix; public API/SemVer policy; dependency, license, vulnerability, and SBOM gates; data/support-artifact prohibitions; trust boundaries; fail-closed release gates; and the PR-002 through PR-005 sequencing. Focus on realistic bypasses, privacy leaks, supply-chain failures, and evidence gaps. Treat the specification’s sourced findings separately from its AutoPulse policy decisions.

Return a lean QA plan with concrete proposed test/evidence checks and this verdict format:

`BLOCKER`, `MINOR FIXES`, or `NO BLOCKERS`.

For every blocker/minor fix, give the exact spec section, risk, and required correction. State explicitly whether PR-002 may begin. Do not claim an implementation audit or final release approval.

