# AGENTS.md

## Mission

Use this repository as a disciplined AI harness template for real software delivery. Favor durable project artifacts over chat-only conclusions.

## Hard rules

- `.ai/` is the canonical source of truth.
- `.ai/ADAPTERS/` is the canonical source for generated runtime adapter files.
- Do not edit `.claude/skills/` or `.agents/skills/` by hand unless you are debugging the sync process.
- Do not commit `.claude/settings.local.json`.
- For Codex implementation sessions, treat `AGENTS.md` and `.agents/skills/` as the primary enforcement surface. `.codex/hooks.json` is only a minimal advisory adapter.
- Do not hard-code stage ownership to a single AI vendor or model. Plan, build, review, QA, and ship stages may run in the same host or be handed across hosts as long as canonical artifacts and guard rules stay intact.
- When a skill changes, update `.ai/SKILLS/` first and then run `scripts/sync-adapters.sh`.
- Keep markdown additive, parse-friendly, and easy to diff.
- Prefer explicit assumptions, failure modes, and acceptance criteria over vague guidance.
- Store reusable learnings in `.ai/MEMORY/`, `.ai/EVALS/`, or `.ai/DECISIONS/` instead of leaving them implicit in a thread.
- Treat `.ai/PLANS/progress.json` and `.ai/EVALS/metrics.json` as machine-readable sources for progress and quality state.
- Run the guard scripts before wiring automation that can edit code, execute shell commands, or retry repeatedly.

## Repository usage expectations

- Start new work by reading `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, and `.ai/WORKFLOW.md`.
- Use the sprint loop: Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect.
- Planning outputs should be durable enough that build and QA can consume them without re-interpreting the original request.
- Prefer `start` when you want one entrypoint that carries implementation through validation instead of stopping at a raw diff.
- Prefer `check` as the default validation entrypoint. Use `review`, `qa`, or `qa-only` directly only when a narrower report is intentionally needed.
- If a change alters architecture, document the delta in `.ai/ARCHITECTURE.md` or add an ADR.
- If a failure repeats, capture it in `.ai/MEMORY/` or `.ai/EVALS/failure-patterns.md`.
- If a procedure repeats, consider promoting it into a skill.
- If completion ambiguity repeats, tighten `.ai/EVALS/` or `.ai/WORKFLOW.md`.

## Required checks

- Run `scripts/sync-adapters.sh` after changing any canonical skill.
- Run `scripts/verify.sh` before finalizing structural or documentation changes.
- Run `scripts/update-progress.sh` after changing item statuses in `progress.json` to keep summary counts in sync.
- Run `scripts/update-metrics.sh` after retry, promotion, blocker, or readiness state changes.
- At the start of a Codex implementation session, run `scripts/codex-preflight.sh` if the host hook did not show it automatically.
- Before a mutating shell command, run `scripts/check-dangerous-command.sh "<command>"`.
- Before editing production implementation files, run `scripts/check-tdd-guard.sh --mode pre <candidate paths>`.
- After a failed attempt that may repeat, run `scripts/record-retry.sh <signature>`. It refreshes metrics and automatically opens the circuit breaker when the retry threshold is hit. Use `scripts/check-circuit-breaker.sh <signature>` directly only for preflight checks or external automation.
- Run `scripts/smoke.sh` once project-specific smoke commands are customized.
- Run `scripts/dashboard.sh` when you need a visible summary of progress, risk, and harness health.
- When validation moves to another AI host, run `scripts/review-brief.sh` and hand off that summary with the diff. Same-host review through `check` is also valid.
- Update relevant runbooks when build, release, rollback, or local setup expectations change.

## Done criteria

A change is not done until all of the following are true:

- The relevant `.ai/` artifacts were updated.
- Adapter skills were regenerated if canonical skills changed.
- The requested stage handoff is documented.
- Required checks passed or an explicit blocker is recorded.
- `.ai/EVALS/done-criteria.md` still matches the current workflow.
- Structured progress and metrics artifacts still reflect reality.

## Skill usage

- Use canonical skills in `.ai/SKILLS/` as the design source.
- Use adapter skills only as host-specific entrypoints.
- Prefer extending an existing skill when the workflow belongs to an existing stage.
- Prefer orchestration skills such as `autoplan`, `start`, and `check` when the task should span multiple stages without relying on chat memory.
- Treat `review`, `qa`, and `qa-only` as supporting skills for narrower checks; the default validation route is still `check`.
- Add a new skill only when the task shape is recurring and meaningfully distinct.
- Dashboard and promotion behavior should read canonical artifacts instead of inventing parallel state.

## Skill extension checklist

1. Define the stage and handoff.
2. Define required inputs and durable outputs.
3. Add or update the canonical skill under `.ai/SKILLS/`.
4. Sync adapters.
5. Verify the repository.
