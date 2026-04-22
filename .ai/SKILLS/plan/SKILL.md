---
name: plan
description: Build the sprint index and workstream subplans from versioned docs, architectural context, decisions, and stack readiness.
---

# plan

## purpose

Turn durable specs and repository context into executable workstream plans with explicit success criteria and validation paths.

## when to use

- After a spec packet already exists
- When the team wants a planning-only command separate from spec authoring
- When implementation and validation need workstream-level plans instead of one giant checklist

## inputs

- Latest relevant files under `docs/PRD/`, `docs/ERD/`, and `docs/API/`
- Other relevant `docs/` files when they constrain the work
- `.ai/PROJECT.md`
- `.ai/ARCHITECTURE.md`
- `.ai/WORKFLOW.md`
- `.ai/DECISIONS/`
- Current backlog, roadmap, incidents, or runbooks when relevant

## procedure

1. Read the latest relevant versions in `docs/PRD/`, `docs/ERD/`, and `docs/API/` first.
2. Read `.ai/DECISIONS/` plus canonical `.ai/` context before splitting implementation.
3. Classify the request as spec-driven or change-driven.
4. Detect whether a usable application framework is already configured in the repository.
5. If framework setup is missing, include a separate setup workstream before feature work.
6. Build `.ai/PLANS/current-sprint.md` as the sprint index with explicit success criteria, workstream links, and stage checklists.
7. Build `.ai/PLANS/current-sprint/*.md` subplans with `Success Criteria`, `Implementation Plan`, and `Validation Plan`.
8. Use `scripts/scaffold-plan.sh` when it helps bootstrap or refresh the sprint index and subplans.

## outputs

- Updated sprint index under `.ai/PLANS/current-sprint.md`
- Workstream-level plan files under `.ai/PLANS/current-sprint/`
- Explicit framework setup workstream when the repository is not ready to implement the request yet

## escalation rules

- Escalate if the docs disagree on the intended behavior or contracts.
- Escalate if framework choice is still undecided and blocks realistic planning.

## handoff rules

- Hand off to `start`, `implement-feature`, or `fix-bug` with the sprint index and subplans as the execution brief.
- Hand off back to `docs` if planning reveals missing product, data, or API specs.
