# AutoPulse Repository Guidance

## Scope and safety

AutoPulse is an offline-first OBD-II diagnostics project. Preserve the
read-only diagnostic boundary: do not add write, coding, actuation, or ECU
configuration behavior. Treat schemas as the data-contract source of truth and
keep validation, replay, adapters, alerts, and tests consistent with them.

For a task touching diagnostics, telemetry, exports, or schemas, inspect the
relevant source, schema, and tests before editing. Record any standards or
protocol assumption in a focused document when it affects behavior. Do not make
unsupported safety, vehicle, or compliance claims.

## Working loop

1. Check `git status --short --branch` and identify the affected paths.
2. Make the smallest complete change using existing conventions.
3. Run targeted tests; run the relevant full suite or packaging checks for a
   cross-cutting change.
4. Inspect the final diff and report verification, assumptions, and residual
   risk.

Use a fresh-context Codex review after implementation for security, public
schema, export, release, or safety-sensitive changes. Do not require Notion,
Claude, Gemini, or another external-model handoff for ordinary work.

## Repository map

- `src/autopulse/data/`: ingestion, normalization, validation.
- `src/autopulse/analysis/`: anomaly and drift analysis.
- `schemas/`: JSON Schema contracts.
- `tests/` and `tests/simulation/`: regression and replay coverage.
- `docs/`: focused technical, standards, and operational records.

Keep task-specific handoffs with the relevant feature documentation. Do not
create or read a repository-wide active-context file by default.
