# Offline processor time and sessions

Implemented for [#119](https://github.com/ajason13/autopulse/issues/119) in
[`PdMProcessor`](../../src/autopulse/analysis/pdm_processor.py), following the
[ICE scoring decision](ice-scoring-policy.md#common-score-and-time-semantics).
This is a supplied-data replay convention, not a vehicle sensor freshness or
physical safety limit. OSF follows the implemented recent-exposure policy in
#120; HDF eligibility remains in #121.

`process_frame()` accepts ISO timestamps, including `Z` and explicit UTC offsets,
and legacy numeric Unix **milliseconds** (integers or finite floats). Naive ISO
times are interpreted as UTC so the host timezone cannot change replay results.
Python's ISO parser also retains its date-only forms, interpreted at midnight
UTC. ISO fractions are truncated to millisecond precision; numeric milliseconds
use integer truncation toward zero. Epoch zero and negative Unix times work.
Times must fit the UTC datetime range, years 1–9999.

Missing, malformed, nonfinite, boolean, unsupported-type or out-of-range times
raise `ValueError` before any state change. A frame's timestamp must be strictly
greater than the last accepted timestamp at millisecond resolution. Duplicate
and backward times also raise `ValueError`; callers should catch rejection or
reset explicitly before replaying from the beginning. Exceptions contain a
fixed reason, not the supplied frame. The processor never substitutes wall time
or clamps an elapsed interval. The `preview-alerts` CLI skips temporally rejected
rows using its existing sanitized rejection counter/log and continues the session.
These are intentional API changes from the old
fallback and clamping behavior; the alert timestamp field remains Unix
milliseconds. Schema-facing ingestion still requires the existing timezone-aware
ISO string contract: these legacy processor inputs do not widen the JSON schema.

The first accepted frame seeds raw and Median(3) → EWMA buffers and temporal
history. It adds zero OSF stress and returns zero HDF/OSF contributions. At a
strictly greater than **60-second** gap since the last accepted frame, clear the
previous session before processing the new frame as a first frame. Exactly 60
seconds stays continuous. A gap never contributes cross-session stress or a
thermal-rate comparison against stale coolant. Within a continuous session,
OSF integrates the previous accepted smoothed indicator over a rolling
60-second horizon; see the [scoring policy](ice-scoring-policy.md#osf-decision-recent-exposure-fraction).

`reset()` discards all six raw/median buffers, detector state and timestamp/coolant
history, retaining the configured VIN hash, vehicle class and window capacity.
A new processor is required for a different vehicle. No state is persisted.
Reset followed by the same replay matches a fresh processor's alerts and state.
OSF interval history and its held indicator participate in this reset boundary;
future HDF eligibility latches must do so when #121 introduces them.

Missing mandatory PIDs retain `SENSOR_ERROR` with the corresponding PID. Invalid
or nonfinite consumed numeric sensor values return `SENSOR_ERROR`; the processor
is not a substitute for the full frame schema validator. Within a session the
existing coolant rate guard rejects changes strictly above 5 °C/s, and accepts
exactly 5 °C/s. Sensor rejection and handled smoothing failures leave all buffers,
detectors and accepted time/history unchanged, including when a supplied time
would otherwise begin a new session. The next valid frame measures elapsed time
from the last accepted frame, subject to the same gap rule. Smoothing stages
copies of the bounded buffers so a handled failure can roll back. Existing
alerts and explicit exceptions provide the rejection signal; no logging of
frames or new telemetry collection is needed.

The default window holds **60 samples**, not 60 elapsed seconds. First-to-last
span is 59 seconds at 1 Hz, 29.5 at 2 Hz, and 118 at 0.5 Hz. The median width of
3, EWMA coefficients, raw statistical windows and their sample-domain behavior
are unchanged. The session gap and OSF exposure use elapsed time;
statistical/filter output is not generally cadence invariant.

Verification: [`test_pdm_temporal_contract.py`](../../tests/test_pdm_temporal_contract.py)
covers policy T1/T2/R1 using production classes: full-state rejection snapshots,
time representations, first-frame behavior, 60/60.001-second boundaries, large
gaps, sensor/thermal/smoothing rejection, reset/replay equality and sample-count
windows at multiple cadences. OSF policy coverage lives in
[`test_osf_exposure_policy.py`](../../tests/test_osf_exposure_policy.py); HDF arming
remains separate downstream work. These tests establish deterministic software
behavior,
not calibrated failure prediction or vehicle accuracy.
