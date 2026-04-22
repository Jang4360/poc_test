---
name: office-hours
description: Turn a vague idea into a sharper problem definition, wedge, target user, and non-goals before planning starts.
---

# office-hours

## purpose

Convert a loose product request into a reusable framing artifact that planning skills can pressure-test.

## when to use

- At the start of a new feature, product bet, workflow, or repo-level initiative
- When the request is still framed as a solution instead of a problem
- When the team needs a clearer wedge before architecture or UI discussion
- When the repository may need spec files before planning can proceed cleanly

## inputs

- The raw request, idea, or opportunity
- Latest relevant files under `docs/PRD/`, `docs/ERD/`, and `docs/API/` when they exist
- `.ai/PROJECT.md`
- `.ai/WORKFLOW.md`
- Current backlog or sprint context from `.ai/PLANS/`

## procedure

1. Restate the request in plain language and separate problem, user, and proposed solution.
2. Challenge ambiguity until the target user, pain, trigger moment, and narrowest useful wedge are explicit.
3. Identify what is out of scope for this sprint.
4. If `docs/PRD/`, `docs/ERD/`, or `docs/API/` are missing for the request, hand off to `docs` before relying on implementation guesses.
5. If specs exist, identify the most relevant versions and record them as planning inputs before relying on implementation guesses.
6. Update `.ai/PLANS/current-sprint.md` with a durable problem framing section, explicit success criteria, and the first-pass workstream split.
7. If the request is broad or still only exists as chat, prefer bootstrapping `.ai/PLANS/current-sprint.md` plus `.ai/PLANS/current-sprint/*.md` with `scripts/scaffold-plan.sh` before deeper review.
8. Move any deferred work into `.ai/PLANS/backlog.md` if it matters later.

## outputs

- Sharpened problem statement
- Clear user and wedge
- Non-goals
- Updated sprint framing artifact with initial success criteria and workstream boundaries

## escalation rules

- Escalate if the request depends on unclear business goals, owner decisions, or conflicting target users.
- Escalate if the problem cannot be stated without assuming an implementation.

## handoff rules

- Hand off to `plan-ceo` when scope or product ambition needs pressure.
- Hand off to `plan-eng` once the problem is concrete enough to design a buildable solution.
- Hand off to `docs` when the repository still lacks durable PRD, ERD, or API context.
