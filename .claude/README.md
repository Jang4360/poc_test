# Claude Adapter

Generated from `.ai/ADAPTERS/claude/` and `.ai/SKILLS/`.

## Purpose

- Provide Claude Code with repo-shared hooks and skill layout.
- Keep hooks minimal and tied only to actively used safeguards.
- Keep stage ownership host-neutral so Claude can implement, review, validate, or receive handoffs without special-case workflow rules.

## Generated files

- `.claude/settings.json`
- `.claude/skills/`

## Non-generated file

- `.claude/settings.local.json` is intentionally local-only and must not be committed.
