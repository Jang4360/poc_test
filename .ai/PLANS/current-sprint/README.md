# Current Sprint Subplans

Use this directory for workstream-level plan files that hang off `.ai/PLANS/current-sprint.md`.

## Rule

- `current-sprint.md` is the sprint index and top-level checklist.
- Each meaningful workstream should get its own markdown file in this directory.
- Prefer one file per domain, API surface, UI slice, job, or operational concern instead of one giant implementation plan.
- Every subplan should contain explicit `Success Criteria`, `Implementation Plan`, and `Validation Plan` sections.
- `scripts/scaffold-plan.sh` can generate the sprint index and a first pass of workstream files before reviews refine them.
- If a request is driven by an existing spec, cite the spec files under `Source Inputs`.
- If a request is primarily command-driven or change-driven, restate the requested change and derive the subplans from impacted domains or interfaces.

## Suggested naming

- `auth-api.md`
- `billing-ui.md`
- `admin-reporting.md`
- `release-safety.md`
- `docs-alignment.md`
