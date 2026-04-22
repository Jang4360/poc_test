# Contributing

## Goal

Keep this repository useful as a generic, vendor-neutral AI harness template.

## Principles

- Favor reusable workflow patterns over tool-specific hacks.
- Keep `.ai/` canonical.
- Keep generated adapters rebuildable.
- Avoid over-design. This template should still be easy to clone and start from directly.

## Making changes

1. Update canonical docs or skills first.
2. Sync adapters if `.ai/SKILLS/` changed.
3. Run verification.
4. Document any methodology change in the relevant `.ai/` artifact.

## Adding or changing a skill

1. Edit or add `.ai/SKILLS/<skill-name>/SKILL.md`.
2. Make sure the skill contains all required sections.
3. Add deterministic helper scripts only when they materially reduce ambiguity.
4. Run `scripts/sync-adapters.sh`.
5. Run `scripts/verify.sh`.

## Changing methodology

- Update `.ai/WORKFLOW.md` if stage contracts change.
- Update `.ai/EVALS/` if quality gates change.
- Update `.ai/MEMORY/` or `.ai/DECISIONS/` if the change should persist as policy or learning.

## Release expectations

- Do not merge template changes that leave canonical and generated skills out of sync.
- Keep placeholders safe and clearly marked only where teams must supply project-specific commands.
