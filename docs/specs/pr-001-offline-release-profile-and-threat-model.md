# PR-001: Supported Offline Release Profile and Threat Model

**Status:** Codex-owned specification accepted by Claude's 2026-08-12 pre-implementation re-review; PR-002 is authorized to begin.  
**Scope:** Production-quality educational distribution for offline/replay workflows only.  
**Checked:** 2026-08-11.

## Purpose and scope

This specification is the release-policy baseline for AutoPulse. It permits a reproducible Python package that validates and replays previously supplied, sanitized telemetry fixtures on a user-controlled machine. “Production-quality” here means defined interfaces, repeatable installation, secure dependency maintenance, privacy-safe support, and evidence-based release gates. It does not mean a fleet, medical, safety-critical, or vehicle-operational product.

This is a policy/specification task. It does **not** authorize implementation, dependency changes, CI changes, release publication, schema changes, or a runtime feature.

### Supported workflows

- Local validation, analysis, debugging, and deterministic replay of user-supplied JSONL/CSV fixtures through existing offline interfaces.
- Local generation of sanitized analysis/alert output and documentation-led educational exploration.
- Clean installation and test execution in the environments in this document.

The package may need a networked, authenticated package index only during its documented installation/update step. Once installed with all required artifacts, replay and analysis must not require network connectivity, cloud accounts, telemetry upload, or a vehicle connection.

### Explicit non-goals and prohibited uses

This profile does not authorize fleet deployment, road testing, unattended or continuous live monitoring, a hosted service, VIN reads or storage, vehicle-adapter auto-discovery, CAN/UDS/OBD capture, or any write-capable diagnostic behavior. It also excludes DTC clearing, actuator tests, coding, routine control, security access, session control/escalation, seed-key material, and proprietary diagnostic payload capture. Existing conditional stationary-harness material is outside this release profile; it is neither enabled nor supported by an offline release.

## Supported environment and compatibility contract

### Release profile (AutoPulse policy decision)

| Area | Supported baseline | Explicitly unsupported in this profile |
| --- | --- | --- |
| Python | CPython 3.13 and 3.14, latest patch release available at release cut | CPython 3.12 and older; prereleases; PyPy; free-threaded builds; untested future CPython minors |
| Linux | 64-bit Ubuntu 24.04 LTS, x86_64 | containers, ARM, other distributions, and EOL images until independently evidenced |
| macOS | macOS 15+ on Apple Silicon or Intel | older macOS releases and nonstandard Python builds |
| Windows | Windows 11 x86_64 with the official CPython installer | Windows Server, 32-bit Python, and MSYS/Cygwin environments |
| Network | no network after a documented successful install | online services, upload, remote control, or telemetry collection |

PR-002/PR-003 must turn each supported cell into clean-install and replay evidence before it can be described as supported in release documentation. That evidence must show that every direct and transitive locked dependency is installed from a prebuilt wheel for the exact Python/OS/architecture cell; source-distribution fallback and an undocumented compiler toolchain are not permitted in a supported-user installation. This deliberately narrow matrix is a support promise, not a claim that the software cannot run elsewhere.

### Package and API compatibility

PR-002 must introduce standards-based project metadata in `pyproject.toml` and name the supported install and command interfaces. Until then, the source tree plus `requirements.txt` is a development convenience, not a distributable public-package contract.

- The public API comprises only symbols and command entry points explicitly documented as public in the release notes/API reference. Internal modules, test helpers, undocumented imports, fixture layouts, log keys, and CLI formatting are not stable interfaces.
- Release versions use Semantic Versioning (`MAJOR.MINOR.PATCH`) in a PEP 440-compatible public version. PATCH fixes defects without breaking a documented public interface; MINOR adds backward-compatible functionality; MAJOR may remove or alter it.
- An incompatible change requires a major release except for a security or privacy emergency, which may be shipped in the lowest safe release line with a clear advisory and migration note.
- A normal deprecation must be documented at least one MINOR release before removal, with a replacement and a testable migration path. Security red-line removals may be immediate.
- Each release notes exact supported Python/OS matrix, known limits, offline boundary, public API/CLI changes, security fixes, and upgrade/downgrade implications.

