# Real Vehicle Smoke Harness Operator Checklist

Status: Required before any stationary vehicle smoke test. A second Claude implementation audit is still required before use.

## Preflight

- Vehicle is parked, stationary, and not on a public road.
- Parking brake is engaged.
- Operator is in the vehicle or directly supervising the vehicle.
- No unattended operation.
- Adapter model and port are known.
- `vin_hashed` is precomputed outside AutoPulse and supplied with `--vin-hashed`.
- AutoPulse will not read VIN.
- Output JSONL path is explicit.
- Runtime log path, if used, is explicit and does not contain `..`.
- `--max-samples` or `--max-duration-seconds` is set.
- `--confirmed-stationary` is supplied only after the operator confirms stationary setup.

## During Capture

- Do not drive.
- Do not leave the vehicle unattended.
- Stop immediately if the vehicle moves, warning lights change, the adapter disconnects, or the operator is uncertain.
- The harness should abort automatically if `vehicle_speed > 0`.

## Stop Conditions

- Motion is detected.
- Adapter disconnects.
- Unsupported protocol is detected.
- Any write-capable service is attempted.
- Raw VIN or raw payload leakage is suspected.
- Operator presses Ctrl-C.

## Expected Command Shape

```sh
PYTHONPATH=src python3 -m autopulse.live.cli \
  --adapter-port /dev/tty.usbserial-EXAMPLE \
  --vin-hashed <64-lowercase-hex-sha256> \
  --output-path ./tmp/stationary-smoke.jsonl \
  --max-samples 60 \
  --confirmed-stationary
```

Run `--dry-run` first. Do not run against a real vehicle until Claude signs off on the implementation.
