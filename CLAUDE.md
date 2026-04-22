# CLAUDE.md

Use this repository as a structured AI harness, not as a loose prompt sandbox.

## Canonical sources

- Read `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, and `.ai/WORKFLOW.md` before major changes.
- Treat `.ai/` as canonical.
- Treat `.claude/skills/` as generated adapter output.
- Treat `.claude/settings.json` as generated from `.ai/ADAPTERS/claude/settings.json`.
- Use `.ai/PLANS/progress.json` and `.ai/EVALS/metrics.json` when summarizing status.

## Skills

- Claude-compatible skills live under `.claude/skills/`.
- Update `.ai/SKILLS/` first, then run `scripts/sync-adapters.sh`.
- Prefer the stage-appropriate skill instead of improvising a new workflow mid-task.
- Use the `dashboard` skill or `scripts/dashboard.sh` for visible status.

## Workflow discipline

- Move work through Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect.
- Claude may plan, build, review, QA, or ship locally; cross-host handoff is optional, not required.
- Write durable artifacts back to `.ai/` when the work changes scope, architecture, risk, release readiness, or learnings.
- If a result should survive the session, store it in `.ai/MEMORY/`, `.ai/EVALS/`, `.ai/PLANS/`, or `.ai/DECISIONS/`.
- Promotion decisions should follow `.ai/PROMOTION.md`.

## Expected checks

- Run `scripts/verify.sh` after structural changes.
- Run `scripts/sync-adapters.sh` after canonical skill changes.
- Run `scripts/update-progress.sh` after changing item statuses in `progress.json`.
- Run `scripts/update-metrics.sh` after retry, promotion, or blocker state changes.
- Use `start` when the request should include implementation plus validation in one pass.
- Use `check` as the default validation gate for an existing change, whether Claude validates locally or receives a handoff via `scripts/review-brief.sh`.
- Use `review`, `qa`, or `qa-only` directly only when a narrower one-stage report is explicitly what the user wants.
- Treat `scripts/record-retry.sh` as the default retry logger. It now auto-checks the circuit breaker and should trigger a `learn` handoff when it exits with an open circuit.
- Use `scripts/smoke.sh` after project-specific commands are configured.
- Use the guard scripts before enabling runtime hooks for command execution or repeated retries.
