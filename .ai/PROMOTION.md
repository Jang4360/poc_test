# Promotion

## Purpose

Route repeated patterns into the right canonical asset instead of leaving them in chat history.

## Routing rules

- One-off issue: usually do not promote
- Repeated mistake or debugging lesson: promote to `.ai/MEMORY/`
- Repeated procedure or workflow: promote to `.ai/SKILLS/`
- Repeated quality gap or completion ambiguity: promote to `.ai/EVALS/` or `.ai/WORKFLOW.md`
- Architecture-level decision or durable tradeoff: promote to `.ai/DECISIONS/`

## Logging

- Record promotion events in `.ai/EVALS/promotion-log.jsonl`
- Use short fields that are easy to count later: `timestamp`, `source`, `destination`, `reason`, `artifact`

## Operating rule

Promotion should compress repeated failure into clearer structure. If the pattern is not recurring or durable, do not promote it.
