---
name: deploy-check
description: Confirm deployment prerequisites, environment assumptions, and rollback readiness before pushing a release over the line.
---

# deploy-check

## purpose

Prevent last-mile deployment surprises.

## when to use

- Right before deployment
- When infrastructure, migrations, or environment assumptions are involved

## inputs

- `.ai/RUNBOOKS/release.md`
- `.ai/RUNBOOKS/rollback.md`
- Current sprint artifact

## procedure

1. Verify the target environment, dependencies, and access assumptions.
2. Check whether rollout, migration, or flag dependencies are explicit.
3. Confirm rollback steps are current.
4. Record the deploy check status in `.ai/PLANS/current-sprint.md`.

## outputs

- Deployment readiness note
- List of environment assumptions
- Rollback readiness confirmation or gap

## escalation rules

- Escalate if the deployment path depends on undocumented manual steps.
- Escalate if rollback depends on missing backups, flags, or procedures.

## handoff rules

- Hand off to `ship` or real deployment execution only after readiness is confirmed.