## Dependency, license, vulnerability, and SBOM policy

### Findings from primary sources

PyPA defines `pyproject.toml` project metadata and PEP 508 dependency strings; PEP 440-compatible versions can express the SemVer release segments used by this policy. PyPA’s requirements-file guidance supports repeatable installs with pinned versions and hashes. SPDX and CycloneDX define machine-readable SBOM formats. GitHub recommends pinning third-party Actions to full commit SHAs, which identifies the exact reviewed action code.

### AutoPulse policy decisions

- PR-002 must select one documented resolver/lock workflow, commit the generated lock/constraints artifact(s), and use exact resolved versions plus artifact hashes for release and CI installation. Direct Git URLs, editable dependencies, unpinned ranges in release resolution, and install-time code from unreviewed indexes are prohibited.
- Source project metadata declares broad compatibility only where necessary; the release lock is the reproducibility authority. Development/test/docs dependencies are separated from runtime dependencies.
- Dependabot or its successor may propose updates, but does not authorize merging. Every dependency update receives tests, license review, vulnerability review, and release-note impact assessment. Critical/high findings affecting a shipped supported path require an owner, severity rationale, mitigation, and target date; a release is blocked unless the risk is fixed or a documented exception has an expiry date and independent Lead Auditor sign-off. The implementer may not approve their own exception.
- PR-002 must produce a release SBOM in SPDX JSON **or** CycloneDX JSON (the selected format and tool are an implementation decision), bound to the exact release commit/artifacts and including direct/transitive components, versions, checksums where available, licenses, and package origin. It contains no raw telemetry, VINs, local absolute paths, credentials, or private URLs. Before committing or publishing it, an automated gate must scan the generated SBOM for absolute-local-path and private-URL patterns; a match fails closed pending review.
- Apache-2.0 remains the project license. Release evidence must inventory third-party licenses and block unknown, incompatible, or policy-disallowed licenses pending maintainer/legal review. This policy does not make a legal compatibility determination.
- At release cut, publish/retain the lock/constraints evidence, SBOM, vulnerability scan result, license report, build/test logs, and checksums according to the retention decision in PR-004. Artifacts must be sanitized.

## Privacy and data handling

AutoPulse’s offline profile is local-first: fixture data and output stay on the operator-controlled filesystem unless the operator deliberately uses an external tool outside AutoPulse. The release itself collects no analytics, crash reporting, identifiers, or live telemetry.

Never request, commit, attach to CI, send in support reports, or publish:

- raw VINs or VIN-like strings, registration/ownership data, exact location, routes, timestamps that enable trip reconstruction, or unique vehicle IDs;
- raw CAN/OBD/UDS payload bytes, ECU serials, full diagnostic captures, adapter serial numbers, seed-key material, session/security-access data, or write/control commands;
- credentials, tokens, cookies, private keys, environment files, private workspace/task URLs, absolute local paths, or raw exception/debug dumps; or
- production customer/fleet data and evidence from road tests or live capture.

Support may request the AutoPulse version, OS/Python major-minor, sanitized command invocation, sanitized error category, content-free checksum of a fixture, and a minimal synthetic reproducer. A sanitized command invocation contains the subcommand and non-sensitive flags only; every path-like argument, value, fixture name, identifier, and free-form input is replaced with a placeholder. `vin_hashed` may be used only for local correlation when it conforms to the existing validation contract; it is not anonymous, must not be treated as public, and must not appear in shared support artifacts unless a future approved policy explicitly permits it.

## Threat model and trust boundaries

### Assets and security objectives

