---
name: autopulse-playwright-regression
description: Use when creating, expanding, or debugging AutoPulse Playwright suites for Starlight docs, including smoke tests, formal regression tests, mobile/desktop navigation checks, GitHub Pages base-path coverage, and browser artifact hygiene.
metadata:
  short-description: Build AutoPulse Playwright tests
---

# AutoPulse Playwright Regression

Use this skill for Playwright Test work in `grubby-galaxy/`.

## Suite Levels

- Smoke suite: fast checks for homepage rendering, mobile menu, desktop sidebar, and critical links.
- Regression suite: broader route crawl, sidebar/search checks, key content assertions, no broken internal links, and deploy base-path coverage.

Keep smoke tests stable and minimal. Put slower exhaustive checks in the formal regression suite.

## Config Guidance

- Use `baseURL: "http://127.0.0.1:4321"`.
- Test deployed-path behavior through `/autopulse/`.
- Prefer a Playwright `webServer` that builds and previews the Astro site.
- Use desktop and mobile Chromium projects at minimum.
- Ignore generated artifacts: `test-results/`, `playwright-report/`, and `blob-report/`.

## Assertions to Prefer

- Role-based locators for links, buttons, navigation, and headings.
- URL assertions that catch accidental root-relative links.
- Mobile menu open/close behavior.
- Sidebar visibility on desktop.
- Content assertions for key docs pages rather than pixel-perfect screenshots.

## Commands

Run from `grubby-galaxy/`:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npm run test:smoke
source "$HOME/.nvm/nvm.sh" && nvm use && npx playwright test --config <config>
```

Install browser binaries only when missing:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use && npx playwright install chromium
```

## Failure Triage

- If a link test fails, inspect whether the URL escaped `/autopulse/`.
- If mobile nav fails, inspect whether a page template removed the Starlight shell.
- If preview fails, run `npm run build` separately and read the Astro error first.
