---
title: Stationary Smoke Test
description: Run the first read-only AutoPulse vehicle check with the approved safety checklist.
---

The stationary smoke harness is AutoPulse's narrow bridge from replay-only validation to a first real-vehicle check. It is ICE-only, read-only, bounded, and designed for a parked vehicle under direct operator supervision.

:::caution[Scope]
Road testing, unattended operation, EV DID capture, ambient temperature PID `0x46`, VIN reads, DTC clearing, UDS writes, routines, security access, and session escalation are out of scope.
:::

## Preconditions

- Claude re-review passed for the smoke harness implementation.
- Vehicle is parked, stationary, and not on a public road.
- Parking brake is engaged.
- Operator is present and supervising.
- Adapter model and port are known.
- `vin_hashed` is precomputed outside AutoPulse.
- A finite capture limit is chosen, such as `--max-samples 60`.
- The operator has reviewed the repo checklist at `docs/operator-checklists/real-vehicle-smoke-harness.md`.

## Dry Run

Run a dry-run before connecting the harness to a live capture:

```sh
PYTHONPATH=src python3 -m autopulse.live.cli \
  --adapter-port /dev/tty.usbserial-EXAMPLE \
  --vin-hashed <64-lowercase-hex-sha256> \
  --output-path ./tmp/stationary-smoke.jsonl \
  --max-samples 60 \
  --dry-run
```

The dry-run should exit with code `0` and should not create the output JSONL file.

## Stationary Capture

After the dry-run succeeds and the checklist is complete:

```sh
PYTHONPATH=src python3 -m autopulse.live.cli \
  --adapter-port /dev/tty.usbserial-EXAMPLE \
  --vin-hashed <64-lowercase-hex-sha256> \
  --output-path ./tmp/stationary-smoke.jsonl \
  --max-samples 60 \
  --confirmed-stationary
```

Monitor `stderr` during capture. Stop on unexpected warning or error events.

## Safety Behavior

The harness:

- polls only the initial six ICE Mode 01 PIDs;
- enforces max 1 Hz cadence;
- validates every accepted frame against the engine OBD schema;
- writes only replay-compatible sanitized JSONL;
- aborts if `vehicle_speed > 0`;
- blocks write-capable services before transmission;
- logs adapter errors by error type only, not raw exception text.

## Output

Accepted samples conform to the engine OBD frame contract and contain `vin_hashed`, never raw VIN. Rejected samples are counted and logged, but raw rejected-frame content is not written.

Use the resulting JSONL with existing replay/debug tooling for offline inspection.
