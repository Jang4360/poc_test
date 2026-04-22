---
name: benchmark
description: Capture performance baselines and before-versus-after comparisons so release decisions are not made on intuition alone.
---

# benchmark

## purpose

Measure whether the change introduced unacceptable performance regressions or surprising wins.

## when to use

- For performance-sensitive changes
- Before release when speed or resource usage matters materially

## inputs

- Target flow or endpoint
- Existing performance expectations if they exist
- Relevant build or QA notes

## procedure

1. Define what should be measured and why it matters.
2. Capture a baseline if one exists or note that none exists.
3. Measure the changed path and compare results.
4. Record significant regressions or gains in `.ai/PLANS/current-sprint.md` and `.ai/EVALS/scorecard.md`.

## outputs

- Benchmark summary
- Before-versus-after comparison
- Performance risk note when relevant

## escalation rules

- Escalate if the team lacks a credible way to measure the critical path.
- Escalate if regressions are large enough to change release readiness.

## handoff rules

- Hand off to `ship` with explicit performance status.
- Hand off to `refactor-module` or implementation work if regressions must be fixed first.
