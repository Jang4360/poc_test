#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
usage: scripts/scaffold-specs.sh --request "<request>" [--goal "<goal>"] [--slug "<slug>"] [--update]

Ensure versioned spec docs exist under:
  - docs/PRD/
  - docs/ERD/
  - docs/API/

Default behavior:
  - Reuse the latest existing spec in each folder when present
  - Create missing folders/files as *_v1.md

Update behavior:
  - Create the next version *_vN.md for each spec type
EOF
}

REQUEST=""
GOAL=""
SLUG=""
UPDATE_MODE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --request)
      REQUEST="${2:-}"
      shift 2
      ;;
    --goal)
      GOAL="${2:-}"
      shift 2
      ;;
    --slug)
      SLUG="${2:-}"
      shift 2
      ;;
    --update)
      UPDATE_MODE="true"
      shift 1
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

if [[ -z "$REQUEST" ]]; then
  usage >&2
  exit 1
fi

python3 - "$ROOT_DIR" "$REQUEST" "$GOAL" "$SLUG" "$UPDATE_MODE" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


root = Path(sys.argv[1])
request = sys.argv[2].strip()
goal = sys.argv[3].strip()
provided_slug = sys.argv[4].strip()
update_mode = sys.argv[5].strip().lower() == "true"

docs_root = root / "docs"
spec_types = ("PRD", "ERD", "API")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "requested-change"


def detect_stack() -> dict:
    frameworks: list[str] = []

    def add_framework(name: str) -> None:
        if name not in frameworks:
            frameworks.append(name)

    package_json = root / "package.json"
    if package_json.exists():
        try:
            import json

            pkg = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            pkg = {}
        deps = {}
        deps.update(pkg.get("dependencies", {}))
        deps.update(pkg.get("devDependencies", {}))
        dep_names = set(deps.keys())
        if "next" in dep_names:
            add_framework("next.js")
        if {"react", "react-dom"} & dep_names:
            add_framework("react")
        if "vue" in dep_names:
            add_framework("vue")
        if "nuxt" in dep_names:
            add_framework("nuxt")
        if {"svelte", "@sveltejs/kit"} & dep_names:
            add_framework("svelte")
        if "@angular/core" in dep_names:
            add_framework("angular")
        if "@nestjs/core" in dep_names:
            add_framework("nestjs")
        if "express" in dep_names:
            add_framework("express")

    for gradle_name in ("build.gradle", "build.gradle.kts"):
        gradle_path = root / gradle_name
        if gradle_path.exists():
            text = gradle_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "spring-boot" in text or "org.springframework.boot" in text:
                add_framework("spring-boot")

    pom_xml = root / "pom.xml"
    if pom_xml.exists():
        text = pom_xml.read_text(encoding="utf-8", errors="ignore").lower()
        if "spring-boot" in text:
            add_framework("spring-boot")

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in text:
            add_framework("fastapi")
        if "django" in text:
            add_framework("django")
        if "flask" in text:
            add_framework("flask")

    requirements = root / "requirements.txt"
    if requirements.exists():
        text = requirements.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in text:
            add_framework("fastapi")
        if "django" in text:
            add_framework("django")
        if "flask" in text:
            add_framework("flask")

    gemfile = root / "Gemfile"
    if gemfile.exists():
        text = gemfile.read_text(encoding="utf-8", errors="ignore").lower()
        if "rails" in text:
            add_framework("rails")

    go_mod = root / "go.mod"
    if go_mod.exists():
        add_framework("go-module")

    return {"frameworks": frameworks}


def parse_version(path: Path) -> int:
    match = re.search(r"_v(\d+)\.md$", path.name)
    return int(match.group(1)) if match else 0


