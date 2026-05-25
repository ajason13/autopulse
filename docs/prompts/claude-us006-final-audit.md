# Claude Final Audit Prompt: US-006 EV Telemetry Implementation

You are Claude Sonnet 4.6 acting as AutoPulse Lead Auditor.

Codex has implemented US-006 within the approved scope. Please perform final audit against the resolved US-006 specification and adversarial QA plan.

## Implemented Scope

Codex implemented:

- `schemas/ev_obd_frame.schema.json`
- EV finite-number schema validation and envelope routing in `src/autopulse/data/validator.py`
- UDS read-only command guardrails in `src/autopulse/data/validator.py`
- EV replay packet/adapter support, dirty-data helpers, test-scoped burst replay, sign-convention enforcement, DTC speculative-probe blocking, and protocol-transition blocking in `tests/simulation/virtual_replay.py`
- compatibility exports through `src/autopulse/adapters.py`, `src/autopulse/replayer.py`, and `src/autopulse/noise.py`
- EV JSON-LD event serialization via `EVTelemetryAlert` and `serialize_ev_alert()` in `src/autopulse/alert_exporter.py`
- US-001 protocol enum correction to canonical `SAE_J1979-2`, while preserving old underscore replay aliases as normalization inputs
- Starlight US-006 docs page

Codex did not implement:

- EV-HDF
- EV-OSF
- EV anomaly scoring under `src/autopulse/analysis/`
- time-of-use
- V2X discharge tracking
- certified energy consumption
- automatic DoCAN-to-DoIP discovery

## Required Audit Checks

Please verify:

1. EV schema uses the final field bounds and semantic descriptions.
2. ICE and EV schemas remain isolated and protocol enums are disjoint.
3. `SAE_J1979_2` is only a replay/input alias and normalizes to canonical `SAE_J1979-2` before schema validation.
4. `route_and_validate()` rejects unknown `powertrain_type`, protocol/powertrain mismatches, and EV/ICE cross-contamination.
5. UDS policy blocks `0x14`, `0x27`, `0x2E`, `0x2F`, `0x31`, non-default `0x10`, unrestricted `0x19`, `0x3E` abuse, speculative `0x19/0x06`, undocumented negative motor speed, and protocol transitions.
6. EV JSON-LD events reject raw VINs and non-finite numbers and do not leak raw payload bytes.
7. Replay burst mode is test-scoped and does not silently exceed passive monitoring safety in production mode.
8. No EV analysis logic slipped into US-006.

## Verification Evidence

Targeted US-006 handoff suite:

```bash
python3 -m pytest tests/test_engine_data_contract.py tests/test_us006_ev_data_contract.py tests/test_us006_schema_routing.py tests/test_us006_ev_adapter_security.py tests/test_us006_ev_replay_harness.py tests/test_us006_ev_alert_exporter.py -q
```

Result:

```text
212 passed in 0.39s
```

Full test suite:

```bash
python3 -m pytest -q
```

Result:

```text
531 passed in 45.66s
```

Starlight docs build:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npm run build
```

Result:

```text
passed, 12 pages built
```

## Requested Output

Return:

1. Pass/fail final audit verdict.
2. Any blocker findings with file/test references.
3. Any non-blocking recommendations.
4. Explicit sign-off or required remediation before merge.
