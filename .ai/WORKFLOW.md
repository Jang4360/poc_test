# Workflow

## Sprint loop

The default loop is:

Think -> Plan -> Build -> Review -> Test -> Ship -> Reflect

The automation-oriented execution shape is:

request or event -> classification -> doc and skill loading -> planning -> implementation -> validation -> risk summary -> promotion -> scoring -> dashboard update

## Stage contracts

### Think

- Primary skills: `docs`, `office-hours`
- Goal: turn vague intent into a sharper problem definition, wedge, user, and non-goals
- Main outputs: versioned PRD, ERD, API docs when needed, plus updated framing in `.ai/PLANS/current-sprint.md`, explicit success criteria, and initial workstream boundaries
- Handoff: planning stages inherit the clarified problem instead of the original loose request

### Plan

- Primary skills: `plan-ceo`, `plan-eng`, `plan-design`, `plan`, `autoplan`
- Goal: challenge scope, architecture, interaction quality, failure modes, trust boundaries, and test strategy before implementation
- Main outputs: reusable checklist-based sprint index sections in `.ai/PLANS/current-sprint.md`, workstream subplans under `.ai/PLANS/current-sprint/`, optional ADR drafts, backlog or roadmap deltas
- Planning helpers: `scripts/scaffold-specs.sh` can bootstrap versioned docs under `docs/PRD`, `docs/ERD`, and `docs/API`, and `scripts/scaffold-plan.sh` can bootstrap or refresh the sprint index and workstream files from those docs plus `.ai/DECISIONS/`
- Handoff: build, review, and QA consume these artifacts directly

### Build

- Primary skills: `start`, `implement-feature`, `fix-bug`, `refactor-module`, `write-test`, `investigate`
- Goal: execute against an approved plan with clear boundaries and evidence
- Main outputs: code changes, happy-path plus failure-path tests, and implementation notes recorded in sprint artifacts when behavior or scope changed
- Handoff: `start` continues directly into validation; pure build skills hand off to `check` so review inherits the approved plan, not just the diff

### Review

- Primary skills: `check`, `design-review`, `security-review`
- Goal: inspect correctness, maintainability, product integrity, and risk
- Main outputs: findings, resolved risks, open questions, and review notes linked from `.ai/PLANS/current-sprint.md`
- Handoff: `check` is the default validation entrypoint and aggregates code review findings plus downstream QA and release risks

### Test

- Primary skills: `check`, `benchmark`
- Goal: verify real user flows, failure cases, and performance expectations
- Main outputs: bug and risk reports, tested exception-path notes, smoke-check references, scorecard updates, regression notes
- Handoff: ship consumes readiness status from `check`, QA, and benchmarks rather than assuming tests passed means production-ready

## Validation rule

- Default validation command: `check`
- Supporting validation sub-skills: `review`, `qa`, `qa-only`, `design-review`, `security-review`, `benchmark`
- Use supporting validation skills directly only when a narrower report is more useful than the combined validation gate

### Ship

- Primary skills: `ship`, `canary`, `deploy-check`, `document-release`
- Goal: verify readiness gates, release safely, and keep release docs aligned
- Main outputs: release checklist status, deployment verification, rollback readiness, release notes
- Handoff: retro consumes what actually happened, not what was intended

### Reflect

- Primary skills: `retro`, `learn`, `dashboard`
- Goal: capture what changed in the team or project system so the next sprint is better
- Main outputs: memory updates, evaluation updates, ADR follow-ups, skill improvements, recurring pattern capture
- Handoff: future work starts with a better repository memory state

## Artifact movement

- Product and contract specs live under `docs/PRD/`, `docs/ERD/`, and `docs/API/`, with versioned filenames such as `_v1`, `_v2`, and so on.
- Product framing and approved plans live in `.ai/PLANS/`.
- `current-sprint.md` should act as the sprint index, containing top-level success criteria, workstream links, and followable checklist items using `[ ]`, `[~]`, `[x]`, and `[!]`.
- `.ai/PLANS/current-sprint/` should contain workstream-level plan files with explicit `Success Criteria`, `Implementation Plan`, and `Validation Plan` sections.
- Planning should read the latest relevant versions in `docs/PRD/`, `docs/ERD/`, and `docs/API/` first, then supporting `docs/` files and `.ai/DECISIONS/`.
- Exception and failure-path expectations live in `.ai/EVALS/exception-checklist.md` and should be pulled into both implementation and validation work.
- Structured task state lives in `.ai/PLANS/progress.json`.
- Quality gates and recurring failure knowledge live in `.ai/EVALS/`.
- Structured quality and readiness metrics live in `.ai/EVALS/metrics.json`.
- Reusable operational and debugging memory lives in `.ai/MEMORY/`.
- Structural decisions live in `.ai/DECISIONS/`.
- Runbooks describe deterministic setup, release, and rollback behavior under `.ai/RUNBOOKS/`.
- Guard and promotion policy live in `.ai/GUARDS.md` and `.ai/PROMOTION.md`.

## Guard rails

- Production edits should pass through the TDD guard before automation is allowed to treat them as ready.
- Shell execution should pass through the dangerous command guard before automation executes high-risk commands.
- Repeated equivalent failures should be logged through `scripts/record-retry.sh`, which refreshes metrics and opens the circuit breaker before more retries are attempted.

## Promotion paths

- One-off issue: leave local unless it is severe.
- Repeated issue: promote to memory.
- Repeated procedure: promote to skill.
- Repeated completion ambiguity: tighten evals or workflow.
- Architecture-level tradeoff: write an ADR.

## Operating rule

If a stage creates output that another stage will need later, store it in `.ai/` instead of leaving it in transient chat context.
