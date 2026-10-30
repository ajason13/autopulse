---
title: Anomaly Detection Reference
description: Experimental ICE scores, eligibility, exposure windows, and alert semantics.
---

`PdMProcessor` consumes validated ICE frames and emits `PdMAlert` objects. It is
computational: it opens no vehicle connection or transport. Callers must validate
complete frames against US-001 before analysis; processor sensor/time guards do
not replace the schema validator.

Analysis uses fixed heuristics and in-memory rolling statistics. Learned
healthy-baseline training and persistence and calibrated prediction are not
implemented. The legacy `failure_probability` field is an experimental score in
`[0, 1]`, not measured failure likelihood. A zero score does not establish vehicle
health; one does not establish certain failure. See [evidence and limitations](../empirical-validation/).

## Implementation and Contracts

| Component | Repository path | Responsibility |
| --- | --- | --- |
| `PdMProcessor`, `PdMAlert` | `src/autopulse/analysis/pdm_processor.py` | Time/sensor guards, session state, filters, statistics, and alert selection. |
| `HDFDetector` | `src/autopulse/analysis/hdf_detector.py` | Eligibility-aware synthetic thermal scoring and rate guard. |
| `OSFDetector` | `src/autopulse/analysis/osf_detector.py` | Finite-horizon low-RPM/high-load exposure. |
| `CircularBuffer` | `src/autopulse/analysis/circular_buffer.py` | Fixed sample-count storage. |

The [ICE scoring policy](https://github.com/ajason13/autopulse/blob/main/docs/specs/ice-scoring-policy.md),
[processor time contract](https://github.com/ajason13/autopulse/blob/main/docs/specs/processor-time-contract.md),
and [ICE alert export contract](https://github.com/ajason13/autopulse/blob/main/docs/specs/ice-alert-export-contract.md)
provide detailed rules, compatibility changes, and synthetic acceptance vectors.
These are software policies, not vehicle-calibrated physical limits.

## Processing and Session State

1. Parse time to Unix milliseconds; reject invalid or non-increasing timestamps before mutation.
2. Check required analysis PIDs and finite numeric inputs. Sensor rejection leaves accepted state unchanged.
3. For continuous sessions, reject coolant changes above the software guard of 5 °C/s before updating state.
4. Seed a first frame, or reset the complete session for a gap greater than 60 seconds. Such frames accrue zero HDF/OSF contribution. Exactly 60 seconds remains continuous.
5. Store accepted raw RPM, coolant, and load samples; compute smoothing and rolling statistics.
6. Evaluate HDF eligibility and OSF exposure, then select the alert. A statistical outlier contributes when neither HDF nor OSF score exceeds 0.5.

Explicit `reset()` clears buffers, coolant/time history, HDF arming, and OSF
exposure. State is not persisted between runs. Replaying from the start requires
a reset or new processor. Legacy naive ISO timestamps mean UTC; numeric
processor timestamps are Unix milliseconds. Full input representation rules
are in the time contract above.

## HDF Eligibility and Score

Raw RPM zero or absent ambient temperature disarms HDF and yields zero HDF
contribution. Otherwise, while unarmed, both raw and smoothed coolant-to-ambient
deltas must reach at least 15 K to arm the next accepted frame. The arming frame
itself contributes zero. This synthetic latch is not a measured engine-warm flag.

For already-eligible inputs, the retained equation returns 1.0 when smoothed
delta is strictly below 8.6 K and smoothed RPM is strictly below 1,380.
Otherwise it uses the sigmoid product capped at 0.99. Those thresholds originated
in an industrial synthetic label rule; they do not establish vehicle cooling
failure. Use `HDFDetector.update()` for eligibility-aware behavior;
`compute_probability()` alone is only the legacy pure equation.

## OSF Exposure and Score

OSF holds the previous accepted smoothed sample's indicator over each observed
interval. Exposure is active only for `0 < rpm < 1500` and `load_pct > 80`.
The interval ledger clips exposure to the most recent 60 seconds:

```python
score = exposure_seconds / 60.0
```

First samples seed the held indicator without inventing elapsed time. Raw RPM
zero resets OSF immediately even if smoothing still carries prior RPM. Session
reset clears the ledger. The legacy `vehicle_class` values L/M/H all use this
same policy; they do not represent calibrated vehicle classes. Lifetime stress
accumulation, torque/RPM products, and class-specific hard limits are not the
current algorithm.

## Smoothing and Statistics

The trailing three-point median feeds EWMA with alpha 0.3 for RPM/load and 0.1
for coolant. These fixed software coefficients can suppress isolated spikes and
delay transitions; they have no vehicle calibration. Raw signals also gate HDF
eligibility and engine-off handling.

Raw per-channel buffers hold 60 samples by default. Cadence changes their time
span; this sample window is separate from OSF's 60-second exposure ledger. Window
summaries contain min, max, mean, sample standard deviation, Z-score, and IQR
fences. An absolute Z-score above 3 or a value outside the IQR fences can select
`STATISTICAL_ANOMALY` with a fixed score of 0.85. That constant is a software alert
level, not an accuracy percentage or inferred vehicle-failure probability.

## Alert Interpretation

`PdMAlert` includes timestamp, hashed vehicle identifier, score, failure type,
anomaly flag, optional primary PID, window summary, and source frame. The
[export contract](https://github.com/ajason13/autopulse/blob/main/docs/specs/ice-alert-export-contract.md)
retains sanitized summaries and excludes the raw source frame from serialization.

| Label | Software meaning |
| --- | --- |
| `NONE` | No selected score above 0.5; does not establish health. |
| `HDF` | Eligible HDF branch selected above 0.5. |
| `OSF_ANOMALY` | Selected exposure fraction above 0.5 and below 1.0. |
| `OSF` | Selected exposure fraction reaches 1.0. |
| `STATISTICAL_ANOMALY` | Raw rolling statistics selected an outlier. |
| `SENSOR_ERROR` | Required analysis input or coolant rate guard rejected a frame; anomaly flag is false. |

## Verification Scope

`tests/test_us003_pdm_algorithms.py` and `tests/test_us004_smoothing.py` exercise
production classes with synthetic inputs. Run them from an installed development
environment as described in [Getting Started](../../guides/getting-started/):

```sh
./.venv/bin/python -m pytest tests/test_us003_pdm_algorithms.py tests/test_us004_smoothing.py -q
```

Use the guide's native executable path in PowerShell. Passing these tests verifies
the software rules for supplied fixtures. It does not measure automotive
accuracy, validate warning lead time, train a model, or authorize vehicle use.
EV support remains validation/routing/replay/event serialization without anomaly
scoring; see [US-006](../../specs/us-006-ev-telemetry-data-contract/).
