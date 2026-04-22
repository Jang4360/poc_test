# Architecture

## Canonical layers

- `.ai/` is the methodology and project-operations layer.
- `docs/PRD/`, `docs/ERD/`, and `docs/API/` are the durable product-spec layer.
- `.ai/SKILLS/` is the canonical workflow layer.
- `.ai/ADAPTERS/` is the canonical runtime-adapter template layer.
- `.ai/PLANS/current-sprint.md` is the sprint index layer.
- `.ai/PLANS/current-sprint/` is the workstream-plan layer.
- `.ai/PLANS/progress.json` is the canonical structured progress layer.
- `.ai/EVALS/metrics.json` plus promotion and retry logs are the canonical measurable state layer.
- `.ai/GUARDS.md`, `.ai/PROMOTION.md`, and `.ai/AUTOMATION.md` define harness control behavior.
- `.claude/skills/` is the Claude adapter layer generated from canonical skills.
- `.agents/skills/` is the Codex adapter layer generated from canonical skills.
- `.codex/` holds repo-local Codex configuration placeholders.
- `scripts/` holds deterministic repository helpers for sync, verification, spec scaffolding, plan scaffolding, smoke checks, guards, scoring, dashboard views, stack detection, and bootstrap.

## Repository map

- Use the root `README.md` for template value, recommended flow, and skill usage examples.
- Use `AGENTS.md` and `CLAUDE.md` for host instruction surfaces.
- Use `.ai/PROJECT.md`, `.ai/WORKFLOW.md`, and `.ai/ARCHITECTURE.md` for methodology and control-plane design.
- Use `.ai/ADAPTERS/README.md` for generated adapter behavior and host-specific file mapping.
- Use `.ai/SKILLS/` for canonical skills; generated `.claude/skills/` and `.agents/skills/` are rebuildable views.

## Design intent

This template keeps one source of truth and three generated compatibility surfaces. It does not split the repository into a syncable core and a separate scaffold. The repository itself is the scaffold.

Host roles are runtime choices, not methodology. The same AI host may plan, implement, review, and QA a change, or the work may be handed across hosts, as long as the durable artifacts and guard scripts remain the control plane.

## Data flow

1. A request or event is classified against the current sprint and workflow.
2. Humans or agents update canonical docs and canonical skills under `.ai/`.
3. Spec authoring updates versioned files under `docs/PRD/`, `docs/ERD/`, and `docs/API/`, then planning updates the sprint index plus workstream subplans, and implementation updates those artifacts as reality changes.
4. Evaluation and release update `.ai/EVALS/metrics.json` and related logs.
5. Promotion decisions update `.ai/MEMORY/`, `.ai/SKILLS/`, `.ai/EVALS/`, or `.ai/DECISIONS/`.
6. `scripts/sync-adapters.sh` copies canonical skills and adapter templates into `.claude/`, `.agents/`, and `.codex/`.
7. Any supported host uses its generated adapter surface plus the canonical `.ai/` artifacts for stage behavior.
8. Validation may run in the same host as implementation or in another host using a generated handoff brief.
9. `scripts/dashboard.sh` turns canonical progress, metrics, and promotion state into a visible status summary.

## Change policy

- Change canonical skill behavior only under `.ai/SKILLS/`.
- Change host instructions in `AGENTS.md` and `CLAUDE.md`.
- Add new deterministic scripts only when markdown instructions are not enough.
