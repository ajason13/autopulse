# Antigravity Handoff: US-006 EV Telemetry Feedback Resolution

You are Antigravity CLI acting as AutoPulse Lead Architect and Coordinator.

## Situation

You were unavailable during the initial US-006 kickoff because of quota limits. Codex temporarily covered coordination duties: it moved the repository onto the next task branch, created/updated Notion records, captured Gemini Deep Research output, and prepared the Claude adversarial planning prompt.

You are now resuming the coordinator role. Do not implement US-006 yet. Your task is to reconcile Claude's planning feedback, update the PM/spec artifacts, and prepare a clean implementation handoff back to Codex.

## Current Branch And Local State

Branch:

```text
us-006-ev-integration-research
```

Base:

```text
origin/main
```

Current local changes:

- `AGENTS.md`: updated governance to name Antigravity CLI as Lead Architect & Coordinator using Gemini 3.5 Flash Medium.
- `CONTEXT.md`: active memory moved to Epic 4 / US-006 and later to Claude QA planning.
- `docs/prompts/gemini-deep-research-us006-ev-integration.md`: Gemini Deep Research prompt used to generate the initial US-006 research result.
- `docs/specs/us-006-ev-telemetry-data-contract.md`: distilled internal US-006 spec from Gemini research.
- `docs/prompts/claude-adversarial-planning-us006-ev-integration.md`: Claude planning prompt with project stack, layout, and attack surface.
- `docs/prompts/antigravity-us006-feedback-handoff.md`: this handoff.

Untracked `.antigravitycli/` exists locally as a symlink directory and was intentionally left untouched.

Verification so far:

```text
git diff --check
```

passed after the prompt/spec edits.

No tests were run because no implementation code has been changed.

## Notion Updates Already Made

Project hub:

- AutoPulse hub docs status was updated to show US-006 EV integration research is now in Claude QA planning.

Epic:

- Created `Epic 4: Electric Vehicle Integration`.
- Status moved from `Researching` to `Designing`.
- Governance note updated: Gemini research has produced US-006 direction; no implementation should begin until Claude validates QA red lines and open questions.

Task:

- Created `US-006 - EV Telemetry Data Contract Research (ZEVonUDS)`.
- Branch property: `us-006-ev-integration-research`.
- Handshake Status moved from `1. Spec Drafting (Gemini)` to `2. QA Planning (Claude)`.
- Task body was replaced with a distilled Gemini spec summary, candidate EV fields, repo artifact pointers, and the Claude handoff instruction.

## What Gemini Research Produced

Gemini proposed:

- target standards family: SAE J1979-3 / ZEVonUDS
- architecture: parallel US-006 EV schema with shared metadata envelope
- validation isolation: do not mutate US-001
- candidate allowed services: `0x22`, limited `0x19`, passive `0x3E`
- forbidden services: `0x2E`, `0x2F`, `0x31`, `0x14`
- candidate EV fields:
  - `battery_soh`
  - `battery_soce`
  - `battery_temp_avg`
  - `traction_motor_speed`
  - `battery_throughput`
  - `grid_energy_in`
- downstream ideas:
  - EV replay support
  - EV dirty-data scenarios
  - possible EV-HDF and EV-OSF analysis later

Codex captured this in:

```text
docs/specs/us-006-ev-telemetry-data-contract.md
```

## Claude Planning Feedback Summary

Claude conditionally approved the parallel schema strategy, but said mandatory revisions are required before implementation.

### Must Fix Before Schema Authoring

1. `battery_temp_avg` maximum of `215.0` C is indefensible.
   - Claude says this was inherited from an ICE coolant byte range, not EV battery physics.
   - Recommended ceiling: `80.0` C for aggressive consumer EV operation, or a stricter OEM/chemistry-specific value.
   - Decision needed: use `80.0` C for US-006 initial schema unless you have a better documented source.

2. `battery_throughput` range of `-2.1e9` to `2.1e9` Ah is physically absurd.
   - Claude recommends a realistic vehicle lifetime ceiling, such as `500000` Ah for high-mileage commercial EVs.
   - Decision needed: set a physics-based range. Suggested initial bound: `0.0 <= x <= 500000.0` Ah unless bidirectional net throughput must be signed.

3. `grid_energy_in` maximum of `429496729.5` kWh is physically absurd.
   - Claude recommends `1000000.0` kWh (1 GWh) as a generous lifetime maximum for commercial/fleet vehicles.
   - Decision needed: revise the field bound to `0.0 <= x <= 1000000.0` kWh.

4. Protocol enum must be defined.
   - Claude suggested at minimum:
     - `SAE_J1979`
     - `SAE_J1979-2`
     - `SAE_J1979-3`
     - `ISO_15765_4_DoCAN`
     - `ISO_13400_DoIP`
   - Decision needed: for EV payloads, prefer a narrower enum unless legacy protocol values are truly valid for EV frames.

