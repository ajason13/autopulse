# Selective Skills Pilot — 2026-08-11

## Decision this pilot informs

Decide whether AutoPulse should vendor and maintain a trimmed adaptation of two
engineering practices from `mattpocock/skills`:

1. a Builder-owned hard-bug diagnosis loop; and
2. a periodic context-writing hygiene review for agent-facing documents.

This is an experiment, not a change to the Multi-Agent SDLC. Notion remains
the authoritative project tracker and policy source; this document is the
portable repository handoff and measurement record.

## Boundaries

- **Delivery mode:** Advisor Mode. The Builder owns each pilot task. At most
  one bounded specialist may be consulted when a task independently warrants
  it; the pilot itself does not add an agent or an audit gate.
- **Excluded work:** live-vehicle work, OBD/UDS read-only controls, schemas,
  security/privacy controls, external integrations, public contracts, release
  blockers, and any task already requiring Gated Delivery.
- **No automatic authority:** the diagnosis practice may identify a likely
  fix, but it does not authorize implementation, commits, Notion updates, or
  a change in delivery mode.
- **Write scope:** this pilot changes only this handoff and, after each task,
  the compact results table below. It must not rewrite `AGENTS.md`, replace
  `CONTEXT.md`, install a third-party bundle, or create a second issue tracker.

## Pilot design

Run three matched pairs (six real, accepted AutoPulse tasks) during the next
30 days. A pair consists of the same task class and similar complexity:

| Pair | Task class | Control | Treatment |
| --- | --- | --- | --- |
| 1 | Hard, reproducible non-safety bug | Current Builder workflow | Current workflow + adapted diagnosis loop |
| 2 | Hard, reproducible non-safety bug | Current Builder workflow | Current workflow + adapted diagnosis loop |
| 3 | Routine docs/tooling defect or small non-safety bug | Current Builder workflow | Current workflow + context-hygiene preflight |

Select a pair before beginning either task. Record why the tasks are comparable
in the results table. Do not delay a production, safety, or release-blocking
task to satisfy the experiment. If a selected task becomes gated, remove it
from the pilot and record the exclusion.

The treatment is deliberately **adapted**, not installed:

- **Diagnosis loop:** before theory or a code fix, create and run a fast,
  deterministic, red-capable reproduction. Minimize it; list 3–5 falsifiable
  hypotheses; use a probe tied to a hypothesis; turn the minimized repro into
  a regression test at an approved seam; remove temporary instrumentation.
- **Context-hygiene preflight:** inspect only the agent-facing files needed by
  the task. Keep always-loaded guidance short; move conditional detail behind
  a precise pointer; remove stale/no-op guidance; retain one source of truth;
  use checkable completion criteria. Do not change technical policy as part of
  this treatment.

## Measurement protocol

Start a row before work begins and stop the active-work timer at the first
ready-for-review handoff. Exclude human response time, CI queue time, and
Claude/other external reviewer wait time; record them separately.

| Metric | Definition | Collection rule |
| --- | --- | --- |
| Task comparability | Task class, scope, touched-area estimate, and reason the pair is comparable | Written before starting the pair |
| Active elapsed time | Builder work time from start to ready-for-review handoff | Minutes; exclude waiting |
| Total tokens | Input + output tokens across the accountable Builder session and any permitted specialist | Use surfaced usage only; otherwise record `UNAVAILABLE`, never estimate from words/bytes |
| Agent count | Distinct agent sessions used for the task | Include only sessions that materially worked on the task |
| Tool calls | Shell, browser, and other tool invocations issued by the Builder | Count from the session/tool history |
| Feedback-loop quality | Whether a task-specific, deterministic, agent-runnable pass/fail command existed before the fix | `yes` / `no` / `not applicable` plus command |
| Rework cycles | Number of post-first-handoff correction cycles caused by failing verification, reviewer findings, or unmet acceptance criteria | Do not count cosmetic wording-only edits |
| Verification | Required commands and result | Exact command plus concise result |
| Quality outcome | Escaped defect or regression reported within 14 calendar days after completion | `none known`, issue link, or `not yet observable` |

For the context-hygiene treatment, record two additional measures:

- bytes of always-loaded agent instructions before and after (`AGENTS.md` plus
  any directly loaded task instruction); and
- number of files/links required to find the authoritative task constraints.

These are context-load indicators, not token measurements.

## Results ledger

