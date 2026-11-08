# Native Windows Python verification

Issue [#154](https://github.com/ajason13/autopulse/issues/154) owns Windows 11
x64 CPython 3.13/3.14 compatibility evidence. Windows 10 execution remains
[#182](https://github.com/ajason13/autopulse/issues/182); official release-support
wording remains a decision in [#141](https://github.com/ajason13/autopulse/issues/141).
These checks use synthetic data only and do not establish vehicle compatibility
or authorize a release.

## Repeatable native procedure

Use native Windows x64, PowerShell 7+, Git, and a supported x64 CPython 3.13 or
3.14 interpreter. Use a normal user account; no activation, Bash, administrator
privileges, or persistent execution-policy change is needed. Online runtime
provisioning and development/dependency downloads precede the disconnected
installation phase. Follow [Getting Started](../../grubby-galaxy/src/content/docs/guides/getting-started.md)
for interpreter installation; pass its full executable path if `py` is absent.
For uv-managed Python, the pinned release tool supports, for example,
`python -m uv python install 3.13 --install-dir LOCAL_DIRECTORY --no-bin --no-registry`.
Record the actual resulting patch version and distribution provenance.

From the repository root, resolve the exact committed revision to test and run
one cell at a time. Replace the two interpreter paths with real installations.
The work directories must be new, writable paths containing a space.

```powershell
$ErrorActionPreference = 'Stop'
$commit = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve tested commit' }
& pwsh -NoProfile -File .\scripts\verify_windows_python.ps1 `
    -Python 'C:\Python313\python.exe' -Commit $commit `
    -WorkRoot "$env:TEMP\AutoPulse Python 313"
if ($LASTEXITCODE -ne 0) { throw 'CPython 3.13 cell failed' }
& pwsh -NoProfile -File .\scripts\verify_windows_python.ps1 `
    -Python 'C:\Python314\python.exe' -Commit $commit `
    -WorkRoot "$env:TEMP\AutoPulse Python 314"
if ($LASTEXITCODE -ne 0) { throw 'CPython 3.14 cell failed' }
```

The script clones the local repository into a clean detached checkout at that
immutable commit, ignoring uncommitted files. It uses direct venv executables,
installs `.[dev]` and `requirements-release.txt`, checks dependencies, exports
`uv.lock` with hashes, downloads wheels only, builds a wheel from the sdist,
and checks distribution metadata/contents. The existing release-cell verifier
validates both archive policies, installs with `--no-index --require-hashes
--only-binary=:all:`, rejects tampered hashes and missing wheels, excludes
`autopulse.live`, and verifies installed synthetic ICE analysis/export.
Registry access is disabled for install probes; the whole machine is not
physically disconnected.

With `PYTHONPATH`/`PYTHONHOME` unset and the temporary work path outside the
checkout, the procedure checks both packaged schema resources, CLI help,
synthetic ICE/EV `validate-frame`, and JSONL replay (one accepted frame, zero
rejections/security violations). It then runs the full Python suite from the
clean source checkout. All native failures stop the procedure with nonzero
status; semantic smoke assertions also fail the cell. Each invocation leaves
its `commands.log`, `cell-summary.md`, `wheelhouse.json`, `pytest.xml`, artifacts,
and environments locally for inspection. Use a fresh work path after failure;
the script never deletes existing work. Environment variables and the caller's
working directory are restored on exit.

Keep raw transcripts local: they contain machine paths and package-index
details. Publish only reviewed, sanitized results, exact OS/interpreter/tool
versions, tested commit, exit codes and limitations. Do not upload environments,
wheelhouses or raw logs as evidence. No live adapter or vehicle input is needed.

## Executed Windows 11 cells

Run date: **2026-11-07 (America/Los_Angeles)**. Native host:
**Microsoft Windows 11 Pro, 25H2, x64, 10.0.26200.9711**. Caption/architecture
were read from `Win32_OperatingSystem`; display version and revision from
`HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`. The registry's legacy
`ProductName` says Windows 10 Pro; CIM identifies this build as Windows 11 Pro.
PowerShell **7.6.9**; Git **2.56.0.windows.4**.

Both cells target immutable commit
`388a920e30d6a935fe59d3603715e9c0ffc43f3b`, which includes the procedure and its
regression test, based on main `85b13091998e38e8b25d79117c88e63776760809`.
Subsequent changes in this PR add evidence/documentation only. Each source
checkout was verified clean before environment setup. Sanitized work paths
below are relative to the invoking repository root; source, development,
installed and temporary directories all contain spaces.

Interpreters are **uv-managed CPython, x86_64, MSC v.1944 64 bit (AMD64)**,
python-build-standalone build **20261026**, not Python.org installer runs.
CPython 3.13.18 was provisioned with the existing pinned uv 0.13.6:

```powershell
.\.venv\testenv\Scripts\python.exe -m uv python install 3.13 --install-dir .venv\pythons --no-bin
```

Provisioning returned 0. CPython 3.14.10 was already present in the same local
interpreter directory. Both report `main, Oct 26 2026` in `sys.version`.
Interpreter executable SHA-256:

| Interpreter | SHA-256 of `python.exe` |
| --- | --- |
| 3.13.18 | `d0a3fdb2f523217cc05cbfa015a249f53f670fe38c72522fa893377c5d2f17d5` |
| 3.14.10 | `bcd8e6a0d88b5e9681e94bb4ce569ca1f76039e8ed9944ac7fcd13528d363cae` |

The actual cell invocations used the following argument values with the
`pwsh -NoProfile -File .\scripts\verify_windows_python.ps1` command above:

| Argument | CPython 3.13 | CPython 3.14 |
| --- | --- | --- |
| `-Python` (resolved absolute path) | `.venv\pythons\cpython-3.13.18-windows-x86_64-none\python.exe` | `.venv\pythons\cpython-3.14.10-windows-x86_64-none\python.exe` |
| `-Commit` | `388a920e30d6a935fe59d3603715e9c0ffc43f3b` | same |
| `-WorkRoot` (resolved absolute path) | `.cache\Windows Python 313 run2` | `.cache\Windows Python 314` |

Each script command and native exit check is preserved in the tested procedure;
local transcripts record expanded paths. Development environments used pip
26.3, pytest 9.2.0, jsonschema 4.26.0, uv 0.13.6, build 1.6.1, hatchling 1.32.4,
twine 7.0.0 and check-wheel-contents 0.6.3. All release tools come from the
unchanged exact pins in `requirements-release.txt`. Development pytest uses
the declared range; disconnected installation instead consumes the locked
hashed export (including its locked development/release dependencies).

| Check (each native command exited 0) | CPython 3.13.18 | CPython 3.14.10 |
| --- | --- | --- |
| Clean checkout, venv setup, development install, `pip check` | PASS | PASS |
| Locked hashed export and wheel-only dependency download | PASS | PASS |
| Build wheel from sdist, `twine check`, `check_wheel_contents` | PASS | PASS |
| Wheel/sdist archive policy, existing installed analysis gate | PASS | PASS |
| Hashed wheel-only no-index install | PASS | PASS |
| Tampered-hash and missing-wheel rejection probes | PASS | PASS |
| `autopulse.live` absent in metadata and imports | PASS | PASS |
| Both installed schema resources; installed CLI help | PASS | PASS |
| ICE and EV validation; each replay accepted 1/rejected 0/security violations 0 | PASS | PASS |
| Full `pytest -q -ra` | 1,040 passed, 1 skipped (26.47 s) | 1,040 passed, 1 skipped (20.37 s) |
| Wrapper process exit code | 0 | 0 |

Negative probes intentionally receive nonzero pip status and are accepted only
when the verifier also matches the expected failure reason. Full-suite JUnit
comparison found identical **1,041 test IDs and outcomes** in both cells,
including **61 passed / 1 skipped** in `test_pdm_temporal_contract.py`.
The sole skip is `test_naive_iso_is_utc_independent_of_host_timezone`:
Windows lacks `time.tzset`. UTC/offset/naive timestamp representation checks,
time rejection atomicity and temporal state regressions still run. No tests
were weakened or dependencies downgraded. The 145 packaging test cases,
including the new native-command failure regression and existing verifier
regressions, ran in both full suites.

| Artifact SHA-256 | CPython 3.13.18 | CPython 3.14.10 |
| --- | --- | --- |
| `autopulse-0.1.0-py3-none-any.whl` | `05bdcdbfcbc714fc6d072bc17808266445eb58181150cafb48eeb6087bc010f1` | `cdac3693d054d18424c656e6f3a829c76553a6da191b6605ed4fac98fe4cc925` |
| `autopulse-0.1.0.tar.gz` | `baca65331cce138884a23a476443cc1bccd7d6bad250c2d4d85529e733dbce4d` | `a1ccba73eb06050af0388e3914bc83ddba95adb997c949ef7f402207d66a6e52` |
| Wheelhouse manifest | `dcfa92021438389cfdcf3d7c0db47761975ba3294f6b7770de7e66fd50c9780d` | `cca43968ade49a549714499771a1651d353930f2238077946c0f5f53194b5e3e` |

These are separate builds and native dependency selections; cross-interpreter
archive byte equality is not claimed. Existing CI separately checks canonical
payload reproducibility for two builds per hosted cell.

## Failure classification and limits

An initial manual invocation mistyped the commit SHA. `git checkout` returned
128 and the wrapper returned 1 before any dependency setup. The successful
3.13 run resolved the full SHA directly from Git and used a new `run2` work
directory. A focused local regression also passed before the matrix: a stub
interpreter returning 23 caused wrapper failure before creating work or
installing dependencies. An earlier sandboxed pytest attempt could not create
its default temporary directory; using a writable repository-local basetemp
passed. This was execution-environment setup, not a product portability defect.

No product portability defect was observed in these two cells. No physical
network disconnect, Python.org installer, Windows 10, ARM64, 32-bit, live
adapter, real telemetry, or vehicle execution is claimed. Online preparation
and offline install/runtime verification are distinct phases. This evidence
feeds #141; it does not adopt support policy or close Windows 10's #182.
Fresh-context review and protected hosted checks are recorded in the linked PR.
