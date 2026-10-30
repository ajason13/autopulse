---
title: Empirical Validation Report
description: Repository verification evidence and limits of AutoPulse experimental telemetry analysis.
---

AutoPulse has software validation and synthetic regression coverage. It has no
repository benchmark establishing vehicle fault-detection accuracy, warning lead
time before DTCs, calibrated failure prediction, or automotive compliance.
Passing a schema or software test does not certify vehicle or battery safety.

## Implemented Behavior and Evidence

| Surface | Repository evidence | What it establishes |
| --- | --- | --- |
| ICE data contract | `schemas/engine_obd_frame.schema.json`, `tests/test_engine_data_contract.py` | Acceptance/rejection of supplied frames under AutoPulse input policy. |
| ICE analysis | `src/autopulse/analysis/`, `tests/test_us003_pdm_algorithms.py`, `tests/test_us004_smoothing.py`, `tests/test_hdf_eligibility_policy.py`, `tests/test_osf_exposure_policy.py`, `tests/test_pdm_temporal_contract.py` | Deterministic synthetic score, eligibility, exposure, reset, and smoothing behavior. |
| EV pipeline | `tests/test_us006_*.py` | Schema validation, routing isolation, adapter policy, replay, and event serialization for supplied inputs. |
| Package boundary | `pyproject.toml`, `tests/packaging/test_package_contract.py` | Offline package inventory, including exclusion of `autopulse.live`. |

These paths refer to the [source repository](https://github.com/ajason13/autopulse).
Consult the tests and CI for the tested commit and environment; this page makes
no fixed test-count or cross-platform performance claim.

The current ICE implementation uses fixed heuristics and in-memory rolling
statistics. Learned vehicle-specific healthy-baseline training and persistence
are not implemented. The legacy `failure_probability` field is a bounded
experimental score; `HDF` and `OSF` identify software branches, not confirmed
vehicle failures. Zero does not establish health and one does not establish
certain failure. See the [analysis reference](../anomaly-detection/).

EV support is limited to validation, routing, replay, adapter guardrails, and
event serialization. EV anomaly scoring, remaining-life prediction, and live EV
capture are not implemented. Accepted protocol identifiers do not establish
standards certification or transport compatibility with a particular vehicle.

## External Research and Mapping Limits

The [UCI AI4I 2020 dataset documentation](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
(DOI: [10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C), checked 2026-10-29)
describes synthetic industrial-machine data, including process/air temperatures,
torque, tool wear, and rotational speed. Its label rules supplied historical
inspiration for AutoPulse's HDF/OSF experiments; they are not an automotive
validation dataset. No model is trained on those rows by the current analysis.

Kelvin-to-Celsius conversion preserves temperature differences but does not
establish equivalence between industrial process temperature and engine coolant.
OBD calculated load is not measured torque or tool wear. The old torque-to-load
mapping and RPM-product stress rationale do not substantiate bearing fatigue,
connecting-rod failure, or vehicle damage claims. The current OSF branch instead
tracks recent low-RPM/high-load exposure under a synthetic software policy.

The [ICE scoring policy](https://github.com/ajason13/autopulse/blob/main/docs/specs/ice-scoring-policy.md)
records the source comparison, units, synthetic acceptance vectors, and dated
observations. It establishes no calibrated physical-risk model.

## Input Bounds and Compliance Limits

US-001's 9,500 RPM ceiling and 140 °C coolant ceiling are repository input-policy
bounds. They do not establish universal valvetrain limits, coolant boiling points,
or failure thresholds across vehicles. The same distinction applies to EV
input bounds. Unsupported numerical accuracy and population-coverage assertions
have been removed; no automotive compliance verdict is asserted here.

## Live and Future Scope

The bounded ICE stationary smoke harness is available only in the repository;
`autopulse.live` is excluded from wheel and sdist distributions. Its operator
checklist and separate authorization still apply. Offline verification and
historical reviews do not authorize a vehicle connection.

Learned/persisted vehicle baselines and calibrated prediction remain future work
requiring a separate design, suitable data, and evaluation. They are not features
of the current package. Historical research and audit records retain their dated
provenance; they do not expand the current evidence above.
