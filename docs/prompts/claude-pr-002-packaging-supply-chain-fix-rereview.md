# Claude — PR-002 implementation-audit fix re-review

Review scope: this is a focused re-review of the three merge-gate findings from
your PR-002 implementation audit. It is not a public-release approval and it
does not authorize CI changes, publication, live capture, VIN reads, or any
write-capable diagnostics.

## Access to the implementation

Claude Chat does not have this workspace. Use one of the following, in order:

1. Review the supplied GitHub PR/commit links, if the requester supplied them
   with this prompt.
2. Review the freshly attached repository tarball, if supplied.
3. If neither is available, request the requester paste the complete contents
   of the files named below. Do not approve from this prompt's summary alone.

Required current files:

- `scripts/verify_release_cell.py`
- `scripts/packaging_policy.py`
- `tests/packaging/test_release_cell_verifier.py`
- `tests/packaging/test_packaging_policy.py`
- `docs/qa/pr-002-cp313-macos-x86_64.md`
- `docs/qa/pr-002-cp314-macos-x86_64.md`
- `docs/specs/pr-002-packaging-supply-chain-decision-record.md`

The earlier full implementation packet is
`docs/prompts/claude-pr-002-packaging-supply-chain-implementation-audit.md`.
If you cannot access the GitHub/tarball version of that packet, ask the
requester to paste it too, since it contains the pre-fix implementation under
review. Do not assume a local path is readable.

For a no-filesystem re-review after the audit fixes, paste
`docs/prompts/claude-pr-002-packaging-supply-chain-current-source-packet.md`
immediately after this prompt. It contains the complete current files and the
captured full-suite output Claude requested; it is a pasteable packet, not a
claim that this path is accessible to Chat.

## Previously reported findings and claimed fixes

1. **MF-01 (merge gate):** the full suite had not been completely captured.
   A complete captured run now reports exit code `0` and `643 passed in
   57.54s`. Verify this is reflected in supplied evidence; do not treat a
   partial progress display as proof.
2. **MF-02:** `validate_archive()` had not been explicitly recorded against
   the actual built artifacts. `verify_release_cell.py` now requires both
   `--wheel` and `--sdist`, calls `validate_archive()` on each before install,
   and writes two explicit PASS lines to each sanitized QA summary.
3. **MF-03:** the offline pip command had no negative proof. The runner now
   creates fresh virtual environments and proves both a tampered AutoPulse
   wheel hash and an incomplete wheelhouse fail under `--no-index`,
   `PIP_NO_INDEX=1`, `--require-hashes`, and `--only-binary=:all:`. The new
   test module invokes the real helper against minimal wheel fixtures.
4. **MF-04 (advisory):** the decision record now explicitly selects an
   intentional suppression-free raw-identifier scan. New sanctioned examples
   must avoid raw identifiers or stay out of release artifacts.

## Required adversarial checks

- Trace whether archive validation is actually run on the real wheel *and*
  sdist, and whether a failure prevents a PASS summary.
- Trace both negative pip probes. Confirm they use newly created environments,
  cannot use an index, and cannot pass merely because the package is already
  installed or cached.
- Confirm the tests exercise those real helpers rather than a separate
  look-alike implementation.
- Confirm the two QA files evidence CPython 3.13 and 3.14 on macOS x86_64
  only; do not infer support evidence for Linux, Windows, or macOS arm64.
- Confirm no new change weakens the prior exclusion of `autopulse.live`, the
  installed schema-resource test, privacy/content scanning, hash checking, or
  the exact-root-sdist-only `.gitignore` exception.

## Verdict format

Return exactly one verdict: **NO BLOCKERS**, **MINOR FIXES**, or **BLOCKER**.
For every finding, give severity, exact file/symbol, exploit or failure mode,
and a concrete correction. State separately whether the full-suite merge gate
is now satisfied, whether MF-02 and MF-03 are closed, and which native support
cells remain evidence gaps. Do not claim release approval.
