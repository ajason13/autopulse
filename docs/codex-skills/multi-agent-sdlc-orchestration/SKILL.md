---
name: multi-agent-sdlc-orchestration
description: Use for project-agnostic coordination of multi-agent software delivery where separate LLMs or tools own architecture, implementation, audit, documentation, and release decisions.
metadata:
  short-description: Orchestrate multi-agent SDLC
---

# Multi-Agent SDLC Orchestration

Use this skill for any project using multiple AI agents with bounded roles.

## Define Roles First

For each agent/tool, clarify:

- Ownership area.
- Inputs it requires.
- Outputs it must produce.
- Merge or release authority.
- What it must not do.

Common split:

- Architect: research, scope, design, acceptance criteria.
- Developer: implementation, local verification, CI, repo hygiene.
- Auditor: adversarial tests, edge cases, regression review, sign-off.
- Coordinator: project memory, task tracking, handoffs, release notes.

## Handoff Contract

Each handoff should include:

- Objective.
- Current branch or artifact state.
- Authoritative context.
- Constraints and non-goals.
- Acceptance criteria.
- Required verification.
- Expected output format.

Avoid handoffs that rely on private links unless the receiving agent has access.

## Decision Discipline

- Separate “what/why” decisions from “how” implementation.
- Record human decisions that resolve blockers.
- Treat tests and audit findings as gates, not suggestions.
- Keep future work distinct from current scope.

## Completion Checklist

- Implementation matches approved scope.
- Tests pass and evidence is recorded.
- Audit status is explicit.
- Docs/project memory are updated.
- PR/release notes explain risk and verification.
