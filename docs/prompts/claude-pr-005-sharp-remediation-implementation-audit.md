# Claude Chat prompt — PR-005 docs supply-chain remediation implementation audit

You are AutoPulse's independent Lead Auditor (Claude Sonnet 4.6). Perform a
source-grounded **implementation audit** of the actual remediation described
below. Return exactly one: **APPROVED FOR COMMIT**, **APPROVED WITH MINOR
FIXES**, or **NOT APPROVED**. This audit authorizes no tag, RC identifier,
release, publication, deployment, runtime change, or reuse of retired
`v0.1.0-rc.1`.

Audit the pushed branch `pr-005-release-candidate-exercise` at immutable
commit `c648031ff3fba5f5a310a212f76526692f6515cc`, whose implementation parent
is `3b95c1623b6d526d76f76ef00028a91efa595f1f` and whose merge base is
`81a157927fcacf4ae47716326885d12477e0002d`. Read actual remote source,
including the full files and `git diff 81a1579..c648031`; do not rely only on
the excerpts below. A later new candidate still requires a fresh full hosted
run and final exact-SHA audit. Do not treat this as release readiness.

## Complete diff manifest

The complete `81a1579..c648031` diff contains exactly these 16 files. Review
this list before relying on the focused excerpts that follow:

- `.github/workflows/ci.yml`
- `CONTEXT.md`
- `docs/prompts/claude-pr-005-release-candidate-final-audit.md`
- `docs/prompts/claude-pr-005-release-candidate-pre-audit.md`
- `docs/prompts/claude-pr-005-release-candidate-pre-audit-rereview.md`
- `docs/prompts/claude-pr-005-release-candidate-pre-audit-rereview-2.md`
- `docs/prompts/claude-pr-005-sharp-remediation-pre-audit.md`
- `docs/prompts/claude-pr-005-sharp-remediation-pre-audit-rereview.md`
- `docs/prompts/claude-pr-005-sharp-remediation-pre-audit-rereview-2.md`
- `docs/prompts/claude-pr-005-sharp-remediation-pre-audit-rereview-3.md`
- `docs/release-notes/release-candidate-template.md`
- `docs/release-notes/v0.1.0-rc.1-draft.md` (retired historical draft; do not
  publish or reuse its label)
- `docs/specs/pr-005-release-candidate-exercise-decision-record.md`
- `grubby-galaxy/package.json`
- `grubby-galaxy/package-lock.json`
- `tests/packaging/test_ci_workflow_contract.py`

The prompt archives and `CONTEXT.md` are durable, sanitized audit history;
they do not alter runtime behavior. The retired draft documents the prior
failure and is not a new RC note. No other source file changed.

## Focused remediation source

### `grubby-galaxy/package.json`

```diff
-    "sharp": "^0.34.5"
+    "sharp": "^0.35.3"
```

`grubby-galaxy/package-lock.json` was regenerated with Node 24/npm 11, not
hand-edited. Its top-level dependency now says `"sharp": "^0.35.3"`; the
`node_modules/sharp` record resolves exact `0.35.3` from the npm registry with
an npm-generated integrity value. This is outside GHSA-f88m-g3jw-g9cj's
affected `<0.35.0` range. The regeneration updates sharp's native optional
packages/libvips records and transitive `semver` according to npm resolution.

### `.github/workflows/ci.yml` — docs job excerpt

```yaml
      - run: npm ci
      - run: npm audit --omit=dev --audit-level=high
      - run: npx playwright install --with-deps chromium
      - run: npm run build
      - run: npm run test:smoke
      - run: npm run test:e2e
```

The job retains its job-level Bash working directory `grubby-galaxy`, immutable
Actions v7 pins, `contents: read`, standard `pull_request`/`push` triggers,
and no job-level `continue-on-error`. The audit step has no `if:`, `shell:`, or
`continue-on-error`; it is exactly the one-line command above.

### `tests/packaging/test_ci_workflow_contract.py`

The new test extracts the `docs` job and its individual step blocks. It
requires exactly one audit step whose stripped content is exactly:

```text
- run: npm audit --omit=dev --audit-level=high
```

It requires the step immediately after `npm ci` and before Playwright install,
build, smoke, and e2e. It rejects an audit-step `if:`, `shell:`,
`continue-on-error` other than explicit `false`, trailing `||`/`;`/`&&`, and
Bash error suppression (`set +e`, `set +o errexit`). It also rejects docs-job
`continue-on-error` other than explicit
`false`, while asserting the job's Bash default. Existing pin/base-path/
read-only-permission assertions remain.

### Durable PR-005 artifacts

- `docs/specs/pr-005-release-candidate-exercise-decision-record.md` records
  the permanently retired old label, source advice for sharp 0.35.3, the
  fail-closed gate, deliberate high-only/production-only scope, and the
  requirement for committed artifacts in a later candidate.
- `docs/release-notes/release-candidate-template.md` is version-agnostic. It
  assigns no new RC label and says local/untracked notes are not audit inputs.
  It includes offline/replay-only prohibited-use, Windows evidence boundary,
  security, and source-grounded final-audit placeholders.

## Local verification (Node 24.15.0 / npm 11.17.0)

- `PYTHONPATH=src python3 -m pytest tests/packaging/test_ci_workflow_contract.py -q` → `3 passed`.
- `npm ci` → passed.
- `npm audit --omit=dev --audit-level=high` → `found 0 vulnerabilities`.
- `npm run build` → passed (13 static pages); only existing bundle-size warning.
- `npm run test:smoke` → `6 passed, 2 skipped`.
- `npm run test:e2e` → `48 passed, 2 skipped`.
- `git diff --check` → passed.

Local evidence does not replace later hosted docs CI or any full release
matrix. No Python package, live adapter, OBD-II/UDS/replay, telemetry/VIN,
logging/observability, deployment, tag, release, or publication change exists.
No raw logs, wheelhouses, artifacts, private paths/URLs, payloads, VIN-like
values, or secrets are retained.

## Required audit questions

1. Does the actual lockfile remediation close the advisory without an
   accidental dependency, licensing, Node-version, or platform regression?
2. Is the actual workflow step unconditional and fail-closed in the docs job?
3. Does the actual contract test reject the agreed realistic bypasses rather
   than merely matching a global substring?
4. Do the committed-source decision/template artifacts correctly avoid
   asserting a new RC or release readiness?
5. Identify any source-specific blocker before the implementation is committed.