def latest(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    return max(paths, key=lambda path: (parse_version(path), path.name))


def title_from_slug(value: str) -> str:
    parts = [part for part in re.split(r"[-_\s]+", value) if part]
    return " ".join(part.capitalize() for part in parts) or "Requested Change"


def write_spec(path: Path, spec_type: str, version: int, previous: Path | None, stack: dict) -> None:
    stack_summary = ", ".join(stack["frameworks"]) if stack["frameworks"] else "unconfigured"
    rel_previous = f"`{previous.relative_to(root).as_posix()}`" if previous else "`none`"
    goal_line = goal or request
    lines = [
        f"# {spec_type}: {title_from_slug(path.stem)}",
        "",
        "## Metadata",
        "",
        f"- Version: `v{version}`",
        "- Status: `draft`",
        f"- Request: `{request}`",
        f"- Goal: `{goal_line}`",
        f"- Stack context: `{stack_summary}`",
        f"- Previous version: {rel_previous}",
        "",
        "## Source Context",
        "",
        "- `TODO: summarize the triggering request or product need`",
        "- `TODO: cite existing docs or decisions that constrain this spec`",
        "",
        "## Scope",
        "",
        "- `TODO: included change 1`",
        "- `TODO: included change 2`",
        "",
        "## Non-goals",
        "",
        "- `TODO: explicit non-goal 1`",
        "- `TODO: explicit non-goal 2`",
        "",
    ]

    if spec_type == "PRD":
        lines.extend(
            [
                "## Target User and Problem",
                "",
                "- `TODO: primary user`",
                "- `TODO: problem trigger and pain`",
                "",
                "## Success Signals",
                "",
                "- [ ] `TODO: measurable outcome 1`",
                "- [ ] `TODO: measurable outcome 2`",
                "",
                "## User Flows and Acceptance",
                "",
                "- [ ] `TODO: main flow`",
                "- [ ] `TODO: edge case or failure flow`",
                "",
            ]
        )
    elif spec_type == "ERD":
        lines.extend(
            [
                "## Domain Model",
                "",
                "- `TODO: core entities`",
                "- `TODO: ownership and lifecycle`",
                "",
                "## Relationships and Constraints",
                "",
                "- `TODO: relationship 1`",
                "- `TODO: constraint or invariant`",
                "",
                "## Migration and Data Risk",
                "",
                "- `TODO: migration impact`",
                "- `TODO: rollback or data recovery note`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Contracts",
                "",
                "- `TODO: endpoint, event, or job contract`",
                "- `TODO: request and response fields`",
                "",
                "## Auth, Validation, and Errors",
                "",
                "- `TODO: auth or trust boundary`",
                "- `TODO: validation or error conditions`",
                "",
                "## Consumer Impact",
                "",
                "- `TODO: frontend, backend, or external consumer impact`",
                "- `TODO: backward compatibility note`",
                "",
            ]
        )

    lines.extend(
        [
            "## Open Questions",
            "",
            "- `TODO: open question 1`",
            "- `TODO: open question 2`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


stack = detect_stack()
slug = provided_slug or slugify(goal or request)
actions: list[str] = []

for spec_type in spec_types:
    folder = docs_root / spec_type
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob("*.md"))
    latest_existing = latest(existing)
    slug_prefix = f"{slug}_{spec_type.lower()}"
    matching = sorted(folder.glob(f"{slug_prefix}_v*.md"))
    latest_matching = latest(matching)

    if update_mode:
        previous = latest_matching or latest_existing
        next_version = (parse_version(previous) + 1) if previous else 1
        target = folder / f"{slug_prefix}_v{next_version}.md"
        write_spec(target, spec_type, next_version, previous, stack)
        actions.append(f"created {target.relative_to(root).as_posix()}")
        continue

    if latest_matching:
        actions.append(f"reused {latest_matching.relative_to(root).as_posix()}")
        continue

    if latest_existing:
        actions.append(f"reused {latest_existing.relative_to(root).as_posix()}")
        continue

    target = folder / f"{slug_prefix}_v1.md"
    write_spec(target, spec_type, 1, None, stack)
    actions.append(f"created {target.relative_to(root).as_posix()}")

for action in actions:
    print(f"scaffold-specs: {action}")
PY
