---
name: adversarial-review-handoff
description: Use for project-agnostic prompts and workflows that ask an auditor model to challenge a design, implementation, schema, security boundary, test suite, or release candidate.
metadata:
  short-description: Prepare adversarial review handoffs
---

# Adversarial Review Handoff

Use this skill when preparing work for an auditor or reviewer model.

## Prompt Skeleton

```text
Role: You are the lead auditor for <project/system>.
Stage: <pre-implementation | implementation audit | follow-up | final sign-off>.
Scope: <what to review>.
Context: <standalone summary of relevant architecture and constraints>.
Evidence: <tests, files, diffs, PR, or summarized implementation>.
Output required:
- PASS/FAIL verdict
- Blockers ordered by severity
- Non-blocking recommendations
- Missing tests or edge cases
- Explicit sign-off status
```

## What to Include

- Security, safety, privacy, or compliance boundaries.
- Data contracts and invariants.
- Known decisions and open questions.
- Test evidence and coverage gaps.
- Any areas intentionally out of scope.

## What to Ask the Auditor to Do

- Attack assumptions.
- Identify fail-open behavior.
- Check boundary values and malformed input.
- Look for cross-module regressions.
- Recommend minimal additional tests.
- Distinguish blockers from future work.

## Follow-Up Reviews

When responding to prior findings:

- Quote or summarize each finding.
- State the implemented response.
- List verification commands and results.
- Ask the auditor to re-review only the changed areas plus any cross-cutting risk.
