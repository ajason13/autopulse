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

Evidence will be recorded after both native cells complete.
