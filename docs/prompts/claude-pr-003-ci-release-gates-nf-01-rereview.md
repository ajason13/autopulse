# Claude — PR-003 NF-01 focused fix re-review

You are AutoPulse's independent Lead Auditor. This is a **pre-implementation,
focused fix re-review** after your second PR-003 verdict of `MINOR FIXES`.
No workflow, dependency, runtime, schema, release, or publication change has
been made or is authorized by this review.

Claude Chat has **no repository, GitHub, or filesystem access**. The text in
this packet is the complete review target; do not request or rely on local
files. You may distinguish any newly checked public GitHub fact from the
AutoPulse policy below.

AutoPulse is an educational offline/replay package. This review may authorize
CI/documentation implementation only; it never authorizes live capture, VIN
handling, telemetry upload, diagnostic control, a public release, or Windows
11 desktop validation.

## Prior status

Your first review found MF-01 through MF-05. The prior corrected contract
explicitly closed them with: Bash `pipefail`; PowerShell native-error handling;
allowlist-built summaries; a tested Windows-server disclaimer; config-derived
docs verification; and an offline-install test with its package index
unreachable/disabled. Your focused re-review found only NF-01:

> A required Windows gate could switch to `shell: cmd` or `shell: bat`, where a
> multi-line block can surface only the last command's exit code and thereby
> mask an earlier failed gate.

## Exact corrected policy text

The following is the authoritative replacement for PR-003's workflow policy
item 5:

> Every Linux/macOS matrix job must set `defaults.run.shell: bash`; required
> gate steps may not override it with a shell that omits `-o pipefail`. Every
> Windows matrix gate step must explicitly use `shell: pwsh`, must not switch
> to `shell: cmd` or `shell: bat`, and must begin with
> `$ErrorActionPreference = 'Stop'` and
> `$PSNativeCommandUseErrorActionPreference = $true`. Required gates may not
> use `continue-on-error` or convert a non-zero native exit status to success.
> This prevents multi-line `cmd`/`bat` blocks from reporting only their last
> command's exit status.

The following is the authoritative replacement for the relevant PR-003
acceptance criterion:

> Workflow-focused adversarial tests or static checks prove: full-SHA action
> pins plus readable version comments; read-only permissions and forbidden
> triggers; exactly the eight named non-`*-latest` cells; explicit Bash
> pipefail and explicit `pwsh` (with no `cmd`/`bat`) Windows native-error
> handling; every required positive, negative, and offline probe;
> allowlist-only summary generation; cache non-evidence; concurrency SHA
> isolation; the Windows disclaimer; and the config-derived docs build. They
> must fail if any required property is silently removed.

For context, the contract continues to require an eight-cell CPython 3.13/3.14
matrix; top-level `contents: read` only; no `pull_request_target`,
`workflow_run`, secrets, environments, deploy/publish steps, or self-hosted
runners; full-SHA action pins; prebuilt-wheel-only and no-network offline
install evidence; allowlist-built summaries; and a literal Windows Server
compatibility-not-Windows-11 disclaimer. Hosted Windows evidence remains only
Python-wheel/workflow compatibility evidence.

## Required focused review

1. Does the replacement close NF-01 without a bypass through implicit shell
   selection, per-step shell overrides, or multi-line script behavior?
2. Is the required static-test wording sufficient to force both explicit
   `pwsh` and absence of `cmd`/`bat` in every required Windows gate?
3. Identify only new blockers/minor fixes introduced by this correction. Do not
   reopen MF-01 through MF-05 without a concrete interaction with NF-01.

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**.
For each finding, give severity, exact policy text, realistic bypass, and a
concrete correction. State whether PR-003 implementation may begin. Do not
claim public-release approval or Windows 11 validation.
