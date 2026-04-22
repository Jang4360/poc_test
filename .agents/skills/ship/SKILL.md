---
name: ship
description: Verify readiness gates, confirm docs and tests are aligned, and prepare the change to land safely.
---

# ship

## purpose

Provide a disciplined release gate before code is merged or deployed.

## when to use

- After review and QA
- When the team believes a change is ready to release

## inputs

- `.ai/PLANS/current-sprint.md`
- `.ai/EVALS/done-criteria.md`
- `.ai/EVALS/smoke-checklist.md`
- `.ai/RUNBOOKS/release.md`
- `.ai/RUNBOOKS/rollback.md`

## procedure

1. Confirm the requested scope is complete enough to ship.
2. Verify review, QA, benchmark, and security outcomes are visible.
3. Confirm release and rollback readiness.
4. Record release status and any accepted risks in the sprint artifact.
5. Update release documentation if behavior or operations changed.

## outputs

- Ship readiness decision
- Accepted-risk list
- Release artifact updates

## escalation rules

- Escalate if rollback is missing or implausible.
- Escalate if unresolved high-severity review or QA findings remain.

## handoff rules

- Hand off to `deploy-check` or actual release execution once readiness is green.
- Hand off to `document-release` when docs lag behind shipped behavior.
