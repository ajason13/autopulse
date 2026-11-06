# Native Windows documentation onboarding

Issue [#155](https://github.com/ajason13/autopulse/issues/155) owns the shared
setup and native Windows 11 evidence. At the maintainer's request, Windows 10
execution is split into [#174](https://github.com/ajason13/autopulse/issues/174)
because its machine was unavailable. It remains unverified. Python evidence
belongs to #154; desktop release-support decisions remain in #141.

## Procedure

Follow [the docs README](../../grubby-galaxy/README.md#local-development).
Use native PowerShell with Node 24 x64, record the actual versions, and use a
clean checkout containing spaces in its path. Run each command only after the
previous one succeeds. Stop manual dev/preview servers before browser checks;
run suites sequentially. Leave `AUTOPULSE_DOCS_PREBUILT` unset for normal tests.

Record `git rev-parse HEAD`, OS caption/build/architecture (for example,
`Get-CimInstance Win32_OperatingSystem`), `$PSVersionTable.PSVersion`,
`node --version`, `npm.cmd --version`, commands and their exit codes. Do not
publish machine identifiers, user paths or unrelated environment variables.

## Windows 11 run — 2026-11-05

- OS: Microsoft Windows 11 Pro, 25H2, x64, build **26200.9711**;
  CIM version `10.0.26200`. The legacy registry ProductName says Windows 10;
  CIM caption and build identify Windows 11.
- Shell: native PowerShell **7.6.5**.
- Tested source: `8ff0759` on `codex/155-windows-docs-setup`, based on
  `b13423610563fc8fba9957b3c78b2819e49508c3`.
- Clean local Git clone in `.cache/AutoPulse Docs Windows`, with commands run
  from its `grubby-galaxy` directory; no copied node_modules or dist.
- Runtime: official Windows x64 **Node 24.22.1**, bundled **npm 11.19.1**,
  using the README's portable ZIP/PATH route. Archive SHA256 matched official
  `SHASUMS256.txt`:
  `d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5`.
  This verifies the ZIP route, not the MSI installer UI.

| Command/check | Result |
| --- | --- |
| `node --version`; `npm.cmd --version` | Exit 0; versions above |
| `npm.cmd ci --cache <Windows temporary cache>` | Exit 0; 479 packages installed, audit reported zero vulnerabilities |
| `npx.cmd playwright install chromium` | Exit 0 |
| `npm.cmd run build` | Exit 0; 13 pages generated |
| `npm.cmd run dev` and `npm.cmd run preview` | Both served homepage and Getting Started with HTTP 200 and expected content at `http://localhost:4321/autopulse/`; owned process trees stopped after checks; port 4321 released |
| `npm.cmd run test:smoke` | Exit 0; 6 passed, 2 expected device-specific skips |
| `npm.cmd run test:e2e` | Exit 0; 50 passed, 2 expected device-specific skips |

Both suites rebuilt the current docs before starting their owned previews.
They ran sequentially on `AUTOPULSE_DOCS_PORT=4322`; a successful socket bind
afterward confirmed port 4322 was released. Coverage included desktop/mobile
navigation, routes, base-path links and Mermaid rendering. Dev/preview were
launched with the documented npm commands by a temporary PowerShell harness;
it checked both routes, stopped its owned process trees and checked port cleanup.
They are long-running servers, so successful verification is HTTP readiness and
cleanup, not a normal server exit. The harness exited 0. No interactive Ctrl+C
or MSI installer exercise is claimed. The subsequent evidence commit adds only
this record; tested setup and rendered source remain unchanged.

Existing content warnings (empty i18n collection/missing 404 entry) and bundle
size warnings were non-blocking. No dependencies, lockfiles, Python behavior,
server lifecycle, schemas, publishing workflow or runtime code changed. No
prose-mirroring tests were added.

## Remaining Windows 10 cell

No native Windows 10 result is claimed. #174 requires the same clean-install,
build, dev/preview, Chromium suites and server-cleanup checks on the actual
Windows 10 machine, recording edition/build/servicing status and exact versions.
[Microsoft's Home/Pro lifecycle](https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro)
ends support on October 14, 2025. The
[Node 24 policy](https://github.com/nodejs/node/blob/v24.x/BUILDING.md#platform-list)
lists x64 Windows 10/Server 2016 and newer but excludes vendor-EOL platforms.
Compatibility results must be distinguished from upstream OS support and
AutoPulse release-support decisions. Sources checked 2026-11-05.
