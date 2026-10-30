# AutoPulse Documentation Site (Starlight)

This directory contains the source code for the AutoPulse documentation site, built with [Starlight](https://starlight.astro.build/).

## Local Development

To run the documentation site locally, follow these steps:

```sh
# Navigate to the docs directory
cd grubby-galaxy

# Initialize nvm (if not already in your shell)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Use the project Node version and start development
nvm use
npm install
npm run dev
```

The site will be available at [http://localhost:4321/autopulse/](http://localhost:4321/autopulse/).

The project currently pins Node via `.nvmrc` to the active LTS/current version used by CI-compatible local builds. If `npm install` fails with `EACCES` under `~/.npm`, the local npm cache contains files owned by another user. Avoid changing project dependencies to work around that; either repair the cache ownership outside the repo or run one install with a temporary cache:

```sh
npm install --cache /private/tmp/autopulse-npm-cache
```

For peer-resolution errors from npm 11 against otherwise compatible Astro/Starlight packages, prefer a targeted `--legacy-peer-deps` install over `--force`.

## Build and Preview

To create a production build and preview it:

```sh
npm run build
npm run preview
```

The configured production base path is `/autopulse/`, so preview URLs are served from
[http://localhost:4321/autopulse/](http://localhost:4321/autopulse/).

## Smoke Tests

Run the Starlight homepage smoke suite with:

```sh
npm run test:smoke
```

This builds the current docs, starts its own foreground Astro preview server, and checks the homepage shell, mobile menu, desktop sidebar, and GitHub Pages base-path links. Both browser suites wait for their own server to finish building and bind its port; they never reuse an existing server. An occupied port fails verification without stopping the existing process or switching ports silently. Playwright stops its owned server after success or failure (with a forced process-tree cleanup if graceful shutdown times out).

The default origin is `http://127.0.0.1:4321`, with pages under `/autopulse/`. To leave a dev/preview server running on that port, select a free verification port using `AUTOPULSE_DOCS_PORT`:

```sh
AUTOPULSE_DOCS_PORT=4322 npm run test:smoke
AUTOPULSE_DOCS_PORT=4322 npm run test:e2e
```

In PowerShell, set `$env:AUTOPULSE_DOCS_PORT = '4322'` before running the npm commands. Run the suites sequentially within a checkout because each rebuilds `dist/`. The test server uses Astro's programmatic build/preview API so agent-triggered CLI backgrounding and preview lock files cannot detach it from Playwright.

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
| `npm install`             | Installs dependencies                            |
| `npm run dev`             | Starts local dev server at `localhost:4321/autopulse/` |
| `npm run build`           | Build your production site to `./dist/`          |
| `npm run preview`         | Preview your build locally, before deploying     |
| `npm run test:smoke`      | Run Starlight homepage smoke checks              |
| `npm run test:e2e`        | Run full Starlight docs regression checks         |
| `npm run astro ...`       | Run CLI commands like `astro add`, `astro check` |

## 👀 Learn More

Check out [Starlight’s docs](https://starlight.astro.build/) or the [Astro documentation](https://docs.astro.build).
