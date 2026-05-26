# AI Artifact Policy

AutoPulse intentionally documents its multi-agent SDLC, but not every AI-related file belongs in the public repository.

## Public Repository Artifacts

Keep these artifacts public when they are sanitized and useful to contributors:

- `AGENTS.md`: repository governance, role ownership, merge gates, and operating rules.
- `CONTEXT.md`: durable public project status, decisions, constraints, and verification summaries.
- `docs/prompts/`: curated reusable prompts that do not depend on private workspaces or local state.
- `docs/codex-skills/`: reviewable source copies for reusable Codex skills.
- `docs/qa/`, `docs/specs/`, and Starlight docs: durable specifications, QA plans, and public implementation references.

Public AI artifacts should explain process and decisions without exposing private workspace URLs, transient local state, raw chat logs, credentials, or personal operational notes.

## Local-Only Artifacts

Keep these out of git:

- `.antigravitycli/`, `.codex/`, `.claude/`, `.gemini/`, and other agent runtime directories.
- Active local memories or installed skills under a user home directory.
- Scratch prompts, one-off handoffs, copied chat transcripts, and quota or tool-state notes.
- Private Notion/Jira/Linear URLs, workspace IDs, API tokens, local environment details, and machine-specific files.
- Generated browser automation reports and traces unless a maintainer explicitly asks for a small fixture.

Use `LOCAL_CONTEXT.md` or `docs/prompts/local/` for private continuation notes that should not be committed.

## Split Rule

Default to public when an artifact is durable, sanitized, and useful to future contributors. Default to local-only when it contains private links, live task coordination, local branch state, raw transcripts, or tool/session state.

If a local-only artifact contains a durable decision, extract the decision into `CONTEXT.md`, `docs/specs/`, `docs/qa/`, or public Starlight docs in a sanitized form.
