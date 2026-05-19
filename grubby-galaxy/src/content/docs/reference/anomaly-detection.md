---
title: Anomaly Detection Reference
description: Technical reference for the US-003 predictive maintenance algorithms, alert outputs, and rolling-window statistics.
---

US-003 implements AutoPulse's predictive maintenance analysis layer under `src/autopulse/analysis/`. The processor consumes validated US-001 engine frames, maintains rolling temporal state, and emits `PdMAlert` objects for downstream UI, reporting, and audit workflows.

The implementation is intentionally computational only. It does not open CAN, serial, socket, or OBD connections, and it does not issue diagnostic commands. All vehicle interaction remains read-only.

## Implementation Map

| Component | File | Responsibility |
| --- | --- | --- |
| `PdMProcessor` | `src/autopulse/analysis/pdm_processor.py` | Orchestrates frame validation, rolling buffers, detector evaluation, and alert selection. |
| `PdMAlert` | `src/autopulse/analysis/pdm_processor.py` | Public alert payload for anomaly status, probability, primary PID, rolling-window summary, and source frame. |
| `HDFDetector` | `src/autopulse/analysis/hdf_detector.py` | Heat Dissipation Failure probability and thermal rate guard. |
| `OSFDetector` | `src/autopulse/analysis/osf_detector.py` | Overstrain Failure stress accumulation, classification, and probability. |
| `CircularBuffer` | `src/autopulse/analysis/circular_buffer.py` | Fixed-size rolling storage for the 60-second analysis window. |
| Statistical helpers | `src/autopulse/analysis/utils.py` | Shared constants, sigmoid, Z-score, and IQR bounds. |

## Alert Contract

`PdMAlert` is the output surface exposed by the processor:

```python
@dataclass
class PdMAlert:
    timestamp: int
    vin_hashed: str
    failure_probability: float
    failure_type: FailureType
    is_anomaly: bool
    primary_pid: int | None = None
    window_summary: WindowSummary | None = None
    obd_frame: dict[str, Any] | None = None
```

`vin_hashed` must be a lowercase 64-character SHA-256 digest. Raw VINs are rejected before alert creation.

Supported `failure_type` values are:

| Value | Meaning |
| --- | --- |
| `NONE` | No active anomaly over the current frame and rolling window. |
| `HDF` | Heat Dissipation Failure branch is the dominant signal. |
| `OSF_ANOMALY` | Overstrain Failure branch crossed the warning threshold but not the hard limit. |
| `OSF` | Overstrain Failure branch reached the class-specific hard limit. |
| `STATISTICAL_ANOMALY` | Rolling-window Z-score or IQR gate detected a monitored PID outlier. |
| `SENSOR_ERROR` | Required PID missing or coolant rate-of-change guard failed. |

## Processing Sequence

For each frame, `PdMProcessor.process_frame()` performs the following sequence:

1. Parse the timestamp into Unix milliseconds.
2. Validate mandatory analysis PIDs: `engine_rpm`, `engine_load`, and `coolant_temp`.
3. Compute elapsed seconds from the previous accepted frame, defaulting to 1 second for the first frame.
4. Run the coolant thermal rate guard before updating rolling buffers.
5. Push accepted RPM, coolant, and load values into 60-sample circular buffers.
6. Generate rolling-window statistics and evaluate statistical anomaly gates.
7. Evaluate HDF when optional `ambient_temp` is present.
8. Accumulate OSF stress using the current frame.
9. Select the highest-priority alert branch and return `PdMAlert`.

Sensor-error frames do not enter the rolling buffers. This prevents physically impossible coolant jumps from corrupting future statistical baselines.

## Heat Dissipation Failure

HDF models insufficient heat rejection using coolant-to-ambient delta and RPM. The critical trigger is a strict conjunction:

```python
if delta_t < 8.6 and rpm < 1_380:
    return 1.0
```

Where:

| Term | Source | Meaning |
| --- | --- | --- |
| `delta_t` | `coolant_temp - ambient_temp` | Cooling delta in degrees Celsius; deltas are scale-invariant with Kelvin. |
| `8.6` | `HDF_DELTA_T_THRESHOLD_K` | AI4I-derived critical delta threshold. |
| `1_380` | `HDF_RPM_THRESHOLD` | AI4I-derived low-RPM threshold. |

