---
name: autopulse-local-env
description: Use for AutoPulse local development setup, Python/Node environment commands, dependency installation, docs preview, Playwright browser setup, test command selection, or documenting reproducible local execution.
metadata:
  short-description: Manage AutoPulse local environment
---

# AutoPulse Local Environment

Use this skill for local setup, verification commands, and environment handoff in AutoPulse.

## Python

Common commands from repo root:

```bash
python3 -m pytest -q
python3 -m pytest tests/<file>.py -q
```

If imports require it:

```bash
export PYTHONPATH=$PYTHONPATH:./src
```

Prefer targeted tests while iterating, then broaden before PR.

## Starlight / Astro Docs

Run from `grubby-galaxy/`:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npm install
source "$HOME/.nvm/nvm.sh" && nvm use && npm run build
source "$HOME/.nvm/nvm.sh" && nvm use && npm run preview -- --host 127.0.0.1
```

Stop preview servers before finalizing work.

## Playwright

Run from `grubby-galaxy/`:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npm run test:smoke
```

Install browsers only if missing:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npx playwright install chromium
```

## Handoff Notes

Record:

- Exact command.
- Pass/fail result.
- Count of passing tests/pages when available.
- Any harmless warnings that future users may see.

Do not hide failed commands; state what failed and what was not verified.
