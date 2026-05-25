---
name: autopulse-pr-release-checklist
description: Use before creating or updating AutoPulse pull requests, after Claude sign-off, before merge readiness checks, or when summarizing verification, risk, docs, Notion, and project-memory updates for a story branch.
metadata:
  short-description: Prepare AutoPulse PRs
---

# AutoPulse PR Release Checklist

Use this skill before opening or updating an AutoPulse PR.

## Pre-PR Checks

1. Confirm branch and base:
   - `git status --short --branch`
   - `git log --oneline --decorate -5`
2. Inspect diff:
   - `git diff --stat main...HEAD`
   - `git diff --check`
3. Run targeted tests required by the story/audit.
4. Run broader regression tests proportional to risk.
5. Update project artifacts: `CONTEXT.md`, docs, Notion, and future-work records when relevant.
6. Leave unrelated untracked or dirty user files untouched.

## PR Body Shape

```markdown
## Summary
- ...

## Verification
- `command` -> result

## Risk / Notes
- ...
```

Add an `Audit` section when Claude/Gemini review is part of the merge gate.

## AutoPulse-Specific Notes

- Mention if Claude has signed off or if review is still pending.
- Mention if a branch is a follow-up with no intended runtime behavior changes.
- Include docs build evidence for `grubby-galaxy/` changes.
- Include schema/security regression evidence for `schemas/`, adapters, validators, or alert exporters.
- Note intentionally untouched untracked files only if they may confuse reviewers.

## PR Creation

Use GitHub CLI when authenticated:

```bash
gh pr create --base main --head <branch> --title "<title>" --body "<body>"
```

After creation, report only the PR number/link and high-signal verification summary.
