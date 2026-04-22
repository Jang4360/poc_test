#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
usage: scripts/scaffold-plan.sh --mode <spec-driven|change-driven> --goal "<goal>" --request "<request>" [--workstream "<name>"]...

Create or refresh `.ai/PLANS/current-sprint.md` plus workstream subplans under
`.ai/PLANS/current-sprint/`.

Rules:
  - Prefer latest versioned docs under `docs/PRD/`, `docs/ERD/`, and `docs/API/`
  - Read `.ai/DECISIONS/` alongside `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, and `.ai/WORKFLOW.md`
  - If no recognized app framework is configured, add a framework setup workstream
EOF
}

MODE=""
GOAL=""
REQUEST=""
declare -a WORKSTREAMS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --goal)
      GOAL="${2:-}"
      shift 2
      ;;
    --request)
      REQUEST="${2:-}"
      shift 2
      ;;
    --workstream)
      WORKSTREAMS+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$MODE" || -z "$GOAL" || -z "$REQUEST" ]]; then
  usage >&2
  exit 1
fi

if [[ "$MODE" != "spec-driven" && "$MODE" != "change-driven" ]]; then
  echo "--mode must be spec-driven or change-driven" >&2
  exit 1
fi

python3 - "$ROOT_DIR" "$MODE" "$GOAL" "$REQUEST" "${WORKSTREAMS[@]}" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


root = Path(sys.argv[1])
mode = sys.argv[2]
goal = sys.argv[3].strip()
request = sys.argv[4].strip()
requested_workstreams = [item.strip() for item in sys.argv[5:] if item.strip()]

plan_dir = root / ".ai" / "PLANS"
current_sprint = plan_dir / "current-sprint.md"
subplan_dir = plan_dir / "current-sprint"
subplan_dir.mkdir(parents=True, exist_ok=True)

docs_dir = root / "docs"
doc_exts = {".md", ".markdown", ".mdx", ".txt", ".rst", ".adoc", ".json", ".yaml", ".yml"}
decision_dir = root / ".ai" / "DECISIONS"


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "requested-change"


def titleize(value: str) -> str:
    pieces = [part for part in re.split(r"[-_\s]+", value) if part]
    if not pieces:
        return "Requested Change"
    return " ".join(piece.capitalize() for piece in pieces)


def tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) > 1}


def parse_version(path: Path) -> int:
    match = re.search(r"_v(\d+)\.md$", path.name)
    return int(match.group(1)) if match else 0


def latest_version_only(paths: list[Path]) -> list[Path]:
    grouped: dict[str, Path] = {}
    for path in sorted(paths):
        key = re.sub(r"_v\d+$", "", path.stem)
        best = grouped.get(key)
        if best is None or parse_version(path) >= parse_version(best):
            grouped[key] = path
    return sorted(grouped.values(), key=lambda item: str(item))


def collect_priority_docs() -> list[Path]:
    if not docs_dir.exists():
        return []
    priority: list[Path] = []
    for folder_name in ("PRD", "ERD", "API"):
        folder = docs_dir / folder_name
        if folder.exists():
            files = [path for path in folder.rglob("*.md") if path.is_file()]
            priority.extend(latest_version_only(files))
    other = [
        path
        for path in docs_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in doc_exts and path.parent.name not in {"PRD", "ERD", "API"}
    ]
    return priority + sorted(other)


def score_doc(path: Path, tokens: set[str]) -> int:
    if not tokens:
        return 0
    path_text = str(path.relative_to(root)).lower()
    stem_tokens = set(re.split(r"[^a-z0-9]+", path.stem.lower()))
    score = 0
    for token in tokens:
        if token in path_text:
            score += 4
        if token in stem_tokens:
            score += 2
    if any(part in {"PRD", "ERD", "API"} for part in path.parts):
        score += 1
    return score


def top_docs_for(text: str, limit: int) -> list[Path]:
    ranked = []
    tokens = tokenize(text)
    for path in collect_priority_docs():
        ranked.append((score_doc(path, tokens), path))
    ranked.sort(key=lambda item: (-item[0], str(item[1])))
    positive = [path for score, path in ranked if score > 0]
    if positive:
        return positive[:limit]
    return [path for _, path in ranked[:limit]]


def docs_lines(paths: list[Path], default_line: str) -> list[str]:
    if not paths:
        return [default_line]
    return [f"- `{path.relative_to(root).as_posix()}`" for path in paths]


def decision_lines() -> list[str]:
    if not decision_dir.exists():
        return ["- `.ai/DECISIONS/` had no additional ADRs beyond the template."]
    files = sorted(path for path in decision_dir.glob("*.md") if path.name != "ADR-template.md")
    if not files:
        return ["- `.ai/DECISIONS/` had no additional ADRs beyond the template."]
    return [f"- `{path.relative_to(root).as_posix()}`" for path in files]


def detect_stack() -> dict:
    frameworks: list[str] = []
    signals: list[str] = []

    def add_framework(name: str, signal: str) -> None:
        if name not in frameworks:
            frameworks.append(name)
        if signal not in signals:
            signals.append(signal)

    package_json = root / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            pkg = {}
        deps = {}
        deps.update(pkg.get("dependencies", {}))
        deps.update(pkg.get("devDependencies", {}))
        dep_names = set(deps.keys())
        if "next" in dep_names:
            add_framework("next.js", "package.json:next")
        if {"react", "react-dom"} & dep_names:
            add_framework("react", "package.json:react")
        if "vue" in dep_names:
            add_framework("vue", "package.json:vue")
        if "nuxt" in dep_names:
            add_framework("nuxt", "package.json:nuxt")
        if {"svelte", "@sveltejs/kit"} & dep_names:
            add_framework("svelte", "package.json:svelte")
        if "@angular/core" in dep_names:
            add_framework("angular", "package.json:@angular/core")
        if "@nestjs/core" in dep_names:
            add_framework("nestjs", "package.json:@nestjs/core")
        if "express" in dep_names:
            add_framework("express", "package.json:express")

    for gradle_name in ("build.gradle", "build.gradle.kts"):
        gradle_path = root / gradle_name
        if gradle_path.exists():
            text = gradle_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "spring-boot" in text or "org.springframework.boot" in text:
                add_framework("spring-boot", gradle_name)

    pom_xml = root / "pom.xml"
    if pom_xml.exists():
        text = pom_xml.read_text(encoding="utf-8", errors="ignore").lower()
        if "spring-boot" in text:
            add_framework("spring-boot", "pom.xml")

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in text:
            add_framework("fastapi", "pyproject.toml:fastapi")
        if "django" in text:
            add_framework("django", "pyproject.toml:django")
        if "flask" in text:
            add_framework("flask", "pyproject.toml:flask")

    requirements = root / "requirements.txt"
    if requirements.exists():
        text = requirements.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in text:
            add_framework("fastapi", "requirements.txt:fastapi")
        if "django" in text:
            add_framework("django", "requirements.txt:django")
        if "flask" in text:
            add_framework("flask", "requirements.txt:flask")

    gemfile = root / "Gemfile"
    if gemfile.exists():
        text = gemfile.read_text(encoding="utf-8", errors="ignore").lower()
        if "rails" in text:
            add_framework("rails", "Gemfile:rails")

    go_mod = root / "go.mod"
    if go_mod.exists():
        add_framework("go-module", "go.mod")

    return {
        "configured": bool(frameworks),
        "setup_needed": not frameworks,
        "frameworks": frameworks,
        "signals": signals,
    }


def infer_requested_frameworks(text: str) -> list[str]:
    lowered = text.lower()
    mapping = {
        "react": ["react"],
        "vue": ["vue"],
        "spring-boot": ["spring boot", "spring-boot", "springboot"],
        "next.js": ["next.js", "nextjs", "next"],
        "nestjs": ["nestjs", "nest"],
        "fastapi": ["fastapi"],
        "django": ["django"],
        "flask": ["flask"],
    }
    found: list[str] = []
    for framework, needles in mapping.items():
        if any(needle in lowered for needle in needles):
            found.append(framework)
    return found


def build_setup_workstream() -> str:
    desired = infer_requested_frameworks(f"{goal} {request}")
    desired_summary = ", ".join(desired) if desired else "request-relevant framework choice"
    slug = "framework-setup"
    path = subplan_dir / f"{slug}.md"
    body = "\n".join(
        [
            "# Workstream: Framework Setup",
            "",
            "## Goal",
            "",
            f"`TODO: configure the base application/framework setup needed before delivering the request: {goal}`",
            "",
            "## Scope",
            "",
            f"- `Set up the missing app framework or runtime expected by the request ({desired_summary}).`",
            "- `Establish the minimum runnable project structure, scripts, and dependencies needed for implementation.`",
            "",
            "## Non-goals",
            "",
            "- `Full production deployment setup beyond what the requested change needs.`",
            "- `Optional tooling that does not unblock implementation or validation.`",
            "",
            "## Source Inputs",
            "",
            f"- Request: `{request}`",
            f"- Suggested framework from request: `{desired_summary}`",
            "- Existing stack detection: `no recognized app framework found in the repository`",
            "- Code or architecture references: `.ai/ARCHITECTURE.md`, `.ai/WORKFLOW.md`",
            "",
            "## Success Criteria",
            "",
            "- [ ] A runnable framework baseline exists for the requested change.",
            "- [ ] The repository has clear setup or start commands that implementation and validation can use.",
            "- [ ] Framework choice and setup scope are explicit enough that later workstreams do not improvise infrastructure mid-build.",
            "",
            "## Implementation Plan",
            "",
            f"- [ ] Confirm or choose the required framework/runtime for `{desired_summary}`.",
            "- [ ] Add the minimum project structure, dependency manifests, and start/test commands.",
            "- [ ] Record setup assumptions in docs or runbooks before feature implementation starts.",
            "",
            "## Validation Plan",
            "",
            "- [ ] Review that the chosen setup matches the requested product surface and team expectations.",
            "- [ ] Verify the project can boot, build, or run the minimal smoke path for the chosen framework.",
            "- [ ] Confirm later workstreams no longer need to treat framework setup as an open question.",
            "",
            "## Risks and Open Questions",
            "",
            "- `Framework choice may still require product or team confirmation.`",
            "- `Setup scope can sprawl unless the first delivery slice stays narrow.`",
            "",
            "## Dependencies",
            "",
            "- `Needs a clear decision on the app runtime or framework when the request does not imply one strongly enough.`",
            "",
            "## Handoff",
            "",
            "- Build skill: `start`",
            "- Validation skill: `check`",
            "- Ship readiness note: `core app setup and runnable commands must exist before feature work is called ready`",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")
    return f"- [ ] [{slug}.md]({path.as_posix()}) — missing framework setup을 먼저 정리한다"


stack = detect_stack()
plan_docs = top_docs_for(f"{goal} {request}", 6)
doc_files = collect_priority_docs()

if requested_workstreams:
    workstreams = requested_workstreams
elif plan_docs:
    derived = []
    for doc in plan_docs[:4]:
        rel = doc.relative_to(docs_dir)
        parts = [slugify(part) for part in rel.with_suffix("").parts if part and part != "."]
        candidate = "-".join(parts[-2:]) if len(parts) > 1 else parts[0]
        derived.append(candidate)
    workstreams = list(dict.fromkeys(derived))
else:
    workstreams = ["requested-change"]

workstream_links = []
if stack["setup_needed"]:
    workstream_links.append(build_setup_workstream())

for workstream in workstreams:
    slug = slugify(workstream)
    file_path = subplan_dir / f"{slug}.md"
    scoped_docs = top_docs_for(f"{goal} {request} {workstream}", 4)
    source_docs = docs_lines(
        scoped_docs,
        "- `docs/PRD`, `docs/ERD`, or `docs/API` did not contain an obvious matching spec; derive from the request plus current code and architecture.",
    )
    body = "\n".join(
        [
            f"# Workstream: {titleize(workstream)}",
            "",
            "## Goal",
            "",
            f"`TODO: refine how {titleize(workstream)} delivers part of the sprint goal: {goal}`",
            "",
            "## Scope",
            "",
            f"- `{titleize(workstream)}` implementation slice",
            "- `TODO: add concrete included change`",
            "",
            "## Non-goals",
            "",
            "- `TODO: explicit non-goal 1`",
            "- `TODO: explicit non-goal 2`",
            "",
            "## Source Inputs",
            "",
            f"- Request: `{request}`",
            f"- Planning mode: `{mode}`",
            *source_docs,
            *decision_lines(),
            "- Code or architecture references: `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, `.ai/WORKFLOW.md`",
            "",
            "## Success Criteria",
            "",
            *(
                [
                    f"- [ ] `{titleize(workstream)}` workstream maps directly to cited PRD, ERD, or API docs.",
                    f"- [ ] `{titleize(workstream)}` workstream has observable acceptance criteria that review and QA can verify without re-reading the original chat.",
                    f"- [ ] `{titleize(workstream)}` workstream defines at least one concrete validation path tied to the cited docs or interfaces.",
                ]
                if mode == "spec-driven"
                else [
                    f"- [ ] `{titleize(workstream)}` workstream restates the requested change in observable behavior, not only implementation terms.",
                    f"- [ ] `{titleize(workstream)}` workstream identifies impacted interfaces, states, or operations before code starts.",
                    f"- [ ] `{titleize(workstream)}` workstream defines at least one concrete validation path tied to the requested behavior.",
                ]
            ),
            "",
            "## Implementation Plan",
            "",
            *(
                [
                    f"- [ ] Read the cited docs for `{titleize(workstream)}` and note the exact interfaces, states, and constraints that must be honored.",
                    f"- [ ] Split `{titleize(workstream)}` into the smallest implementation slice that can be validated independently.",
                    f"- [ ] Record any spec, contract, or decision gaps before implementation guesses become code.",
                ]
                if mode == "spec-driven"
                else [
                    f"- [ ] Translate the requested `{titleize(workstream)}` change into impacted modules, routes, APIs, jobs, or operators.",
                    f"- [ ] Choose the smallest safe delivery slice for `{titleize(workstream)}` instead of planning the whole change as one unit.",
                    f"- [ ] Record any doc, contract, decision, or architecture updates that must land with `{titleize(workstream)}`.",
                ]
            ),
            "",
            "## Validation Plan",
            "",
            *(
                [
                    f"- [ ] Review `{titleize(workstream)}` against the cited docs and note any contract drift.",
                    f"- [ ] Validate the main user or operator flow that proves `{titleize(workstream)}` matches the intended spec behavior.",
                    f"- [ ] Run smoke or targeted regression checks for the interfaces touched by `{titleize(workstream)}`.",
                ]
                if mode == "spec-driven"
                else [
                    f"- [ ] Review `{titleize(workstream)}` against the explicit success criteria, decisions, and impacted boundaries.",
                    f"- [ ] Validate the changed user or operator flow plus the most likely regression path for `{titleize(workstream)}`.",
                    f"- [ ] Update or confirm docs when `{titleize(workstream)}` changes expected behavior or operating steps.",
                ]
            ),
            "",
            "## Risks and Open Questions",
            "",
            "- `TODO: risk or question 1`",
            "- `TODO: risk or question 2`",
            "",
            "## Dependencies",
            "",
            "- `TODO: dependency or blocker`",
            "",
            "## Handoff",
            "",
            "- Build skill: `start`",
            "- Validation skill: `check`",
            "- Ship readiness note: `TODO: what must be true before ship`",
            "",
        ]
    )
    file_path.write_text(body, encoding="utf-8")
    workstream_links.append(f"- [ ] [{slug}.md]({file_path.as_posix()}) — TODO: {titleize(workstream)} 워크스트림 목표를 한 줄로 정리하세요")

