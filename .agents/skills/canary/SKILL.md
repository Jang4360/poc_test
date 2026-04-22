---
name: canary
description: Verify a release in the first moments after deployment by watching the most likely breakpoints and user-critical signals.
---

# canary

## purpose

Catch release issues early before they become a wider incident.

## when to use

- Immediately after deployment
- For risky or user-critical releases

## inputs

- Release context
- Monitoring or log access if available
- Rollback criteria from the runbook

## procedure

1. Identify the fastest indicators of release health.
2. Check the highest-risk paths first.
3. Record observed health, anomalies, and rollback triggers in the sprint artifact or incident log.

## outputs

- Canary status
- Early warning notes
- Rollback recommendation if required

## escalation rules

- Escalate immediately if the primary flow or key health metric degrades.
- Escalate if the canary cannot be observed with enough confidence.

## handoff rules

- Hand off to rollback procedures when release health is unacceptable.
- Hand off to `retro` if the canary uncovered a process gap.