Assets include source/release provenance; package artifacts and dependency integrity; the read-only/offline boundary; fixtures and derived outputs; privacy-sensitive vehicle/operator data; CI credentials; and support artifacts. Objectives are integrity of validated replay, prevention of diagnostic control, confidentiality of prohibited data, reproducible attribution of releases, and safe failure when inputs or dependencies are untrusted.

### Trust boundaries and required controls

| Boundary | Threats | Required release-policy control |
| --- | --- | --- |
| Untrusted fixture -> validator/replayer | malformed/oversized input, parser abuse, schema bypass, hostile values | validate before processing; bounded resource behavior must be specified/tested; reject invalid/non-finite data; never execute fixture content |
| Release source -> build artifact | source substitution, confused build provenance | protected review/release process, exact commit/version evidence, reproducible clean-install verification, checksums |
| Package index/dependency -> environment | typosquatting, compromised or substituted artifact, dependency drift | approved index, locked/hash-verified resolution, SBOM, vulnerability/license review, no unreviewed direct URLs |
| GitHub Action -> CI | mutable action tag or excessive token permissions | least-privilege workflow permissions; PR-003 pins third-party Actions to full SHAs and reviews workflow changes |
| Local output/log -> support/public channel | privacy leakage, log injection, unsafe error detail | structured sanitized output; no automatic upload; support templates prohibit sensitive content; redaction and artifact review |
| Offline package -> vehicle/adapter | accidental live connection or diagnostic control | offline release excludes adapter/capture workflows; no live command path is a supported public interface; red-line regression tests protect any retained code |

### Security red lines

1. No OBD-II/UDS diagnostic write, control, session, security-access, VIN-read, DTC-clear, adapter discovery, or live capture capability may be added to the offline release profile.
2. No raw VIN, raw payload bytes, secrets, or private operational data may enter releases, fixtures, CI logs/artifacts, documentation, or support.
3. Untrusted replay input must not cause code execution, network access, automatic live adapter access, or silent acceptance of invalid data.
4. A release gate fails closed if required provenance, dependency, SBOM, security, privacy, test, or audit evidence is missing.

Security vulnerabilities are reported through the route in `SECURITY.md`. Maintainers acknowledge, triage, and provide a remediation/status update within the timelines set by PR-004; exact service-level targets remain unresolved.

## Minimum observability and support

Offline workflows must provide local, sanitized, structured outcome signals: release version, command/workflow name, accepted/rejected/processed counts, stable error category, and exit status. They must not default to file logging, network reporting, or raw input echoing. PR-004 defines the safe support template, retention/deletion procedure, severity ownership, escalation route, and operator guidance that distinguishes a safe stop from a recoverable offline-input error.

## Release gates and required documentation

No release-ready claim is allowed until PR-005 records all applicable evidence:

1. clean install from declared artifacts in every supported matrix cell;
2. full automated test suite plus adversarial tests selected by Claude;
3. schema/security/red-line tests, including malformed replay and privacy-log cases;
4. build/package metadata validation, locked/hash-verified dependency install, license report, vulnerability review, SBOM generation, and artifact checksum/provenance evidence. The dependency install must prove wheel availability for every locked dependency on each supported matrix cell, and the generated SBOM must pass the automated privacy/path-leak scan;
5. PR-003 CI evidence that checks are deterministic, fail closed, run with least privilege, and validate the deployed documentation base path;
6. a fail-closed release-artifact content check: list the contents of each built sdist/wheel and compare them to an approved inclusion allowlist. It must reject secrets, environment files, VCS metadata, unapproved fixtures, test-only modules, and other files outside the declared distribution contract;
7. documentation review covering installation, offline boundary, non-goals, public API/CLI, supported platforms, upgrade policy, reporting security issues, data handling, known limitations, and release notes; and
8. Claude’s recorded independent final verdict. A blocker prevents release readiness; no Claude approval is claimed by this specification.

## Acceptance criteria and sequencing

