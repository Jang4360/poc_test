---
name: security-review
description: Review changes for trust boundaries, auth, secrets handling, data exposure, and exploit-shaped failure modes before release.
---

# security-review

## purpose

Make security and trust boundary review a normal stage artifact instead of a late surprise.

## when to use

- For changes touching auth, permissions, secrets, user data, or external integrations
- Before shipping risk-sensitive functionality

## inputs

- Current change and plan
- `.ai/ARCHITECTURE.md`
- Incident history if relevant

## procedure

1. Identify the trust boundaries and sensitive assets involved.
2. Review auth, authorization, secret handling, logging, and data movement risks.
3. Record findings and mitigations in `.ai/PLANS/current-sprint.md`.
4. Update runbooks or memory if the review changes operational practice.

## outputs

- Security findings
- Mitigation list
- Updated trust-boundary notes when needed

## escalation rules

- Escalate immediately on confirmed data exposure or privilege escalation risk.
- Escalate if the release depends on a control that does not exist yet.

## handoff rules

- Hand off to `ship` only after critical security findings are resolved or explicitly accepted.
