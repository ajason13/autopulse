# Pages validation and artifact provenance

Issue: [#134](https://github.com/ajason13/autopulse/issues/134).

CI and Pages use the same `npm run validate:docs` command after `npm ci` in
`grubby-galaxy`. Validation runs the production dependency audit, Chromium
installation, spec-publication and provenance tests, build and server-lifecycle
tests. Lifecycle probes may destroy `dist`, so validation then makes one final
production build. Smoke and regression suites inspect that build sequentially,
without rebuilding. Each suite owns its preview process and releases its port.

`dist/autopulse-build.json` records the checkout SHA, Actions run/attempt (or
`local`), production site/base, lockfile hash, source-input hash, and a sorted
file/hash manifest with its digest. Inputs are checked before and after the
final build. Each prebuilt preview checks the receipt against current inputs
and output, and validation checks again after each browser suite. Missing,
foreign, changed or stale output fails closed. Filesystem links and special
files are rejected because the Pages archive action dereferences links.
The manifest excludes itself from the file digest; this is an integrity check,
not a cryptographic attestation or a defense against malicious build code.

Normal `test:smoke` and `test:e2e` commands retain fresh-build behavior.
`AUTOPULSE_DOCS_PREBUILT=1` is reserved for validation of a recorded build;
setting it does not bypass provenance or stale-listener checks. Do not edit
inputs, run another build, or run browser suites concurrently in that checkout.

Pages accepts only main-ref push or manual events. Its build job has only
`contents: read`; dependency and repository code never receive Pages/OIDC write
permissions. On success, upload archives the validated directory including hidden
files, with no subsequent rebuild. The unique artifact name includes the SHA,
run ID and attempt; its upload ID is a required job output. The deployment job
requires successful validation and a nonempty artifact ID, uses that name from
the same run, and executes only the pinned deployment action. That action
resolves exactly one matching artifact in the current workflow run. Only this
job has `pages: write` and `id-token: write`, under the `github-pages`
environment. No PR or cross-workflow artifacts are accepted. Existing Pages
environment/branch protections still apply.

## Verification

From the docs directory with the pinned Node major and locked dependencies:

```text
npm ci
npm run validate:docs
```

Provenance tests use a temporary Git checkout whose path contains spaces. They
exercise missing output, wrong SHA/run/attempt/config/digest, changed sources or
lockfile, file addition/deletion/modification and changed build inputs. A
controlled runner fails each validation stage and asserts later stages never
run and the prebuilt receipt is removed. Lifecycle tests exercise the real
preview command's missing/stale provenance rejection and unchanged bytes/port
cleanup after successful and failing prebuilt browser probes.

`tests/packaging/test_ci_workflow_contract.py` checks the actual workflow
conditions over main/feature/tag refs, push/manual/PR events, successful,
failed, cancelled and skipped validation, and present/missing artifact IDs.
It also checks permissions, immutable pins, job dependency, upload ordering,
same-run artifact binding, and absence of repository execution in deployment.
These controlled negative scenarios can run in ordinary hosted PR CI without
publishing intentionally bad content or granting the test harness Pages tokens.
The read-only `Verify Pages gate without deployment` workflow also runs these
controlled scenarios on main pushes and manual dispatches, without any upload
or deployment action. Actual push/manual deployment run evidence belongs in the issue/PR; unit
scenarios alone do not claim those hosted paths executed.
