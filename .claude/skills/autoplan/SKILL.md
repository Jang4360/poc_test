---
name: autoplan
description: Run a full planning pass by consolidating problem framing, product scope review, engineering review, and design review into one reusable sprint artifact.
---

# autoplan

## purpose

Produce a complete spec-plus-plan packet without skipping the Think or Plan stages.

## when to use

- When a new task needs a full reviewed plan
- When a new task may need missing PRD, ERD, or API specs before planning can be trusted
- When the team wants one command-shaped planning entrypoint
- When downstream build and QA need structured artifacts immediately

## inputs

- Raw task request
- Latest relevant files under `docs/PRD/`, `docs/ERD/`, and `docs/API/` when they exist
- `.ai/PROJECT.md`
- `.ai/ARCHITECTURE.md`
- `.ai/WORKFLOW.md`
- `.ai/DECISIONS/`

## procedure

1. Classify the request before planning:
   - Spec-driven when the needed behavior is already described in `docs/` or another durable artifact.
   - Change-driven when the request proposes a new feature, change, or fix that must be translated into a plan from the request plus existing docs and code.
2. Inspect `docs/PRD/`, `docs/ERD/`, and `docs/API/` first. Reuse the latest relevant versions when they exist.
3. If any of the three spec families are missing or clearly stale for the request, run the intent of `docs` first so planning has durable source files.
4. Run the intent of `office-hours`.
5. Run the intent of `plan-ceo`.
6. Run the intent of `plan-eng`.
7. Run the intent of `plan-design` when the work is user-facing.
8. Run the intent of `plan` to build the sprint index and subplans from the resulting docs plus `.ai/DECISIONS/`.
9. Consolidate the approved result in `.ai/PLANS/current-sprint.md` as a checklist-based sprint index. The sprint index must contain, in order: `## Goal`, `## Success Criteria`, `## Workstream Index`, then the stage sections (`## Think` through `## Reflect`), and `## Risks and Open Questions`.
10. In `## Success Criteria`, write measurable and verifiable completion conditions, not process steps. Each criterion must be observable by review or QA without re-reading the original chat.
11. In `## Workstream Index`, list each subplan file as `- [ ] [filename.md](relative-path) — one-line workstream goal`. Replace any `TODO` placeholder descriptions with the real goal after planning reviews are complete.
12. If the repository lacks a usable app framework for the request, include framework setup as its own workstream instead of hiding it inside implementation.
13. Use `scripts/scaffold-specs.sh` and `scripts/scaffold-plan.sh` when they help bootstrap or refresh the durable artifacts.
14. Use checklist markers consistently in the sprint artifact: `[ ]` not started, `[~]` in progress, `[x]` completed successfully, `[!]` failed or blocked.

## outputs

- Versioned spec packet under `docs/PRD/`, `docs/ERD/`, and `docs/API/` when needed
- Single reviewed sprint index
- Explicit scope, architecture, risk, and UX expectations
- Workstream-level subplans that implementers and validators can execute independently

## escalation rules

- Escalate if the request is too ambiguous to survive a combined planning pass.
- Escalate if the plan reveals unresolved product ownership or technical feasibility questions.

## handoff rules

- Hand off to `implement-feature`, `fix-bug`, or another build skill with the consolidated plan as the brief.