stack_summary = ", ".join(stack["frameworks"]) if stack["frameworks"] else "no recognized app framework"
stack_signal_summary = ", ".join(stack["signals"]) if stack["signals"] else "none"

plan_doc_lines = docs_lines(
    plan_docs,
    "- `docs/PRD`, `docs/ERD`, or `docs/API` did not contain an obvious matching spec; planning falls back to the request plus current code and runbooks.",
)

plan_text = "\n".join(
    [
        "# Current Sprint",
        "",
        "## Goal",
        "",
        goal,
        "",
        "## Request Mode",
        "",
        f"- Primary mode: `{mode}`",
        f"- Request summary: `{request}`",
        "- Default docs rule: read the latest relevant versions under `docs/PRD/`, `docs/ERD/`, and `docs/API/` first, then fall back to other `docs/` files, `.ai/DECISIONS/`, code, and runbooks.",
        "",
        "## Structured state",
        "",
        "- Narrative plan: this file",
        "- Machine-readable progress: `.ai/PLANS/progress.json`",
        "- Quality and readiness metrics: `.ai/EVALS/metrics.json`",
        "- Workstream subplans: `.ai/PLANS/current-sprint/`",
        "",
        "## Checklist Status Rule",
        "",
        "- `[ ]` not started",
        "- `[~]` in progress",
        "- `[x]` completed successfully",
        "- `[!]` failed, blocked, or requires strategy change",
        "",
        "## Planning Inputs",
        "",
        f"- User request or command: `{request}`",
        *plan_doc_lines,
        *decision_lines(),
        "- Canonical context: `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, `.ai/WORKFLOW.md`",
        "- Supporting context: backlog, roadmap, incidents, runbooks, and relevant code paths",
        "",
        "## Environment and Stack",
        "",
        f"- Detected framework state: `{stack_summary}`",
        f"- Detection signals: `{stack_signal_summary}`",
        f"- Setup needed before implementation: `{'yes' if stack['setup_needed'] else 'no'}`",
        "",
        "## Success Criteria",
        "",
        "- [ ] 스프린트 인덱스가 목표, 성공 기준, 작업 분해, 리스크를 분명히 보여준다.",
        "- [ ] 의미 있는 작업 단위마다 별도 세부 계획 파일이 존재한다.",
        "- [ ] 각 세부 계획 파일은 구현과 검증 스킬이 바로 사용할 수 있는 성공 기준과 검증 계획을 담고 있다.",
        "- [ ] 계획은 `docs/PRD`, `docs/ERD`, `docs/API`의 최신 관련 버전을 우선 입력으로 사용한다.",
        *(
            ["- [ ] 앱 프레임워크가 아직 구성되지 않았다면 세팅 작업이 별도 워크스트림으로 계획에 포함된다."]
            if stack["setup_needed"]
            else ["- [ ] 기존 프레임워크 설정을 전제로 구현 계획이 불필요한 bootstrap 작업 없이 분해된다."]
        ),
        "",
        "## Workstream Index",
        "",
        *workstream_links,
        "",
        "## Think",
        "",
        "- [ ] 대상 사용자, 문제, 비목표를 명확히 한다.",
        "- [ ] 필요한 docs, contracts, decisions, runbooks를 계획 입력으로 확정한다.",
        "",
        "## Plan",
        "",
        "- [ ] 작업을 도메인, API, UI, 잡, 운영 경계 중 하나로 분해한다.",
        "- [ ] 각 작업 단위의 성공 기준과 검증 기준을 명시한다.",
        *(
            ["- [ ] 구현 전에 필요한 프레임워크 세팅 범위를 별도 워크스트림으로 확정한다."]
            if stack["setup_needed"]
            else []
        ),
        "",
        "## Build",
        "",
        "- [ ] 각 세부 계획을 기준으로 구현 단위를 독립적으로 진행할 수 있게 만든다.",
        "- [ ] 구현 도중 바뀐 현실을 상위 계획과 세부 계획에 반영한다.",
        "",
        "## Review",
        "",
        "- [ ] 검증 스킬이 diff만이 아니라 세부 계획의 성공 기준을 함께 보도록 한다.",
        "",
        "## Test",
        "",
        "- [ ] 각 세부 계획마다 최소 한 개의 검증 경로를 실행한다.",
        "- [ ] 구조 변경 후 `scripts/verify.sh`를 실행한다.",
        "",
        "## Ship",
        "",
        "- [ ] 문서, 런북, release readiness 판단이 구현된 계획과 모순되지 않는다.",
        "",
        "## Reflect",
        "",
        "- [ ] 반복되는 실패, 모호한 완료 기준, 불필요하게 큰 작업 단위를 기록한다.",
        "",
        "## Risks and Open Questions",
        "",
        "- [ ] `TODO: unresolved risk or dependency`",
        "- [ ] `TODO: open question that could change the split or acceptance criteria`",
        "",
    ]
)

current_sprint.write_text(plan_text, encoding="utf-8")

print(f"scaffold-plan: wrote {current_sprint.relative_to(root).as_posix()}")
for line in workstream_links:
    match = re.search(r"\[([a-z0-9-]+\.md)\]\(", line)
    if match:
        print(f"scaffold-plan: included {match.group(1)}")
if doc_files:
    print("scaffold-plan: read latest relevant docs from docs/PRD, docs/ERD, docs/API, then fallback docs")
else:
    print("scaffold-plan: no docs directory detected; planning relied on request plus canonical .ai context")
print(f"scaffold-plan: stack detected = {stack_summary}")
PY
