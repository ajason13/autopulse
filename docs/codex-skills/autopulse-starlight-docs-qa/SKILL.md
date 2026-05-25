---
name: autopulse-starlight-docs-qa
description: Use for AutoPulse Starlight/Astro documentation changes, GitHub Pages base-path issues, docs navigation bugs, landing-page fixes, docs build failures, or Playwright smoke checks against the docs site.
metadata:
  short-description: QA AutoPulse Starlight docs
---

# AutoPulse Starlight Docs QA

Use this skill when editing or testing the AutoPulse docs site under `grubby-galaxy/`.

## Core Rules

- GitHub Pages deploys under `/autopulse/`; internal links must respect that base path.
- Avoid root-relative links like `/specs/...` unless Astro/Starlight explicitly rewrites them correctly.
- The homepage should retain access to Starlight navigation unless the user explicitly wants a standalone splash page.
- Mobile and desktop navigation are both acceptance criteria.

## Local Commands

Run from `grubby-galaxy/`:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npm run build
source "$HOME/.nvm/nvm.sh" && nvm use && npm run preview -- --host 127.0.0.1
source "$HOME/.nvm/nvm.sh" && nvm use && npm run test:smoke
```

Use the commands that match the change; do not run preview forever without stopping it.

## Smoke Coverage

For homepage/navigation fixes, verify:

- `/autopulse/` renders the docs shell.
- Desktop sidebar is visible without interaction.
- Mobile menu button opens and exposes Guides, Specs, Reference, and relevant story pages.
- Homepage CTA/card links stay under `/autopulse/`.
- External links point to the correct repository or resource.

## Visual Inspection

Use Playwright CLI or Playwright Test when useful:

- Check desktop and mobile snapshots.
- Confirm no overlapping text or hidden navigation.
- Confirm the current URL after clicking key links.
- Stop any local preview server before finishing.

## Documentation Style

- Keep docs technical and direct.
- Prefer durable architecture/status information over implementation chatter.
- Update landing-page cards, sidebar config, and relevant reference/spec pages together when adding new docs.
