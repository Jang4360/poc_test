# Codex Runtime Adapter

Generated from `.ai/ADAPTERS/codex/`.

## Purpose

- Keep repo-local Codex configuration explicit but minimal.
- Keep runtime-specific behavior subordinate to canonical `.ai/` assets.
- Use only the smallest hook layer needed for active Codex work, whether Codex is planning, implementing, reviewing, or validating.

## Generated files

- `.codex/config.toml`
- `.codex/hooks.json`
- `scripts/codex-preflight.sh`
- `scripts/codex-review-brief.sh`

## Rule

`AGENTS.md` and `.agents/skills/` are the primary Codex-facing surfaces. `.codex/hooks.json` only triggers a minimal session-start preflight that surfaces guard commands, dashboard state, retry warnings, and validation routing. Tool-level blocking still lives in the guard scripts and host instructions unless a stable Codex hook contract proves otherwise.
