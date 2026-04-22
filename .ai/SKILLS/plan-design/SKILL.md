---
name: plan-design
description: Force interaction states, information hierarchy, and anti-generic UI thinking into the plan before implementation begins.
---

# plan-design

## purpose

Prevent product plans from collapsing into generic UI or missing important user states.

## when to use

- For any user-facing flow
- When interaction states, copy, or layout hierarchy are still vague
- Before implementing a new UI or meaningful UX change

## inputs

- `.ai/PLANS/current-sprint.md`
- `.ai/PROJECT.md`
- Any design constraints already captured in memory or ADRs

## procedure

1. Review the user flow and identify primary, empty, loading, error, and success states.
2. Check the information hierarchy and whether the interface expresses a clear product opinion.
3. Reject generic UI patterns that do not reinforce the wedge or user goal.
4. Add design review notes and required states to `.ai/PLANS/current-sprint.md`.
5. Capture reusable design principles in `.ai/MEMORY/conventions.md` if they should persist.

## outputs

- Required interaction state list
- Information hierarchy critique
- Anti-generic UI guidance
- Updated sprint plan with UI expectations

## escalation rules

- Escalate if critical UX decisions require product or brand approval.
- Escalate if the requested interface conflicts with the stated wedge or target user.

## handoff rules

- Hand off to build skills once the UI states are explicit.
- Hand off to `design-review` after implementation for a live audit.
