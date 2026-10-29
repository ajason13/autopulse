# ICE experimental scoring policy

**Decision:** #118, 2026-10-28 UTC. Accepted for the offline implementation
issues listed below. Temporal handling (#119), OSF (#120), and HDF eligibility (#121) are implemented. Observation baseline:
`e5957cd4f1bc1ea06f6d4552a3ceec13b016900d`.

AutoPulse will treat ICE detector outputs as bounded experimental anomaly
scores, not calibrated failure probabilities. Replace lifetime OSF accumulation
with recent low-RPM/high-load exposure, and gate the legacy HDF experiment on an
observed running/warm-up sequence. The policy makes supplied synthetic streams
interpretable and reproducible; it establishes no vehicle diagnostic accuracy,
physical damage threshold, warning lead time, or maintenance recommendation.

## Scope and evidence

This record is authoritative for the #118 decision. The dated observations below
preserve the original runtime baseline; implementation ownership belongs to
[#119](https://github.com/ajason13/autopulse/issues/119)
(temporal/session handling), [#120](https://github.com/ajason13/autopulse/issues/120)
(OSF), and [#121](https://github.com/ajason13/autopulse/issues/121) (HDF eligibility).
Do not change schemas, diagnostic services, EV scoring, or train a model here.

The primary comparison is the
[UCI AI4I 2020 dataset documentation](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
(DOI: [10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C), accessed 2026-10-28 UTC).
It describes synthetic industrial-machine data. Its OSF rule multiplies tool
wear in minutes by torque in N·m, with limits 11,000/12,000/13,000 min·N·m for
L/M/H product-quality variants. Those variants are not vehicle classes. Its HDF
rule combines a process-to-air temperature difference below 8.6 K with tool
speed below 1,380 RPM. These are dataset label-generation rules, not evidence
that vehicle coolant-to-ambient temperatures or OBD load predict a failure.
Only the documentation was consulted; no dataset rows are copied or trained on.

Repository evidence:

| Surface | Observation |
| --- | --- |
| [OSFDetector](../../src/autopulse/analysis/osf_detector.py) and [constants](../../src/autopulse/analysis/utils.py) | Integrate `load_pct * rpm * exp(lugging_k) * seconds` when lugging, otherwise `load_pct * rpm * seconds`; reuse the dataset limits. State grows until `reset()`. |
| [HDFDetector](../../src/autopulse/analysis/hdf_detector.py) | Applies the temperature/speed conjunction even at RPM zero; its sigmoid product is called a probability without calibration evidence. |
| [PdMProcessor](../../src/autopulse/analysis/pdm_processor.py) | Invents one elapsed second on the first frame, smooths signals, integrates current OSF workload, and has no engine-state gate. Missing ambient skips HDF. |
| [ICE schema](../../schemas/engine_obd_frame.schema.json) | Allows zero RPM, coolant equal to ambient, and absent ambient. It supplies neither torque/tool wear nor a verified engine-warm flag. |
| [Algorithm tests](../../tests/test_us003_pdm_algorithms.py), [smoothing tests](../../tests/test_us004_smoothing.py) | Exercise implemented equations and sample-count filters; passing those tests does not validate a vehicle model. |

Current OSF units are percentage-points × rev/min × seconds (the lugging factor
is dimensionless), not min·N·m. Converting seconds to minutes or percent to a
fraction cannot supply missing torque, tool wear, or vehicle evidence. Retuning
the three limits until idle passes would preserve the dimensional mistake and
eventual saturation of any indefinitely positive workload integral.

## Reproduce the current counterexamples

From the repository root with the supported development environment installed:

```bash
PYTHONPATH=src .venv/bin/python scripts/probe_ice_scoring.py
```

The [probe](../../scripts/probe_ice_scoring.py) imports production detectors,
processor, and validator. Every supplied frame is schema-validated, timestamps
are fixed UTC, and the hash is a synthetic placeholder. No hardware, network,
wall-clock input or private telemetry is used; scores come from production code.
It prints observations rather than asserting that the defects must persist.

Observed on the baseline, CPython 3.14.6:

| Case | Actual result |
| --- | --- |
| Direct OSF, 850 RPM, load 18%, one second, class L | Increment 15,300 > 11,000; `OSF`, score field `1.0`. Explicit detector reset returns `s_idx` to zero. |
| Processor synthetic warm idle, coolant 88 °C, ambient 22 °C | First frame `OSF`, score `1.0`, `s_idx=15300`. |
| Same idle, 601 frames from t=0 through t=600 seconds | Last `OSF`, score `1.0`, `s_idx=9195300`; includes the invented first second. |
| Direct HDF, delta 0 K, RPM 0 | `1.0`. |
| Processor engine off, RPM/load 0, coolant/ambient both 22 °C | First frame `HDF`, score `1.0`, OSF stress zero. |
| Processor cold start, 850 RPM, load 18%, coolant/ambient both 22 °C | First frame `HDF`, score `1.0`; OSF is also saturated but loses the tie. |

These are counterexamples to the existing interpretation, not measurements of
healthy or faulty vehicles. Re-running after follow-up fixes should change the
observations; preserve this dated baseline, not tests that freeze these defects.

## Common score and time semantics

The #119 temporal/reset portion is implemented as documented in the
[processor time contract](processor-time-contract.md). OSF exposure is implemented
in #120 as described below. HDF eligibility is implemented in #121; this decision's dated observations above retain their original
baseline.

1. A score lies in `[0, 1]`; zero means no contribution from that branch, including
   when it is ineligible. Zero is **not** evidence of a healthy engine. One is
   the top of an experimental scale, not certain failure. An ineligible branch
   cannot supply an HDF/OSF alert; statistical and sensor-error paths stay
   independent. Tests must inspect branch state as well as the selected alert.
2. Retain `failure_probability` and existing failure-type strings for API
   compatibility in the implementation issues. Document their experimental
   meaning at the point of use; do not multiply by 100 and present a failure
   likelihood. Renaming/export migration is separate [#123](https://github.com/ajason13/autopulse/issues/123)
   work. A legacy `OSF`/`HDF` label identifies a branch, not a confirmed fault.
3. On a session's first accepted frame, seed time/filter state, accrue **zero**
   exposure, return zero HDF/OSF contributions, and only then establish any HDF
   arming state for the next frame. Never invent a one-second observation.
4. #119 owns timestamp parsing/rejection and complete reset implementation.
   The selected offline session-gap rule is `dt > 60 seconds`: reset before
   processing the next accepted frame, which becomes a first frame. `dt == 60`
   remains one continuous observed interval. This is a bounded replay
   convention, not a validated sensor freshness limit. Reject invalid or
   non-increasing timestamps before mutation; never clamp or use wall time.
5. Explicit session reset, a new processor, or a gap above that limit clears
   all buffers, temporal/coolant history, OSF interval history, and HDF arming.
   Changing vehicle identity requires a new processor, not reuse of the previous
   vehicle's state. No state is persisted between replay runs.
6. A rejected sensor/timestamp frame mutates none of that state. The next valid
   frame uses the last accepted timestamp, subject to the same gap rule; this
   makes the interpolation assumption visible rather than pretending the
   rejected sample was observed.

The 60-second convention reuses the project's existing nominal one-minute
analysis horizon at 1 Hz. It is a design bound, not a newly estimated vehicle
constant. Existing rolling summaries and Median(3) → EWMA filters remain
**sample-count based**, capacity 60 by default: 60 samples span 59 elapsed
seconds from first to last at 1 Hz, 29.5 at 2 Hz, or 118 at 0.5 Hz. Do not claim
that these filters or the statistical branch are cadence invariant.

## OSF decision: recent exposure fraction

Retire `load_pct * rpm * time`, the exponential penalty, class-specific dataset
limits, and their sigmoid from the processor scoring path in #120. Retain
legacy constructor arguments only for compatibility; L/M/H must yield the same
new score and must not imply vehicle calibration. Document the intentional
change to detector stress-state/helper semantics in that implementation.

For an accepted running sample, let the existing smoothed RPM/load be `r, l`.
Define a dimensionless experimental exposure indicator:

```text
q = 1 if 0 < r < 1500 RPM and l > 80 percent, else 0
W = 60 seconds
E(t) = integral of q(u) over [max(session_start, t - W), t)
osf_score(t) = E(t) / W
```

Use a **left-endpoint zero-order hold**: the previous accepted sample's `q`
applies on `[previous_time, current_time)`. A current value cannot retroactively
describe the preceding interval. Clip intervals exactly at `t - W` and discard
expired history. Missing pre-session time contributes zero; always divide by
the full W, not the short observed duration. Thus a first fault-like sample has
score zero, and one second of exposure yields `1/60`, not `1.0`.

Use raw RPM zero as an immediate engine-off gate **before** scoring: clear OSF
exposure and its held sample and return zero for OSF, even if smoothed RPM/load
still lag. Restart seeds a new exposure history. Do not clear independent
statistical/filter/thermal-guard state solely for this branch gate. Its raw
engine-off reset deliberately discards the interval ending at that sample;
only fully running observed intervals enter the exposure ledger.

The retained 1500 RPM / 80% boundaries are existing fixture heuristics, not a
validated definition of damaging lugging. There is no load-to-torque conversion.
Idle at 850/18 and steady operation at 2000/40 have `q=0` and score zero for any
duration. Persistent low-RPM/high-load input intentionally reaches one after
60 seconds; a real engine might tolerate that operating point. This score
measures recent time in a condition, not accumulated damage or failure risk.

Classify score `<= 0.5` as `NONE`, `0.5 < score < 1` as `OSF_ANOMALY`, and score
`1` as `OSF`. This aligns branch labels with the processor's existing strict
`> 0.5` anomaly gate. The old 0.8 × class-limit boundary is retired. Preserve
other branch selection/tie behavior; #123 owns wider alert-contract changes.

### OSF implementation and compatibility (#120)

[`OSFDetector`](../../src/autopulse/analysis/osf_detector.py) now exposes
`update(load_pct, rpm, elapsed_seconds)`: the first call seeds the indicator
without accruing exposure, then each call integrates the previous indicator.
Use elapsed seconds since the previous accepted sample. The processor supplies
smoothed load/RPM, gates on raw RPM zero, and owns session-gap resets. Direct
callers must reset at session boundaries themselves. Zero elapsed time adds no
exposure; negative elapsed time or nonfinite inputs raise before mutation.
Engine-off clears
only OSF, including its held indicator; a restart first seeds fresh history.

Intentional helper/state API changes: `s_idx` is now a read-only recent exposure
**duration in seconds**, not cumulative workload. `compute_stress_increment()`,
`update_stress_index()`, the class-specific `limit` attribute and `OSF_LIMITS`
constant are removed: scalar increments cannot represent interval expiry and
left-held transitions. Call `update()` instead; `OSF_WINDOW_SECONDS` is 60.
`vehicle_class` still accepts L/M/H with identical scoring.
`compute_probability(k=...)` retains its legacy name/argument, ignores `k`, and
returns `s_idx / 60`. It is an experimental exposure fraction, not a sigmoid or
calibrated probability. Alert `failure_probability` retains its API spelling
with that same interpretation for the OSF branch.

Only positive-exposure intervals are stored; adjacent intervals merge and
expired intervals are removed, with partial clipping at the horizon. No lifetime
ledger, persisted state or new telemetry logging is introduced. Existing alerts
and inspectable detector state provide the result for supplied-data replay.
[`test_osf_exposure_policy.py`](../../tests/test_osf_exposure_policy.py) validates
O1–O5, T2 and the OSF portion of R1 using production classes and schema-validated
processor fixtures. Cross-cadence equality applies to identical indicator
trajectories; the existing smoothing/statistical windows remain sample based.

## HDF decision: an armed synthetic experiment

The existing HDF conjunction and sigmoid remain only as a **synthetic** scoring
experiment implemented in #121. Do not invent a universal coolant operating temperature or
claim the AI4I process variable is a vehicle thermal model. An observed
warm-up latch prevents the specific near-ambient cold-start counterexample:

| Condition on an accepted frame | HDF contribution and next state |
| --- | --- |
| Raw RPM zero | Score zero; disarm immediately, regardless of smoothed RPM. |
| Ambient absent | Score zero; disarm. Never substitute ambient. |
| Running, ambient present, not previously armed | Score zero. Arm **for the next frame** only if both raw and smoothed `coolant - ambient >= 15 K`. |
| Previously armed, running, ambient present | Evaluate the existing HDF function with smoothed delta and RPM; remain armed. |
| Explicit/new session or gap reset | Disarm; first-frame rule applies. |

Requiring both raw and smoothed deltas for arming prevents stale smoothing
history from arming a restart at ambient temperature. Arming uses the existing
15 K sigmoid midpoint because it is outside that function's `>0.5` delta
component, not because it establishes physical engine warmth. A replay that
starts already warm may arm from its first frame, but is not evaluated until
the next. A cold stream may stay unarmed indefinitely; no timer manufactures
eligibility. Crossing 15 K is a mathematical fixture transition only.

After arming, the original strict critical conjunction (`delta < 8.6 K` and
`rpm < 1380`) gives score 1. Otherwise use the existing bounded sigmoid product,
including its noncritical cap of 0.99 and strict `>0.5` alert threshold. The
slopes have inverse-delta and inverse-RPM units respectively; the product is
an uncalibrated score. Preserve the existing thermal rate sensor-error guard,
including when HDF is ineligible. Rejected frames cannot arm or disarm HDF.
Branch gates do not bypass sensor validation or erase thermal-guard history.

This latch does not prove engine warmth. A healthy running engine cooling
after arming, an unusual ambient change, or noisy sensors could still produce
a false positive. It also misses a fixture starting already anomalous without
an arming observation. Those are explicit limits of the experiment, not
unresolved implementation decisions. No automotive HDF prediction is claimed.

### HDF implementation and compatibility (#121)

[`HDFDetector.update()`](../../src/autopulse/analysis/hdf_detector.py) owns the
latch and current `score`, taking raw RPM/delta and smoothed RPM/delta from the
processor after sensor/time guards pass. Missing ambient is represented by
`None`, never an invented temperature. `armed` exposes the next-frame latch;
`reset()` clears both latch and score. The processor's existing complete session
reset creates a fresh detector, so even an already-warm first frame returns
zero before arming for the following frame. Engine-off or ambient loss clears
only HDF eligibility, leaving statistical/filter/thermal-guard state independent.

The legacy static `compute_probability()` remains the pure equation for
already-eligible synthetic inputs; it does **not** apply operating-state gates
or maintain eligibility. Direct callers seeking the complete policy must use
`update()` on accepted finite samples and call `reset()` at session boundaries.
The processor enforces input/temporal rejection before detector updates. The
`failure_probability` alert field retains its API name and experimental-score
meaning. Existing alerts and inspectable `armed`/`score` state suffice for offline
debugging; no frame logging or telemetry collection is added.

[`test_hdf_eligibility_policy.py`](../../tests/test_hdf_eligibility_policy.py)
covers H1–H6 and R1 through production classes and schema-validated synthetic
fixtures, including raw-versus-smoothed arming, independent branch execution,
full-state rejection snapshots, strict critical boundaries, full-window cooling,
and reset/replay equality. Boundary fixtures explicitly use capacity one to
remove smoothing latency; the normal warm-up/cooling fixtures use the default
60-sample production filters. Scores establish deterministic fixture behavior,
not vehicle accuracy or calibrated risk.

## Acceptance vectors for implementation

Times below are elapsed seconds on a fixed UTC synthetic clock. All frames use
the full ICE schema, finite values and a synthetic hash. Validate them before
processing. Units are RPM, percent load, °C temperatures and elapsed seconds.
OSF-only fixtures omit ambient to isolate HDF; eligible HDF fixtures use load
18 and running RPM 850 so OSF's indicator stays zero. A statistical alert may
coexist during transitions: assert branch scores/state separately, and only
assert the final alert after explicitly checking branch competition.

| ID / owner | Vector and checkable outcome |
| --- | --- |
| T1 / #119 | Missing/malformed/nonfinite timestamp, duplicate time or backward time: documented rejection/`SENSOR_ERROR` before mutation. Snapshot all state. Repeat replay twice: identical alerts, timestamps and state; no wall clock. |
| T2 / #119, #120 | First frame at any valid timestamp: zero OSF/HDF, seeded state. Positive exposure at t=0 then t=60: score 1; t=60.001 instead: gap reset, score zero. Large gaps must not integrate or compare stale coolant. |
| O1 / #120 | Constant 850/18 idle and 2000/40 steady fixtures at 0.5, 1 and 2 Hz for 600 seconds: OSF score zero throughout, across L/M/H. No gradual saturation. Temperatures fixed at 88. |
| O2 / #120 | Detector-level held `q=1` from t=0: scores at t=0,1,30,31,60 are 0,1/60,0.5,31/60,1. Labels NONE,NONE,NONE,OSF_ANOMALY,OSF. Establish constant 1000/90 smoothed inputs in processor tests too. |
| O3 / #120 | Detector-level `q=1` on [0,30), `q=0` thereafter: E(30)=30, E(60)=30, E(75)=15, E(90)=0 seconds; scores 0.5,0.5,0.25,0. Covers partial expiry. A sample at t=30 changes only future intervals. |
| O4 / #120 | Indicator boundaries: 1500/90, 1000/80, and zero RPM all give q=0; 1499/80.1 gives q=1. After nonzero exposure, accepted raw RPM zero clears it immediately even with lagging smoothing. First restart sample scores zero; next uses only restart exposure. |
| O5 / #120 | Same held indicator trajectory with edges at common timestamps, subdivided into 0.5,1,2-second or irregular intervals of at most 60 seconds: identical E/score at common times, absolute tolerance 1e-9. Include non-grid window clipping, e.g. t=75.25 gives E=14.75 for O3. |
| H1 / #121 | Direct/processor raw RPM zero with coolant=ambient=22: HDF zero/disarmed. Running 850/18 with coolant rising from 22 to 36 in 1 °C/second steps (ambient22): zero HDF throughout, never armed. |
| H2 / #121 | Continue that warm-up to coolant88 at 1 °C/second and hold: no HDF alert; arm only when both raw and smoothed deltas reach15. First already-warm 88/22 frame scores zero and arms; subsequent stable warm frames score below0.5. |
| H3 / #121 | Warm at 88/22 for 120 one-second samples, then cool to27 by 1 °C/second and hold for120 samples at RPM850/load18. Rate guard passes; after smoothing settles below8.6 K, armed HDF reaches1. This is a synthetic condition injection, not a vehicle fault experiment. |
| H4 / #121 | With eligibility established, direct HDF delta8.5/RPM1379 gives1; delta8.6/RPM1379 and delta8.5/RPM1380 give<1; delta12/RPM1100 is strictly between0.5 and1. Processor boundary tests must account for smoothing. |
| H5 / #121 | From armed state, remove ambient: zero/disarm, OSF/statistics still execute. Restore ambient while raw delta<15: remain unarmed despite stale smoothed temperature. Engine-off disarms too. New session/gap reset requires rearming. |
| H6 / #121 | Coolant jump greater than5 °C/s yields SENSOR_ERROR in armed and unarmed states with no buffer, exposure, time or latch mutation. Exactly5 °C/s passes this existing software guard; no physical validation of that limit is claimed. |
| R1 / #119–#121 | Reset after nonzero exposure and armed HDF, replay the original sequence: same state/score timeline as a fresh processor; all buffers/history/latches reset. |

O5's equality is conditional on the **same detector-input indicator trajectory**;
it is an integration invariant, not a claim that different sampling cadences
produce the same smoothed inputs. Processor cadence tests use constant signals
for O1/O2; changing signals retain US-004's documented sample-domain latency.
Do not change smoothing parameters to make those outputs agree. Healthy and
fault labels in this table describe constructed fixtures, not ground truth
about vehicles. These vectors supplement existing algorithm/smoothing tests;
update expectations only when the owning implementation changes the behavior.

## Verification and delivery boundaries

#118 verification is the production probe above, cross-checking the cited source
and code, checking policy arithmetic/boundaries, and reviewing the decision and
downstream vectors with a fresh-context Codex reviewer. No runtime correction
or passing future-behavior test is claimed here. The document lives alongside
other repository design records; the Starlight site does not ingest this file.

The owning implementations must run production-backed focused algorithm,
processor and smoothing regressions, the full Python suite, required hosted
checks, and fresh-context review. #119, #120, and #121 are implemented. The next
implementation in the offline track is #122 (optional ambient replay).
The complete replay/export demonstration remains
[#126](https://github.com/ajason13/autopulse/issues/126). Broader public wording
cleanup remains [#130](https://github.com/ajason13/autopulse/issues/130), and
learned/calibrated vehicle-baseline research remains separately scoped in
[#137](https://github.com/ajason13/autopulse/issues/137). This decision authorizes
neither live capture nor release publication.
