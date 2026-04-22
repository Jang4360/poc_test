---
name: dashboard
description: Open a visual dashboard from plan checklists and core risk or health signals.
---

# dashboard

## purpose

Make repository progress and harness quality state visible without relying on chat memory.

## when to use

- When you need an immediate status view of work, risk, and harness health
- Before ship or retro
- When deciding what to do next

## inputs

- `.ai/PLANS/progress.json`
- `.ai/EVALS/metrics.json`
- `.ai/EVALS/promotion-log.jsonl`
- `.ai/PLANS/current-sprint.md`

## procedure

1. Run `scripts/dashboard.sh` so the dashboard is generated from the current canonical artifacts instead of from chat memory.
2. Treat checklist items in `.ai/PLANS/current-sprint.md` as the primary board data for counts, progress, success, and failure state.
3. Use `.ai/EVALS/metrics.json` and retry or promotion logs as secondary health and risk overlays.
4. If the dashboard reveals stale or missing checklist state, update `.ai/PLANS/current-sprint.md` and re-run `scripts/dashboard.sh` before relying on the summary.

## outputs

- Visual dashboard opened in the browser
- Checklist totals, progress counts, success rate, and failure rate
- Risk list when real risk exists
- Followable next actions

## escalation rules

- Escalate if progress or metrics artifacts are stale or contradictory.
- Escalate if the dashboard exposes blockers with no owner or next step.

## handoff rules

- Hand off to the next stage skill based on the top unresolved risk or next planned item.
