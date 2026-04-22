---
name: retro
description: Close the sprint loop by summarizing what worked, what broke, what slowed the team down, and what should change in the harness.
---

# retro

## purpose

Convert a completed sprint or release into actionable process improvements.

## when to use

- At the end of a sprint, milestone, or release
- After a meaningful failure or repeated friction pattern

## inputs

- Sprint artifact
- Review, QA, release, and incident outcomes
- Scorecard and failure-pattern notes

## procedure

1. Summarize the intended work versus what actually shipped.
2. Identify the best decisions, biggest misses, and recurring sources of friction.
3. Propose concrete updates to memory, evals, runbooks, ADRs, or skills.
4. Record the retro summary in `.ai/PLANS/current-sprint.md` or archive it into the relevant durable files.

## outputs

- Sprint retrospective
- Process improvements
- Candidate updates for memory, evals, skills, or ADRs

## escalation rules

- Escalate if the retro reveals unresolved systemic ownership or reliability issues.
- Escalate if repeated incidents are not being converted into repository policy.

## handoff rules

- Hand off to `learn` to capture the recurring patterns durably.