| Pair/task | Arm | Comparable because | Active min | Tokens | Agents | Tools | Red-capable loop | Rework cycles | Verification | 14-day outcome | Notes |
| --- | --- | --- | ---: | --- | ---: | ---: | --- | ---: | --- | --- | --- |
| [P1 control / #53](https://github.com/ajason13/autopulse/issues/53) | control | Offline replay timing/state defect; paired before implementation | UNAVAILABLE | UNAVAILABLE | 1 | 10 | yes; targeted pytest | 0 | Targeted 2 passed; US-002 and full pytest passed | Not yet observable | Ready for review; observability unchanged |
| [P1 diagnosis / #54](https://github.com/ajason13/autopulse/issues/54) | diagnosis | Offline replay timing/state defect; paired before implementation | UNAVAILABLE | UNAVAILABLE | 1 | 6 | yes; targeted pytest and standalone repro | 0 | Targeted 1 passed; US-002 and full pytest passed | Not yet observable | Ready for review; observability unchanged |
| [P2 control / #56](https://github.com/ajason13/autopulse/issues/56) | control | Offline replay developer-compatibility defect; paired before implementation | UNAVAILABLE | UNAVAILABLE | 1 | 9 | yes; isolated source-only pytest | 0 | Targeted 1 passed; focused and full pytest passed | Not yet observable | Ready for review; observability unchanged |
| [P2 diagnosis / #55](https://github.com/ajason13/autopulse/issues/55) | diagnosis | Offline replay developer-compatibility defect; paired before implementation | — | — | — | — | — | — | — | — | Not started |
| [P3 control / #58](https://github.com/ajason13/autopulse/issues/58) | control | Starlight local-developer documentation defect; paired before implementation | — | — | — | — | — | — | — | — | Not started |
| [P3 context hygiene / #57](https://github.com/ajason13/autopulse/issues/57) | context-hygiene | Starlight local-developer documentation defect; paired before implementation | — | — | — | — | — | — | — | — | Not started |

## Created task backlog

The primary reviewed the following issues against the pilot boundaries on
2026-08-11. All are explicitly offline, documentation, or developer-tooling
work; none changes live-vehicle behavior, diagnostic command boundaries,
schemas, privacy/security controls, dependencies, external integrations, or
release policy.

1. [#53](https://github.com/ajason13/autopulse/issues/53) — prevent a phantom
   final interval in replay metrics (Pair 1 control).
2. [#54](https://github.com/ajason13/autopulse/issues/54) — preserve replay
   frequency when invalid drift is rejected (Pair 1 diagnosis).
3. [#56](https://github.com/ajason13/autopulse/issues/56) — make replay
   modules importable from a source-only package (Pair 2 control).
4. [#55](https://github.com/ajason13/autopulse/issues/55) — accept bare
   hexadecimal PID tokens in the CANdid parser (Pair 2 diagnosis).
5. [#58](https://github.com/ajason13/autopulse/issues/58) — correct
   docs README routes for the GitHub Pages base path (Pair 3 control).
6. [#57](https://github.com/ajason13/autopulse/issues/57) — correct
   the Getting Started Node prerequisite (Pair 3 context-hygiene treatment).

## Decision rule

After all eligible pairs have a 14-day outcome, compare treatment with control
within each pair. This small sample is directional evidence, not a statistical
claim.

Adopt a trimmed local practice only when all are true:

1. no treatment task has an escaped defect, failed required verification, or
   governance breach attributable to the practice;
2. treatment total tokens are no more than 10% above the paired control median
   when usage is available (otherwise declare token impact inconclusive);
3. treatment improves active time by at least 20% **or** reduces rework cycles
   by at least one in at least two pairs; and
4. the Builder's final note says the practice improved task clarity or
   feedback quality without adding unacceptable user round-trips.

If the safety/quality condition fails, stop the pilot. If no rule is met, do
not adopt; retain the useful observations as optional guidance only. If the
sample is incomplete after 30 days, close it as `INCONCLUSIVE` rather than
extending it indefinitely.

## Reporting template

For every completed task, append this compact note below the ledger:

```md
### <task ID> — <date>

- Arm: control | diagnosis | context-hygiene
- Comparable-pair rationale:
- Model / effort and exception, if any:
- Active minutes / surfaced tokens / agents / tools:
- Feedback loop (if applicable):
- Rework cycles and cause:
- Verification:
- 14-day quality outcome:
- Builder decision: keep / revise / drop the practice, with one reason.
```

### #53 — 2026-08-11

- Arm: control
- Comparable-pair rationale: offline replay timing/state; paired with #54
  before implementation.
- Model / effort and exception, if any: Builder baseline. Session-level token
  and wall-clock usage were not surfaced/captured, so both are `UNAVAILABLE`.
- Active minutes / surfaced tokens / agents / tools: `UNAVAILABLE` /
  `UNAVAILABLE` / 1 / 10.
- Feedback loop: `PYTHONPATH=src python3 -m pytest
  tests/test_us002_virtual_replay_harness.py::TestLogReplayerModes::test_production_replayer_records_intervals_only_between_frames -q`
  (2 passed).
- Rework cycles and cause: 0.
- Verification: targeted regression (2 passed); `PYTHONPATH=src python3 -m
  pytest tests/test_us002_virtual_replay_harness.py -q` passed; `PYTHONPATH=src
  python3 -m pytest -q` passed; `git diff --check` passed.
- 14-day quality outcome: not yet observable.
- Builder decision: baseline complete. The narrow regression test established
  the cardinality contract without adding logging or changing safety-sensitive
  behavior.

### #54 — 2026-08-12

- Arm: diagnosis
- Comparable-pair rationale: offline replay timing/state; paired with #53
  before implementation.
- Model / effort and exception, if any: Builder baseline with the adapted
  diagnosis treatment. Session-level token and wall-clock usage were not
  surfaced/captured, so both are `UNAVAILABLE`.
- Active minutes / surfaced tokens / agents / tools: `UNAVAILABLE` /
  `UNAVAILABLE` / 1 / 6.
- Feedback loop: `PYTHONPATH=src python3 -m pytest
  tests/test_us002_virtual_replay_harness.py::TestLogReplayerModes::test_production_replayer_preserves_frequency_when_drift_rejects_speed -q`
  (red before fix; 1 passed after fix), backed by the minimized standalone
  `set_speed(2)` repro.
- Diagnosis record: the candidate frequency was committed before drift-budget
  validation. Alternatives considered: validation used a different rate,
  rounding created the invalid rate, or stale state was reconstructed later.
  Source order falsified the latter three for this case.
- Rework cycles and cause: 0.
- Verification: targeted regression (1 passed); minimized standalone repro
  preserved 1 Hz after rejection; `PYTHONPATH=src python3 -m pytest
  tests/test_us002_virtual_replay_harness.py -q` passed; `PYTHONPATH=src
  python3 -m pytest -q` passed; `git diff --check` passed.
- 14-day quality outcome: not yet observable.
- Builder decision: keep the diagnosis treatment for hard bugs. It forced a
  testable failure before changing state, without adding agents, logging, or
  user round-trips in this task.

### #56 — 2026-08-12

- Arm: control
- Comparable-pair rationale: offline replay developer compatibility; paired
  with #55 before implementation.
- Model / effort and exception, if any: Builder baseline. Session-level token
  and wall-clock usage were not surfaced/captured, so both are `UNAVAILABLE`.
- Active minutes / surfaced tokens / agents / tools: `UNAVAILABLE` /
  `UNAVAILABLE` / 1 / 9.
- Feedback loop: `PYTHONPATH=src python3 -m pytest
  tests/test_us002_virtual_replay_harness.py::TestLogReplayerModes::test_production_replay_modules_import_from_source_only_copy -q`
  (1 passed). The pre-fix isolated import failed with
  `ModuleNotFoundError: No module named 'tests'`.
- Scope decision: promoting replay support exposed an eager repository-schema
  load. Validator imports are now deferred to validation/guard operations, so
  importing the source package is side-effect-free while existing validation
  paths and schemas remain unchanged.
- Rework cycles and cause: 0.
- Verification: targeted source-only import regression (1 passed); focused
  US-002/debug/EV replay suite passed; `PYTHONPATH=src python3 -m pytest -q`
  passed; `git diff --check` passed.
- 14-day quality outcome: not yet observable.
- Builder decision: baseline complete. The repair keeps the test package as a
  compatibility shim while making the source package independently importable.

## Sources checked

- Matt Pocock, [`skills` repository README](https://github.com/mattpocock/skills), checked 2026-08-11. The repository positions its skills as composable and supports selective installation.
- [`diagnosing-bugs`](https://github.com/mattpocock/skills/blob/main/skills/engineering/diagnosing-bugs/SKILL.md), checked 2026-08-11.
- [`writing-for-agents`](https://github.com/mattpocock/skills/blob/main/skills/productivity/writing-for-agents/SKILL.md), checked 2026-08-11.
- [`tdd`](https://github.com/mattpocock/skills/blob/main/skills/engineering/tdd/SKILL.md), checked 2026-08-11. Its public-interface and agreed-seam guidance is retained as normal Builder practice, but is not a separately measured treatment.

## Uncertainty

- Token reporting varies by Codex surface. Missing surfaced usage makes token
  impact inconclusive; byte counts must not be substituted.
- Six tasks is too small to establish causation. The experiment is intended to
  detect a clear operational win or a clear reason not to adopt.
- Task matching is a human judgement. The pre-start comparability note limits,
  but cannot remove, that bias.
