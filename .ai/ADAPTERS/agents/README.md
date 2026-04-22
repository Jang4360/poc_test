# Codex Skills Adapter

Generated from `.ai/SKILLS/`.

## Purpose

- Expose repository skills to Codex through `.agents/skills/`.
- Keep `.agents/` focused on skill discovery, because Codex already reads root `AGENTS.md`.
- Keep stage ownership in the canonical skills instead of assuming Codex is build-only.

## Note

Per OpenAI Codex docs, Codex scans `.agents/skills` from the current working directory up to the repository root. Root-level skills in this repository are intended to be available everywhere in the repo.
