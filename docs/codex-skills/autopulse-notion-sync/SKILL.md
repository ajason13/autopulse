---
name: autopulse-notion-sync
description: Use when AutoPulse Notion pages need to be searched, updated, commented on, or synchronized with repository work, including story status, Claude sign-off, PR state, future work, engineering wiki entries, or project hub updates.
metadata:
  short-description: Sync AutoPulse Notion status
---

# AutoPulse Notion Sync

Use this skill for Notion updates tied to AutoPulse stories, audits, PRs, docs, and future work.

## Before Updating

- Prefer Notion search/fetch over memory when locating pages.
- Fetch the target page before editing so property names and existing content are known.
- If updating a database page, use the exact schema/property names returned by Notion.
- Keep Notion summaries concise; link or name repo artifacts only when useful to humans.

## Pages Usually Affected

- Story task page: status, scope, verification, blocker resolution, final audit status.
- Epic or project hub: one-line progress summary and current branch/PR.
- Engineering wiki: durable decisions, security policy, architecture patterns.
- Future-work/backlog pages: non-blocking audit observations and deferred scope.

## Status Language

Use concrete status terms:

- `In Progress`
- `Ready for Claude Review`
- `Claude Signed Off`
- `Ready to Merge`
- `Merged`
- `Blocked`
- `Deferred / Future Work`

Include exact dates for relative statuses when useful.

## What to Record

- Branch and PR number when available.
- Test command and result summary.
- Claude/Gemini verdict if supplied.
- Human decisions that resolved blockers.
- Future work that should not be implemented in the current story.

## What to Avoid

- Do not paste raw secrets, raw VINs, private tokens, or full logs.
- Do not overquote third-party or generated research when a summary is enough.
- Do not mark a task complete if tests failed or sign-off is still pending.
- Do not delete child pages or databases unless the user explicitly confirms.

## Comment Pattern

For a page-level comment:

```text
US-006 update: Claude signed off on the implementation. PR #NN includes schema, adapter, replay, alert serialization, docs, and regression evidence. Future work remains deferred to US-007.
```
