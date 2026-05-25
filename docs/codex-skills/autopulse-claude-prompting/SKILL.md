---
name: autopulse-claude-prompting
description: Use when creating prompts for Claude Chat or Claude Code to audit AutoPulse work, review implementation files, generate adversarial QA plans, sign off on stories, or re-review fixes after Codex changes.
metadata:
  short-description: Prompt Claude for AutoPulse audits
---

# AutoPulse Claude Prompting

Use this skill when preparing Claude review or audit prompts for AutoPulse.

## Prompt Structure

1. Role: name Claude as Lead Auditor and state the story/stage.
2. Scope: say whether this is pre-implementation, implementation audit, follow-up, or final sign-off.
3. Authoritative context: summarize the project, constraints, and decisions in plain language.
4. Review targets: list files, modules, or behaviors to inspect. If Claude Chat lacks repo access, summarize contents instead of using private URLs.
5. Security red lines: state read-only OBD-II/UDS constraints and data privacy rules.
6. Required output: pass/fail verdict, blockers, non-blocking recommendations, test gaps, and explicit sign-off status.

## Context Rules

- Do not assume Claude Chat can access GitHub, Notion, or local files.
- Include enough context for a standalone review.
- Avoid dumping huge diffs when a file/function summary plus targeted snippets will do.
- Use exact branch/PR names when Claude Code has repo access.

## Ask for Actionable Findings

Request:

- Severity-ranked blockers.
- File/function-specific concerns.
- Missing adversarial tests.
- Regression risks.
- Clear “approved for merge” or “not approved” language.

## Follow-Up Prompt Pattern

```text
You previously raised these findings: ...
Codex changed: ...
Verification run: ...
Please re-review only the changed areas unless you see a cross-cutting risk.
Return PASS/FAIL, blockers, and non-blocking recommendations.
```