| Work item | Preconditions | Required outcome / acceptance criteria |
| --- | --- | --- |
| PR-002 | This spec plus Claude QA plan/review | Implement the selected standards-based packaging and locked/hash-verified install; prove prebuilt-wheel availability for all locked dependencies per supported cell; generate and path-scan sanitized SBOM, license, vulnerability, and artifact-content-allowlist evidence. Test escaping of CSV output values beginning with `=`, `+`, `-`, or `@`. |
| PR-003 | PR-002 artifact model approved | Implement documented CI matrix and fail-closed release checks; validate package/docs including deployed base path; least-privilege/pinned Action controls; sanitized retained evidence. |
| PR-004 | Threat model and observability boundary approved | Deliver privacy-safe support, incident, retention/redaction, and security-response runbooks; only minimum approved local observability; no new telemetry or live capability. |
| PR-005 | PR-002 through PR-004 complete and audited | Exercise a tagged RC on all supported cells; collect every gate artifact; publish limitations/non-goals; obtain Claude final verdict. Block release readiness for unresolved findings. |

Each item is a separate Gated Delivery task. The Lead Architect approves scope and verification; Claude supplies independent adversarial QA and final review; the Builder implements only the approved task. No task may silently broaden the offline profile.

The support matrix never expands automatically when a new CPython minor release ships. Adding a Python, OS, or architecture cell requires a documented compatibility decision and the complete applicable PR-002/PR-003 evidence before release documentation can call it supported.

## Sourced findings and references

All URLs below were checked on 2026-08-11. They support external technical facts, not AutoPulse-specific policy decisions.

- Python Developer’s Guide, [Status of Python versions](https://devguide.python.org/versions/): CPython lifecycle/status source used to select a maintained narrow matrix.
- PyPA, [pyproject.toml specification](https://packaging.python.org/en/latest/specifications/declaring-project-metadata/): project metadata, build-system, dependencies, `requires-python`, and entry-point fields.
- PyPA, [Version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/): PEP 440-compatible public-version scheme and its compatibility with major/minor/micro SemVer segments.
- PyPA, [Dependency specifiers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/): PEP 508 dependency and environment-marker syntax.
- pip documentation, [Secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/): hashes and repeatable dependency installation guidance.
- SPDX, [SPDX 3.0.1 specification](https://spdx.dev/wp-content/uploads/sites/31/2024/12/SPDX-3.0.1-1.pdf), and CycloneDX, [SBOM standard](https://cyclonedx.org/specification/overview/): standardized SBOM formats.
- GitHub Docs, [Security hardening for GitHub Actions](https://docs.github.com/en/actions/how-tos/security-for-github-actions/security-guides/security-hardening-for-github-actions): full commit-SHA pinning and least-privilege workflow guidance.

## Weak claims and unresolved decisions

- The selected build backend, resolver/lock format, exact package name, distribution channels, signing/attestation mechanism, SBOM tool/format, and vulnerability/license scanners are intentionally deferred to PR-002.
- CPython 3.13/3.14 and each named OS cell are not support promises until PR-003 proves them; their availability or lifecycle status alone does not establish AutoPulse compatibility. CPython 3.11/3.12 may later become a documented best-effort tier for downstream distribution users, but not a guaranteed desktop profile while they are security-only.
- The current repository lacks `pyproject.toml`, a Python lock/constraints artifact, SBOM, release build, and comprehensive release matrix. This is an observation, not a claim that those controls already exist.
- Exact support-response SLAs, artifact retention duration/location, accepted third-party-license list, severity scoring method, publication channel, and human legal/privacy/safety review authority require maintainer decisions.
- The exact allowlist representation and the SBOM path/private-URL detection patterns are PR-002 implementation decisions; both must be reviewable and fail closed against the policy above.
- “Offline” describes AutoPulse runtime behavior after installation, not a guarantee that every dependency installer can work without a pre-staged local package cache. PR-002 must document a reproducible disconnected-install option if that becomes a release requirement.
