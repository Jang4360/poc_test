---
name: learn
description: Turn recurring patterns, failures, and team preferences into durable repository memory, evaluation rules, skill upgrades, or ADR follow-ups.
---

# learn

## purpose

Make the repository smarter over time by capturing what repeats.

## when to use

- After retro
- After recurring bugs, review findings, QA failures, or operational surprises
- When a new convention or policy should persist
- When `scripts/record-retry.sh` opens the circuit breaker during an active `start` or `check` pass — run immediately in the same session, not as a deferred follow-up
- When `scripts/dashboard.sh` surfaces a circuit breaker hot cluster (>=3 repeated failures in 24h) outside an active delivery pass

## inputs

- Retro notes or failure context
- Circuit breaker output: signature and count from `scripts/record-retry.sh` (inline trigger), `scripts/dashboard.sh`, or `scripts/check-circuit-breaker.sh`
- Incident, debugging, and scorecard context
- Existing memory and evaluation files

## procedure

1. Identify what pattern is worth preserving. Check `retry-log.jsonl` for the failure signature if coming from a circuit breaker trigger.
2. Apply the promotion routing rule:
   - Repeated mistake or debugging lesson → `.ai/MEMORY/debugging.md` or `.ai/MEMORY/incidents.md`
   - Repeated procedure or workflow → `.ai/SKILLS/` (new or updated skill)
   - Repeated quality gap or completion ambiguity → `.ai/EVALS/failure-patterns.md` or `.ai/WORKFLOW.md`
   - Architecture-level decision → `.ai/DECISIONS/` as an ADR
3. Update the chosen artifact with concise, reusable guidance.
4. Call `scripts/record-promotion.sh <destination> <reason> <artifact>` to log the event.
5. If the workflow itself should change, note the required skill or runbook update.

## outputs

- Durable learning captured in the right canonical file
- Promotion event logged in `.ai/EVALS/promotion-log.jsonl`
- Follow-up list for methodology improvements when needed

## escalation rules

- Escalate if the pattern implies a governance or product decision beyond the repository.
- Escalate if the team cannot agree whether the lesson is local, temporary, or policy-level.

## handoff rules

- Hand off to future sprints through updated `.ai/` artifacts.
- Hand off to skill maintenance when the lesson should change workflow behavior.
