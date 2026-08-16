# AutoPulse Offline Package

AutoPulse is an educational, read-only OBD-II validation, analysis, and replay
package. This distribution operates on previously supplied local JSON/JSONL/CSV
input. It does not connect to a vehicle, collect telemetry, or use a network at
runtime.

## Supported release cells

The intended support matrix is CPython 3.13 and 3.14 on Ubuntu 24.04 x86_64,
macOS 15 or newer on Apple Silicon or Intel, and Windows 11 x86_64. A cell is
not release-supported until its native wheel-only installation and offline
replay evidence passes. CPython 3.12 and older, PyPy, prereleases,
free-threaded Python, containers, and other operating systems are outside this
profile.

## Disconnected installation

Use only the wheelhouse and hashed requirements export produced for the exact
Python/OS/architecture cell. On a disconnected machine, run:

```text
python -m pip install --no-index --find-links WHEELHOUSE \
  --require-hashes --only-binary=:all: -r HASHED_REQUIREMENTS
```

Do not substitute a wheelhouse from another cell. A missing file or hash is a
hard failure; source builds and network fallback are not supported.

The only installed command is `autopulse-debug`. For example:

```text
autopulse-debug validate-frame --powertrain ICE --file SANITIZED_FRAME_JSON
autopulse-debug replay-ice --jsonl SANITIZED_REPLAY_JSONL
```

Inputs and outputs remain on the operator-controlled filesystem. Debug output
is sanitized, but vehicle-derived identifiers and raw telemetry must not be
placed in shared support artifacts.

## Safety boundary

This package does not support live adapters, vehicle capture, VIN reads, road
testing, unattended monitoring, DTC clearing, actuator/control requests,
diagnostic session escalation, security access, or any write-capable OBD-II or
UDS service. `autopulse.live` is deliberately absent from both package
artifacts and has no console entry point. Existing repository-only stationary
smoke-harness material is outside the offline distribution.
