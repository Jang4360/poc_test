# Adapters

This directory is the canonical source for generated runtime-specific adapter files.

## Rule

- Keep runtime-independent methodology in the rest of `.ai/`.
- Keep only minimal runtime-specific layout or hook templates here.
- Generate `.claude/`, `.agents/`, and `.codex/` from this directory plus `.ai/SKILLS/`.
- Do not hand-edit generated adapter outputs unless debugging the generator.

## Host mapping

- Claude reads `CLAUDE.md`, `.claude/settings.json`, and `.claude/skills/`.
- Codex reads `AGENTS.md`, `.agents/skills/`, and repo-local `.codex/` placeholders.
- Host ownership is not fixed by policy. The same host may plan, build, review, validate, and ship, or a handoff may happen through durable artifacts such as `scripts/review-brief.sh`.
- The canonical workflow lives in `.ai/`; adapters only expose it to different runtimes.
