---
name: investigate
description: Run a disciplined investigation to collect evidence, isolate hypotheses, and identify the real fault line before proposing a fix.
---

# investigate

## purpose

Prevent teams from guessing their way through ambiguous failures.

## when to use

- When the root cause is unclear
- When a bug report is noisy or incomplete
- When multiple failed fixes suggest the team is solving the wrong problem

## inputs

- Symptom, report, logs, or reproduction hints
- Relevant debugging memory and incidents
- Architecture notes for the affected area

## procedure

1. State the observed symptom and strongest evidence.
2. Trace the likely path through code, state, or systems.
3. Generate ranked hypotheses and eliminate them with evidence.
4. If repeated failed fixes already exist for the same signature, run `scripts/check-circuit-breaker.sh <signature>` before proposing another brute-force attempt.
5. Record the investigation trail in `.ai/MEMORY/debugging.md` if it is reusable.
6. Recommend the next fix or test action only after the cause is credible.

## outputs

- Investigation summary
- Ranked hypotheses with evidence
- Recommended next action

## escalation rules

- Escalate if production access, logs, or data required for proof are missing.
- Escalate if the investigation exposes a systemic issue beyond a local fix.

## handoff rules

- Hand off to `fix-bug` when the root cause is sufficiently clear.
- Hand off to `security-review` or `incident` tracking when the fault crosses trust boundaries.
