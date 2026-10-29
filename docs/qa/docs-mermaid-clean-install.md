# Documentation Mermaid clean-install verification

## Outcome and provenance

[Issue #127](https://github.com/ajason13/autopulse/issues/127) could not be
reproduced on main `89ed9ae324c1b414db72e6bf90f98f1c368328e3` on
2026-10-29. The freshly built architecture page rendered its Mermaid SVG in
desktop and mobile Chromium before and after a clean locked dependency install.
No rendering, dependency, configuration, or assertion change was needed.

Environment: macOS 15.4.1 (24E263), x86_64, Node 24.15.0 selected by
`grubby-galaxy/.nvmrc` (major 24), npm 12.2.1. Commands ran from
`grubby-galaxy/`. The existing Playwright Chromium installation was available;
no browser download was needed.

| Package | Before `npm ci` | After `npm ci` |
| --- | --- | --- |
| Astro | 7.4.2 | 7.4.2 |
| `@astrojs/starlight` | 0.41.7 | 0.41.7 |
| `astro-mermaid` | 2.2.0 | 2.2.0 |
| Mermaid | 12.2.0 | 12.2.0 |
| `@playwright/test` | 1.60.0 | 1.60.0 |
| sharp | 0.35.5 | 0.35.5 |

`npm ls --all --json` contained 1,212 dependency paths both before and after
installation, with zero version differences. `npm ci` used a fresh temporary
cache (`/private/tmp/autopulse-127-npm-cache`), added 482 packages, audited 483,
and reported zero vulnerabilities. The committed lockfile was unchanged:
SHA-256 `812374b247c4d932feae4c9ff1a366a1faebb82e27fbe596e069c5b3c2bfb31e`.
Its Git blob also matches the original issue's reviewed commit
`d5d2bd1623d37a737b07d75334cf54ed4113a7b1`.

The historical failing installation was not preserved. Its installed versions,
generated assets, and exact cause cannot be reconstructed from the issue's
results alone. The earlier passing old server did not establish current-build
correctness. The current baseline already includes
[PR #156](https://github.com/ajason13/autopulse/pull/156), which makes both suites
build and own their preview server. This verification establishes a passing
clean baseline; it does not establish that reinstalling repaired a reproduced
fault or identify the cause of the earlier ignored-Markdown-plugin warning.

## Verification results

All commands below exited zero. Browser commands used
`AUTOPULSE_DOCS_PORT=4322` and ran sequentially.

| Check | Result |
| --- | --- |
| Pre-install `npm run test:e2e -- --grep 'architecture diagram'` | 2 passed: desktop and mobile |
| `npm ci --cache /private/tmp/autopulse-127-npm-cache` | Clean locked install passed |
| `npm audit --omit=dev --audit-level=high` | Zero vulnerabilities |
| `npm run build`, after removing generated `.astro/` and `dist/` | 13 pages built |
| `npm run test:smoke` | 6 passed, 2 expected device-specific skips |
| `npm run test:e2e` | 50 passed, 2 expected device-specific skips |

Both Mermaid tests retain the visible `pre.mermaid svg` assertion and checks
for Data Ingestion Layer, Validation & Security, and Drop & Log. They visit
`/autopulse/reference/architecture/`. Each browser suite rebuilt the current
source and waited for its owned child's readiness announcement at
`http://127.0.0.1:4322/autopulse/`; an unrelated existing server cannot satisfy
that check. The verification port was free after the suites stopped.

The install reported blocked optional `fsevents` install scripts. Build/browser
output contained large-chunk, empty `i18n`, missing `docs → 404`, and color-env
warnings. These did not prevent the checks above from passing. The historical
ignored-Markdown-plugin warning was absent from this run.

## Bounded local recovery and reproduction

Use these Unix-shell commands from the repository root to replace the local
dependency tree with the committed lockfile and rebuild generated assets.
The Node cleanup command removes only generated docs output and Astro cache.

```sh
cd grubby-galaxy
source "$HOME/.nvm/nvm.sh"
nvm use
node --version
npm --version
npm ls --all --json > /tmp/autopulse-docs-install-before.json
docs_npm_cache="$(mktemp -d)"
npm ci --cache "$docs_npm_cache"
npm ls --all --json > /tmp/autopulse-docs-install-after.json
npm audit --omit=dev --audit-level=high
node --input-type=module -e 'import {rmSync} from "node:fs"; for (const path of ["dist", ".astro"]) rmSync(path, {recursive:true, force:true});'
npm run build
AUTOPULSE_DOCS_PORT=4322 npm run test:smoke
AUTOPULSE_DOCS_PORT=4322 npm run test:e2e
```

Use a free port; an occupied port fails verification without replacing its
listener. Run these commands in order and stop if any fails. If Chromium is
missing, install it with `npx playwright install chromium` before the suites.
The temporary cache avoids modifying a user-owned npm cache; retain it while
investigating an install failure. See the
[docs README](../../grubby-galaxy/README.md#smoke-tests) for server lifecycle
details.

If the diagram still fails, retain the dependency comparison, build warnings,
failing URL, browser error, and Playwright failure artifacts. Report the
reproduced difference before changing dependencies or Mermaid configuration;
keep the desktop/mobile SVG assertions intact.