When the hard HDF trigger is not met, the detector computes an early-warning probability:

```python
p_dt = sigmoid(15.0 - delta_t, 0.0, k_dt=0.8)
p_rpm = sigmoid(1_380.0 - rpm, 0.0, k_rpm=0.003)
probability = min(0.99, p_dt * p_rpm)
```

`ambient_temp` is optional in US-001. Frames without `ambient_temp` skip HDF evaluation and remain eligible for OSF and statistical anomaly detection.

## Thermal Rate Guard

Coolant temperature is guarded by a physics-derived maximum rate of change:

```python
rate = abs(curr_temp - prev_temp) / elapsed_seconds
return rate > 5.0
```

If the rate exceeds 5 degrees Celsius per second, the processor returns:

```python
failure_type = "SENSOR_ERROR"
primary_pid = 0x05
```

The guard fails closed. Invalid elapsed-time inputs return `SENSOR_ERROR` rather than silently bypassing validation.

## Overstrain Failure

OSF models mechanical stress as accumulated workload over time:

```python
wf = load_pct * rpm
gamma = exp(0.3) if rpm < 1_500 and load_pct > 80.0 else 1.0
stress_increment = wf * gamma * elapsed_seconds
```

The processor adds the current frame's increment before classifying the alert, so a frame that crosses the OSF threshold is reported immediately.

Class-specific hard limits are:

| Vehicle class | `S_limit` |
| --- | ---: |
| `L` | `11_000.0` |
| `M` | `12_000.0` |
| `H` | `13_000.0` |

Classification:

| Condition | Result |
| --- | --- |
| `S_idx >= S_limit` | `OSF` |
| `S_idx >= 0.8 * S_limit` | `OSF_ANOMALY` |
| otherwise | `NONE` |

The OSF probability is a sigmoid anchored at the anomaly lower bound:

```python
anomaly_lo = 0.8 * S_limit
probability = sigmoid(S_idx, anomaly_lo, k=0.001)
```

## Rolling Window Statistics

The processor maintains three `CircularBuffer` instances:

| Buffer | PID | Field |
| --- | --- | --- |
| RPM | `0x0C` | `engine_rpm` |
| Coolant temperature | `0x05` | `coolant_temp` |
| Engine load | `0x04` | `engine_load` |

The default capacity is 60 samples. At 1Hz polling, this represents a 60-second analysis window. `push()` is O(1): it appends until capacity, then overwrites the oldest value using `_head % capacity`.

Each window summary exposes:

| Metric | Meaning |
| --- | --- |
| `min` | Minimum value in the current rolling window. |
| `max` | Maximum value in the current rolling window. |
| `avg` | Arithmetic mean. |
| `std_dev` | Sample standard deviation. |
| `z_score` | Z-score of the latest accepted value. |
| `iqr_low` | Lower IQR fence: `Q1 - 1.5 * IQR`. |
| `iqr_high` | Upper IQR fence: `Q3 + 1.5 * IQR`. |
| `is_statistical_outlier` | `true` when the latest value is outside the IQR fences. |

The statistical anomaly gate promotes the alert when any monitored PID satisfies either condition:

```python
abs(z_score) > 3.0
is_statistical_outlier is True
```

When no HDF or OSF branch has a stronger probability, this emits:

```python
failure_type = "STATISTICAL_ANOMALY"
failure_probability = 0.85
primary_pid = 0x0C | 0x05 | 0x04
```

## Verification

US-003 is covered by `tests/test_us003_pdm_algorithms.py`, including:

- HDF strict-boundary behavior.
- OSF class thresholds and lugging penalty.
- Thermal rate guard behavior.
- 60-sample circular buffer ordering and overwrite behavior.
- Z-score and IQR window summary exposure.
- Statistical anomaly promotion.
- VIN hash enforcement and read-only computational boundaries.

Current release verification:

```bash
python3 -m pytest -q
```

Expected result:

```text
284 passed
```
