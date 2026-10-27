# Real Vehicle Smoke Harness Operator Checklist

Status: Required before any stationary vehicle smoke test. Claude re-review passed after PR #33, and PR #36 merged explicit protocol `6` live-adapter connection settings. Use is conditional on this checklist, confirmed protocol compatibility, and a successful dry-run.

## Preflight

- Vehicle is parked, stationary, and not on a public road.
- Parking brake is engaged.
- Operator is in the vehicle or directly supervising the vehicle.
- No unattended operation.
- Adapter model and port are known.
- Target vehicle is confirmed compatible with ISO 15765-4 CAN protocol `6` (11-bit ID, 500 kbps); do not rely on adapter auto-discovery.
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
- Protocol `6` compatibility is uncertain.
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

Run `--dry-run` first. It validates configuration without opening the adapter; it does not verify hardware connectivity or vehicle protocol compatibility. Do not run against a real vehicle unless protocol `6` compatibility is confirmed and every preflight item above is satisfied.
