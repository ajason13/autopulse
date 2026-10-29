# Python source-development onboarding verification

This record accompanies [issue #129](https://github.com/ajason13/autopulse/issues/129)
and the [Getting Started guide](../../grubby-galaxy/src/content/docs/guides/getting-started.md).
It concerns online source development, not disconnected release qualification.

## Environment and provenance

- Date: 2026-10-29.
- Host: macOS 15.4.1, build 24E263, Intel x86_64.
- Source baseline: `b1861bec19437f1598263e198024cc847ab7b28a`.
- Documentation branch: `docs/129-python-onboarding`; the accompanying PR identifies
  the documentation commit. Python source, dependency declarations, and lockfile
  are unchanged from the baseline.
- Each interpreter used a fresh local clone and `.venv` under a temporary
  `AutoPulse Development` checkout path containing spaces. The synthetic JSON
  was extracted from the revised guide. `PYTHONPATH` was unset; `uv` used a fresh
  temporary cache. No existing repository virtual environment supplied packages.
- The local clone substituted a local Git transport for the guide's GitHub clone;
  package installation used the network. This is not offline installation evidence.

## Executed procedure

From each clean checkout, create `.venv` with the selected CPython interpreter,
then run the guide's commands:

```sh
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev]" -r requirements-release.txt
./.venv/bin/python -m pip check
./.venv/bin/autopulse-debug --help
./.venv/bin/autopulse-debug validate-frame --powertrain ICE --file "synthetic frame.jsonl"
./.venv/bin/autopulse-debug replay-ice --jsonl "synthetic frame.jsonl"
./.venv/bin/python -m pytest tests/test_engine_data_contract.py -q
./.venv/bin/python -m pytest tests/test_us002_virtual_replay_harness.py -q
./.venv/bin/python -m pytest -q
```

Also run the README's focused debug/security logging checks with this same Python:

```sh
./.venv/bin/python -m pytest tests/test_us006_ev_adapter_security.py -q -vv --tb=short --log-cli-level=DEBUG
./.venv/bin/python -m pytest tests/test_debugging.py -q -vv --tb=short
```

The requirements-file install supplies `uv==0.13.5` for the full suite's
`tests/packaging/test_package_contract.py` locked-export check. Installing runtime
requirements alone would omit both pytest and `uv`, as well as the local package.
The editable install resolves dependencies within declared ranges; it does not
replace CI's locked, hashed release gates.

## Python results

All commands above exited 0 on both interpreters. Both used pip 26.2.2,
pytest 9.2.0, and uv 0.13.5. `pip check` found no broken requirements.

| Interpreter | Contract tests | Replay tests | Security logging tests | Debug tests | Full suite |
| --- | --- | --- | --- | --- | --- |
| CPython 3.13.14 | 78 passed | 160 passed | 20 passed | 17 passed | 875 passed, 1 skipped |
| CPython 3.14.6 | 78 passed | 160 passed | 20 passed | 17 passed | 875 passed, 1 skipped |

The existing timezone-switch test is skipped because these interpreters lack
`time.tzset`; other timestamp/offset checks passed. CLI help succeeded;
validation returned `ok: true`; replay reported one accepted frame and zero
rejections/security violations. CPython 3.13's installed CLI also passed help,
validation, and replay from outside the checkout with `PYTHONPATH` unset.

## Windows evidence boundary

Native Windows 10/11 desktops and PowerShell were unavailable on this host, so
neither desktop onboarding path was executed here. Do not label this macOS result
or hosted Windows Server results as native Windows desktop validation.
The guide provides explicit `.venv\Scripts` executable paths, quoted arguments,
and a UTF-8-without-BOM input requirement; no activation or execution-policy
change is needed. PowerShell commands were inspected against the existing CLI
arguments, package metadata, and Windows CI invocation conventions.

[#154](https://github.com/ajason13/autopulse/issues/154) retains the native Windows
10/11 x64 CPython 3.13/3.14 evidence matrix, including OS/build, interpreter,
commit, commands, exit codes, and checkout paths containing spaces. Desktop
release-support decisions remain in [#141](https://github.com/ajason13/autopulse/issues/141).
Node/docs onboarding is separately scoped to
[#155](https://github.com/ajason13/autopulse/issues/155).

## Documentation checks

Using Node 24.15.0 / npm 12.2.1 from `grubby-galaxy/`:

- `npm run build`: passed, 13 pages.
- `AUTOPULSE_DOCS_PORT=4339 npm run test:smoke`: 6 passed, 2 expected
  device-specific skips.
- `AUTOPULSE_DOCS_PORT=4339 npm run test:e2e -- --grep 'getting-started|sidebar'`:
  6 passed, 2 expected device-specific skips. Covers the guide's desktop/mobile
  route and internal links, plus desktop/mobile sidebar navigation.
- The first smoke attempt on default port 4321 failed because an existing
  listener owned it. Verification used the documented port override; the existing
  server was preserved. Port 4339 was released after the passing suites.
- Existing bundle-size, empty i18n/404-content, and color-environment warnings
  did not prevent the build or browser checks.
- All 12 repository-file/route links in the changed documents resolve locally;
  `git diff --check` passed.

Focused documentation review checked commands against package metadata,
requirements files, the lockfile contract test, CLI arguments, and the existing
Windows CI conventions. No runtime, dependency, schema, deployment, or release
profile changes are included. Broader product-claim corrections remain #130.
