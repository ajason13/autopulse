---
name: project-context-sync
description: Use for project-agnostic updates to project memory, task trackers, documentation hubs, status pages, or handoff notes after branches, PRs, audits, decisions, or verification results change.
metadata:
  short-description: Sync project memory and status
---

# Project Context Sync

Use this skill when repository work needs corresponding updates in project memory or task tracking.

## Sync Targets

Depending on the project, update:

- Active memory file such as `CONTEXT.md`.
- Task tracker or Notion/Jira/Linear page.
- Engineering wiki or architecture decision record.
- Public docs when user-facing behavior changed.
- PR/release notes.
- Future-work backlog.

## What to Capture

- Current branch and PR.
- Status and next owner.
- Decisions made and who made them.
- Verification commands and results.
- Audit/sign-off status.
- Deferred work and explicit non-goals.

## Writing Style

- Use compact, dated entries.
- Prefer facts over narrative.
- Include exact command results where useful, but summarize long logs.
- Avoid private secrets, raw customer data, or unnecessary operational detail.

## Sanity Check

Before finishing:

- Project memory matches repo state.
- Task tracker status matches PR/test/audit state.
- Future work is not mixed into current acceptance criteria.
- The next agent or human can continue without reading the whole chat.