### Must Resolve Before Adapter Implementation

5. Expand forbidden UDS services beyond Gemini's initial list.
   - Block `0x10` DiagnosticSessionControl except DefaultSession `0x01`.
   - Block `0x27` SecurityAccess.
   - Block `0x2E`, `0x2F`, `0x31`, `0x14`.
   - Restrict `0x19` to passive read subfunctions only.
   - Rate-limit `0x3E` TesterPresent to no more than once per 4 seconds and never use it to sustain non-Default sessions.

6. CAN-to-Ethernet transition behavior.
   - Claude recommends abort-and-log on DoCAN to DoIP transition.
   - Avoid automatic discovery because it expands attack surface.

### Must Resolve Before Replay Or Analysis Work

7. `traction_motor_speed` sign convention.
   - Keep optional.
   - Negative values may be valid, but the schema must document sign convention and source.
   - If no generic passenger-vehicle mapping exists, defer this to an OEM-specific extension.

8. EV-HDF and EV-OSF formulas are not implementation-ready.
   - Claude recommends limiting US-006 sprint scope to schema validation and replay harness.
   - Do not implement EV analysis logic until a later story with stronger physics basis.

9. Exclude unstable or unevenly supported parameters.
   - Keep time-of-use, V2X discharge, and certified energy consumption out of US-006.
   - Defer to a later story such as US-007 after standards and OEM mapping are clearer.

## Recommended Antigravity Actions

1. Update the Notion US-006 task to reflect Claude's status:
   - Keep task at `2. QA Planning (Claude)` until blockers are resolved.
   - Add Claude's mandatory revisions as a concise "Architect Resolution Required" section.

2. Update `docs/specs/us-006-ev-telemetry-data-contract.md`:
   - Revise candidate field ranges:
     - `battery_temp_avg`: max `80.0` C, pending final human approval.
     - `battery_throughput`: replace `2.1e9` with physics-based range.
     - `grid_energy_in`: max `1000000.0` kWh.
   - Add explicit protocol enum policy.
   - Add explicit UDS service policy including `0x10`, `0x27`, `0x3E`, and restricted `0x19`.
   - Mark `traction_motor_speed` optional with sign-convention caveat.
   - Reduce US-006 scope to schema, routing, adapter guardrails, replay harness, and JSON-LD safety checks.
   - Move EV-HDF/EV-OSF formulas to "future research / not in US-006 implementation scope".

3. Update `CONTEXT.md` after spec resolution:
   - Keep active story US-006.
   - Record that Claude required architecture revisions before Codex implementation.
   - Mark Codex implementation as blocked until Antigravity resolves field bounds and policy decisions.

4. Prepare a final Codex implementation handoff only after the above updates:
   - include final field table
   - include final protocol enum
   - include final UDS allow/deny matrix
   - include final test file list from Claude
   - state explicitly that EV anomaly analysis is out of scope unless you override Claude's recommendation

## Human Policy Defaults To Use Unless Overridden

Use these conservative defaults if the human does not override them:

- `0x14` ClearDiagnosticInformation remains forbidden.
- `battery_temp_avg` max is `80.0` C.
- `grid_energy_in` max is `1000000.0` kWh.
- `battery_throughput` is bounded to a realistic lifetime value rather than protocol max.
- CAN-to-DoIP transition aborts and logs; no automatic discovery.
- `traction_motor_speed` remains optional.
- EV-HDF and EV-OSF are out of scope for US-006 implementation.
- Time-of-use, V2X discharge, and certified energy consumption are out of scope for US-006.

## Prompt For Your Next Turn

Use this as your working instruction:

```text
You are Antigravity CLI resuming AutoPulse Lead Architect & Coordinator duties for US-006.

Read the current branch state and Notion US-006 task. Claude has conditionally approved the parallel EV schema strategy but requires mandatory revisions before Codex implementation. Update the US-006 spec and Notion task to address Claude's feedback:

1. Replace inherited/protocol-max EV field bounds with physics-based bounds.
2. Define the EV protocol enum.
3. Expand UDS allow/deny policy to include 0x10, 0x27, restricted 0x19, rate-limited 0x3E, and forbidden 0x14/0x2E/0x2F/0x31.
4. Keep traction_motor_speed optional with sign-convention caveat.
5. Scope US-006 implementation to schema/routing/adapter/replay/serialization safety, not EV-HDF or EV-OSF analysis.
6. Update CONTEXT.md and Notion to reflect these architecture decisions.
7. Prepare a final Codex handoff prompt after the spec is resolved.

Do not implement code. Do not move US-006 to development until these blocker decisions are reflected in the project artifacts.
```
