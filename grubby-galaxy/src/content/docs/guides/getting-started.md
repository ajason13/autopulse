---
title: Getting Started
description: Install AutoPulse for source development and verify a synthetic offline replay.
---

This guide sets up the local Python package and runs synthetic validation and
replay without a vehicle connection. Dependency installation requires internet
access. For disconnected wheelhouse installation, use the separate
[offline package guide](https://github.com/ajason13/autopulse/blob/main/docs/offline-package.md).

## Prerequisites

- Git and **CPython 3.13 or 3.14** (`>=3.13,<3.15` in `pyproject.toml`).
- On Windows, use native PowerShell and an x64 CPython installation with the
  `py` launcher. If the launcher is unavailable, invoke the installed interpreter
  by its quoted full path with PowerShell's `&` operator.
- Node is needed only for the documentation site; see the optional docs section.

## 1. Install the source-development environment

Run one of the following blocks. Both create a virtual environment and install
the local package, pytest, and tools used by the full Python suite.
The quoted checkout name deliberately includes a space; another writable checkout
path is fine. Stay in the repository root for subsequent Python commands.

### macOS / Linux

Use `python3.14` instead of `python3.13` to select CPython 3.14.

```sh
git clone https://github.com/ajason13/autopulse.git "AutoPulse Development"
cd "AutoPulse Development"
python3.13 --version
python3.13 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev]" -r requirements-release.txt
./.venv/bin/python -m pip check
./.venv/bin/autopulse-debug --help
```

### Windows PowerShell

Use `py -3.14` instead of `py -3.13` to select CPython 3.14. Run each command
only after the preceding command succeeds; `$LASTEXITCODE` should be `0` after
native executable commands. Activation, administrator privileges, and changes
to PowerShell's execution policy are unnecessary.

```powershell
git clone https://github.com/ajason13/autopulse.git "AutoPulse Development"
Set-Location "AutoPulse Development"
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -r requirements-release.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\autopulse-debug.exe --help
```

To invoke an interpreter path containing spaces, use, for example,
`& "C:\Path With Spaces\python.exe" -m venv .venv`. After creating `.venv`,
use its executables as shown above so pip and pytest target the same interpreter.

These are proposed Windows 10/11 x64 development instructions. Native desktop
verification remains unrecorded; hosted Windows Server checks do not substitute
for it. Windows 10 is outside the current offline release profile. Track native
evidence in [#154](https://github.com/ajason13/autopulse/issues/154) and support
decisions in [#141](https://github.com/ajason13/autopulse/issues/141).

### Which dependencies are installed?

| Purpose | Existing dependency source | What it provides |
| --- | --- | --- |
| Runtime | `pip install .` / `pyproject.toml` | Local AutoPulse package, `autopulse-debug`, and `jsonschema` |
| Focused Python tests | `pip install -e ".[dev]"` | Editable package plus pytest |
| Requirements-file alternative | `requirements-dev.txt` | Runtime dependencies plus pytest; install the local package separately |
| Full-suite and release tooling | `requirements-release.txt` | Exact-pinned build, audit, metadata, and `uv` tools; used with the dev install above |

The table names pip's install arguments; invoke pip through the virtual
environment's Python as in the setup blocks. `requirements.txt` installs runtime
dependencies only. Installing it alone does not install AutoPulse, pytest, or
`uv`. The full suite invokes `python -m uv` in its lockfile contract test.
The `release` extra also declares release tools; the requirements file
additionally pins the build backend used by CI.

AutoPulse uses a `src/` layout. Editable installation makes the package and CLI
available in this environment without setting `PYTHONPATH`; changes to Python
source are available without reinstalling. This online development install is
not a hashed, locked release installation. Release verification uses `uv.lock`
and per-platform hashed exports through the existing CI workflow.

## 2. Validate and replay a synthetic frame

Save the following **single line** as UTF-8 **without a byte-order mark** in
`synthetic frame.jsonl` in the repository root. It is one JSON object, suitable
for both single-frame validation and JSONL replay. The repeated `c` identifier
is synthetic; no vehicle data is needed.

```json
{"timestamp":"2026-05-26T10:00:00Z","vin_hashed":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","protocol":"SAE_J1979","engine_rpm":1200.0,"vehicle_speed":30,"coolant_temp":88.0,"engine_load":22.0,"stft_bank1":0.5,"ltft_bank1":-0.5}
```

macOS / Linux:

```sh
./.venv/bin/autopulse-debug validate-frame --powertrain ICE --file "synthetic frame.jsonl"
./.venv/bin/autopulse-debug replay-ice --jsonl "synthetic frame.jsonl"
```

Windows PowerShell:

```powershell
.\.venv\Scripts\autopulse-debug.exe validate-frame --powertrain ICE --file "synthetic frame.jsonl"
.\.venv\Scripts\autopulse-debug.exe replay-ice --jsonl "synthetic frame.jsonl"
```

Validation should return `ok: true`; replay should report `accepted_frames: 1`,
`rejected_frames: 0`, and `security_violations: 0`. Both should exit with status 0.
This verifies local data flow, not anomaly accuracy or vehicle compatibility.
Remove the synthetic file when finished; do not commit local input files.

## 3. Run the Python checks

Run these commands from the repository root. The first two are focused contract
and replay checks; the final command runs the full suite, including the lockfile
contract requiring `uv`.

macOS / Linux:

```sh
./.venv/bin/python -m pytest tests/test_engine_data_contract.py -q
./.venv/bin/python -m pytest tests/test_us002_virtual_replay_harness.py -q
./.venv/bin/python -m pytest -q
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_engine_data_contract.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_us002_virtual_replay_harness.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

## Optional: run the documentation site

Node.js 22.12+ is required by the docs toolchain; AutoPulse pins Node 24 in
`grubby-galaxy/.nvmrc` for local builds and deployment. With Unix `nvm` installed:

```sh
cd grubby-galaxy
nvm install
nvm use
npm install
npm run dev
```

The docs will be available at `http://localhost:4321/autopulse/`. Stop the server
with Ctrl+C and return to the repository root before running Python checks.
See the [docs README](https://github.com/ajason13/autopulse/blob/main/grubby-galaxy/README.md)
for build and browser checks. Native Windows Node/docs onboarding is tracked
separately in [#155](https://github.com/ajason13/autopulse/issues/155).

Next, explore the [Engine Data Contract](../../specs/us-001-engine-data-contract/)
for the sensor data contract. See the
[onboarding verification record](https://github.com/ajason13/autopulse/blob/main/docs/qa/python-onboarding.md)
for executed environments and remaining Windows evidence.
