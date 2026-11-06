# AutoPulse Documentation Site (Starlight)

This directory contains the source code for the AutoPulse documentation site, built with [Starlight](https://starlight.astro.build/).

## Local Development

Use **Node.js 24**, the major pinned in `.nvmrc` and used by CI, with its bundled
npm. Use `npm ci` to install `package-lock.json` without updating dependencies.
Run commands from `grubby-galaxy`, the directory containing `package.json`.
Python is only needed for Python development; follow
[Getting Started](src/content/docs/guides/getting-started.md) for that setup.

### Windows PowerShell (x64)

Install the **24.x Windows x64** distribution from the
[official Node.js download page](https://nodejs.org/en/download), selecting
version 24 explicitly. The installer can add Node and npm to PATH; reopen
PowerShell afterward. Alternatively, extract the official Windows x64 ZIP into
a user-writable directory and add that directory to the current shell's PATH:

```powershell
# ZIP alternative only: replace with the folder containing node.exe and npm.cmd.
$env:Path = "C:\Tools\node-v24.x-win-x64;$env:Path"
```

No Unix version manager, WSL, or Git Bash is needed. Use `npm.cmd` and `npx.cmd`
so PowerShell does not select their `.ps1` wrappers; no execution-policy change
is required. Run each command only after the preceding command succeeds;
`$LASTEXITCODE` should be `0` after native executable commands.

From a writable parent directory (or use an existing checkout):

```powershell
git clone https://github.com/ajason13/autopulse.git "AutoPulse Development"
Set-Location "AutoPulse Development\grubby-galaxy"
Get-Content .nvmrc
node --version
npm.cmd --version
npm.cmd ci
npm.cmd run dev
```

Confirm `.nvmrc` says `24` and `node --version` starts with `v24.`; record the
actual npm version. Open [http://localhost:4321/autopulse/](http://localhost:4321/autopulse/).
Stop dev with Ctrl+C before preview or browser tests. The remaining Windows commands are:

```powershell
npm.cmd run build
npm.cmd run preview
# Open http://localhost:4321/autopulse/ and stop preview with Ctrl+C.
npx.cmd playwright install chromium
npm.cmd run test:smoke
npm.cmd run test:e2e
```

If npm reports a cache access error, retry the failed install with a temporary
Windows cache; keep the lockfile and dependency versions:

```powershell
$docsNpmCache = Join-Path ([System.IO.Path]::GetTempPath()) 'autopulse-docs-npm-cache'
npm.cmd ci --cache "$docsNpmCache"
```

Windows 11 is the preferred native development environment. For Windows 10,
[Microsoft's lifecycle record](https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro)
ends Home/Pro support on October 14, 2025. The
[Node 24 platform policy](https://github.com/nodejs/node/blob/v24.x/BUILDING.md#platform-list)
lists Windows x64 starting at Windows 10/Server 2016 but excludes vendor-EOL
platforms regardless of the table. Check the exact Windows edition and servicing
status before interpreting compatibility results as upstream support.
Windows 10 docs compatibility is unverified until its native checks are recorded;
a successful build alone does not change that support policy.
See the [native verification record](../docs/qa/windows-docs-onboarding.md)
for executed cells and remaining work. Docs development evidence does not grant
AutoPulse desktop release support; that decision remains in
[#141](https://github.com/ajason13/autopulse/issues/141).

### macOS / Linux

With Unix `nvm` installed, start from the repository root:

```sh
cd grubby-galaxy
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install
nvm use
node --version
npm --version
npm ci
npm run dev
```

Open [http://localhost:4321/autopulse/](http://localhost:4321/autopulse/) and stop
with Ctrl+C. If npm reports an `EACCES` cache error, use a user-writable temporary
cache without modifying dependencies:

```sh
npm ci --cache "$(mktemp -d)"
```

## Build and Preview

To create a production build and preview it:

```sh
npm run build
npm run preview
```

The configured production base path is `/autopulse/`, so preview URLs are served from
[http://localhost:4321/autopulse/](http://localhost:4321/autopulse/).

## Smoke Tests

Install Chromium once after `npm ci`, then run the Starlight homepage smoke suite:

```sh
npx playwright install chromium
npm run test:smoke
```

This builds the current docs, starts its own foreground Astro preview server, and checks the homepage shell, mobile menu, desktop sidebar, and GitHub Pages base-path links. Both browser suites wait for their own server to finish building and bind its port; they never reuse an existing server. An occupied port fails verification without stopping the existing process or switching ports silently. Playwright stops its owned server after success or failure (with a forced process-tree cleanup if graceful shutdown times out).

The default origin is `http://127.0.0.1:4321`, with pages under `/autopulse/`. To leave a dev/preview server running on that port, select a free verification port using `AUTOPULSE_DOCS_PORT`:

```sh
AUTOPULSE_DOCS_PORT=4322 npm run test:smoke
AUTOPULSE_DOCS_PORT=4322 npm run test:e2e
```

In PowerShell, use:

```powershell
$env:AUTOPULSE_DOCS_PORT = '4322'
npm.cmd run test:smoke
npm.cmd run test:e2e
Remove-Item Env:AUTOPULSE_DOCS_PORT
```

Run the suites sequentially within a checkout because each rebuilds `dist/`. The test server uses Astro's programmatic build/preview API so agent-triggered CLI backgrounding and preview lock files cannot detach it from Playwright.

`npm run test:lifecycle` exercises stale HTTP 200/404 servers, rebuilding stale output, and port cleanup after a passing and deliberately failing request probe. Run it after `npm run build` and separately from the browser suites; CI runs it before smoke/e2e.

Run the broader Starlight regression suite with:

```sh
npm run test:e2e
```

This checks every generated docs route, interior-page mobile and desktop navigation, search dialog behavior, and internal links staying under the `/autopulse/` GitHub Pages base path.

## Mermaid Troubleshooting

If the architecture diagram is missing, reproduce with the pinned Node version,
`npm ci`, and the current-build browser suites before changing dependencies or
Mermaid configuration. The [clean-install verification record](../docs/qa/docs-mermaid-clean-install.md)
includes the tested versions, results, and a bounded local recovery procedure.

## Key Documentation

The canonical public US-001, US-002, US-004, and US-006 specifications live in
`../docs/specs/`. Edit those files first, then copy each changed file unchanged
to `src/content/docs/specs/` with the same filename. Commit both copies together.
Keep frontmatter in the canonical file and use links that work both on GitHub
and on the published site. The original US-006 implementation design is retained
in `../docs/research/us-006-original-design.md`; it is historical research,
not a second public specification.

Astro checks byte equality for all four specifications during configuration,
including direct Astro builds, `npm run build`, dev startup, Pages builds, and
the browser suites' programmatic builds. Missing or stale copies fail with the
filename before publication. To verify an edit, run `npm run build` followed by
`npm run test:e2e` for route, navigation, and internal-link checks. No generation
step rewrites source files automatically.

The specifications are available at the following local routes (when the dev server is running):

- [/autopulse/specs/us-001-engine-data-contract/](/autopulse/specs/us-001-engine-data-contract/)
- [/autopulse/specs/us-002-virtual-replay-harness/](/autopulse/specs/us-002-virtual-replay-harness/)

## 🚀 Project Structure

Inside this folder, you'll see:

```
.
├── public/
├── src/
│   ├── assets/
│   ├── content/
│   │   └── docs/
│   └── content.config.ts
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

- `src/content/docs/`: Where the `.md` or `.mdx` pages live.
- `src/assets/`: Images and other assets.
- `public/`: Static assets like favicons.

## Commands

| Command                   | Action                                           |
| :------------------------ | :----------------------------------------------- |
| `npm ci`                  | Installs locked dependencies                            |
| `npm run dev`             | Starts local dev server at `localhost:4321/autopulse/` |
| `npm run build`           | Build your production site to `./dist/`          |
| `npm run preview`         | Preview your build locally, before deploying     |
| `npm run test:smoke`      | Run Starlight homepage smoke checks              |
| `npm run test:e2e`        | Run full Starlight docs regression checks         |
| `npm run astro ...`       | Run CLI commands like `astro add`, `astro check` |

## 👀 Learn More

Check out [Starlight’s docs](https://starlight.astro.build/) or the [Astro documentation](https://docs.astro.build).
