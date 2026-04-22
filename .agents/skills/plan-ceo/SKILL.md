---
name: plan-ceo
description: Challenge scope, sharpen the product wedge, and decide whether the team is building too little, too much, or the wrong thing.
---

# plan-ceo

## purpose

Pressure-test the plan from a product and scope perspective before code starts.

## when to use

- After `office-hours`
- When a feature is likely under-scoped, over-scoped, or strategically weak
- When a team needs an opinionated product tradeoff before implementation

## inputs

- Current sprint framing from `.ai/PLANS/current-sprint.md`
- Relevant roadmap and backlog context
- `.ai/PROJECT.md`

## procedure

1. Read the current framing and identify the proposed wedge.
2. Ask whether the wedge is strong enough to matter for the target user.
3. Challenge scope with three lenses: stronger wedge, simpler first version, and dangerous distractions.
4. Make success criteria explicit enough that build and validation can tell what counts as a successful outcome.
5. Record the recommended scope position in `.ai/PLANS/current-sprint.md`.
6. Push deferred but relevant work into `.ai/PLANS/backlog.md` or `.ai/PLANS/roadmap.md`.

## outputs

- Scope recommendation
- Product wedge critique
- Explicit non-goals and deferred opportunities
- Updated sprint plan with product rationale and success criteria

## escalation rules

- Escalate if the team cannot agree on the primary user or success metric.
- Escalate if the plan depends on a business decision outside the repository.

## handoff rules

- Hand off to `plan-eng` once scope is acceptable.
- Hand off back to `office-hours` if the problem definition itself is still weak.
