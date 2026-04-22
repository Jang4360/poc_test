---
name: docs
description: Ensure versioned PRD, ERD, and API specs exist under docs before detailed planning starts, reusing existing specs when they are already present.
---

# docs

## purpose

Create or update durable product and contract specs under `docs/` so planning does not depend on chat-only intent.

## when to use

- Before planning when `docs/PRD`, `docs/ERD`, or `docs/API` are missing
- When existing specs are stale and a new version should capture changed intent
- When the team wants a spec-only pass before deeper planning

## inputs

- Raw task request
- Existing files under `docs/PRD/`, `docs/ERD/`, and `docs/API/` when they exist
- `.ai/PROJECT.md`
- `.ai/ARCHITECTURE.md`
- `.ai/DECISIONS/`

## procedure

1. Inspect `docs/PRD/`, `docs/ERD/`, and `docs/API/` for existing versioned specs before creating anything new.
2. If all three spec families already exist and remain usable for the request, reuse the latest relevant versions instead of rewriting them.
3. If any family is missing, create it under the correct folder using versioned naming such as `feature_prd_v1.md`, `feature_erd_v1.md`, and `feature_api_v1.md`.
4. If the request changes existing intent materially, create a new version such as `_v2` instead of overwriting the previous file.
5. Capture source request, scope, non-goals, and open questions in the generated or updated spec files.
6. Record stack context so later planning can tell whether framework setup is already present or still needs to be planned.
7. Use `scripts/scaffold-specs.sh` to bootstrap or update the spec packet when a durable file set is missing.

## outputs

- Reused or newly created versioned specs under `docs/PRD/`, `docs/ERD/`, and `docs/API/`
- Explicit product, data, and contract context for planning
- Clear spec version trail instead of silent overwrites

## escalation rules

- Escalate if the request is too ambiguous to produce even draft specs.
- Escalate if the spec update would invalidate important existing contracts and no owner decision is available.

## handoff rules

- Hand off to `office-hours` when the problem framing still needs sharpening.
- Hand off to `plan` or `autoplan` once the spec packet is usable.
