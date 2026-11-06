# Synthetic offline ICE analysis

This small fixture exercises the production package without importing `tests`
or using vehicle data. The repeated `a` and `b` SHA-256-shaped identifiers are
synthetic. It runs locally without network or hardware access.

## Install and run

Use CPython 3.13 or 3.14. From the repository root, install the package in a
virtual environment; activation is unnecessary. These source-development
installation commands use the network to resolve runtime dependencies.

macOS/Linux:

```sh
python3.14 -m venv .venv
./.venv/bin/python -m pip install .
./.venv/bin/autopulse-debug analyze-ice --jsonl examples/synthetic-ice.jsonl > analysis.json
```

Native Windows PowerShell:

```powershell
py -3.14 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install .
& .\.venv\Scripts\autopulse-debug.exe analyze-ice --jsonl examples/synthetic-ice.jsonl > analysis.json
```

An installed wheel exposes the same command from any working directory. Copy
`synthetic-ice.jsonl` to that directory and run
`autopulse-debug analyze-ice --jsonl synthetic-ice.jsonl > analysis.json` using
the environment's executable. The fixture is supplied separately, rather than
embedded in the wheel. See the [offline package guide](../docs/offline-package.md)
for the locked wheelhouse installation procedure.

## Expected results

The report has `ok: true`, `powertrain_type: ICE`, `total_rows: 8`,
`accepted_frames: 5`, and `rejected_frames: 3`. Its `vehicles` array contains
the `a` identity first and the `b` identity second. Each contains its own
`vin_hashed` and `observations` array.

| Physical line | Identity | Expected result |
| --- | --- | --- |
| 1 | a | Accepted, `NONE`, session seed |
| 2 | b | Accepted, `NONE`, independent session seed |
| 3 | a | Accepted, `NONE`, healthy idle |
| 4 | b | Accepted, `HDF`, score 1.0 |
| 5 | b | Rejected at `input`: RPM 9501 exceeds the schema maximum |
| 6 | b | Rejected at `analysis`: duplicate accepted timestamp |
| 7 | b | Rejected at `analysis`: implausible coolant rate (`SENSOR_ERROR`) |
| 8 | b | Accepted, `HDF`, score 1.0; rejected rows left state intact |

Healthy scores are approximately zero (floating-point arithmetic can leave a
tiny positive value). Accepted times are Unix milliseconds: `1779789600000`,
`1779789601000` for a; `1779789600000`, `1779789601000`, `1779789603000` for b.
Each window summary retains RPM 900, coolant 88, and load 5 for min/max/average,
with zero standard deviation and z-score and no statistical outlier.

The deliberate ambient change from 25 to 80 degrees Celsius drives only b's
eligible, previously warmed HDF delta below its threshold. This is an artificial
branch demonstration, not evidence of a physical vehicle fault. The exported
legacy field `failure_probability` is an experimental heuristic score, not a
calibrated likelihood of failure. See the
[ICE scoring policy](../docs/specs/ice-scoring-policy.md).

## Input and output contract

`analyze-ice` accepts only flat canonical
[US-001 ICE rows](../schemas/engine_obd_frame.schema.json). Each raw row is
validated before replay normalization; the canonical replay packet is validated
again before analysis. Missing required fields, protocol aliases, EV frames,
shared envelopes, command metadata, and unknown properties are rejected rather
than repaired or stripped. Input order is preserved within each identity;
timestamps must increase per identity at millisecond resolution. Existing
processor session-gap and sensor guards apply.

Blank lines do not count. Every nonblank line counts exactly once as accepted
or rejected, including malformed JSON and non-object JSON. `rejections` reports
the physical `row_index` and one fixed `stage`: `input`, `replay`, or `analysis`.
Rejected values and exception text are omitted. An empty or entirely rejected
file returns a completed report with zero observations. Exit 0 means the file
was processed; inspect the rejection count to decide whether its contents met
your needs. File, decoding, or export failures return exit 1 and a fixed error
without a partial stdout report.

Every accepted frame exports an existing JSON-LD observation, including `NONE`.
The exporter omits the raw frame and emits finite values and validated identity
hashes. The report partitions observations in first-accepted identity order;
within each partition, output follows input order. All stable fields are
deterministic; `@id` uses a fresh UUID and must be excluded from comparisons.
JSON-LD context URLs are identifiers and are not fetched at runtime.

Structured rejection logs go to stderr with row numbers and stages. Add
`--verbose` before `analyze-ice` for existing validation/replay/export debug
events and completion counts. Keep outputs under operator control; valid
identity hashes remain present. This flow holds the result and rolling state
in memory and is intended for small local fixtures, not unattended monitoring.
