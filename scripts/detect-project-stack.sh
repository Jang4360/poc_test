#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JSON_MODE="${1:-}"

python3 - "$ROOT_DIR" "$JSON_MODE" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


root = Path(sys.argv[1])
json_mode = sys.argv[2] == "--json"

frameworks: list[str] = []
signals: list[str] = []
languages: set[str] = set()


def add_framework(name: str, signal: str, language: str) -> None:
    if name not in frameworks:
        frameworks.append(name)
    if signal not in signals:
        signals.append(signal)
    languages.add(language)


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
        add_framework("next.js", "package.json:next", "javascript")
    if {"react", "react-dom"} & dep_names:
        add_framework("react", "package.json:react", "javascript")
    if "vue" in dep_names:
        add_framework("vue", "package.json:vue", "javascript")
    if "nuxt" in dep_names:
        add_framework("nuxt", "package.json:nuxt", "javascript")
    if {"svelte", "@sveltejs/kit"} & dep_names:
        add_framework("svelte", "package.json:svelte", "javascript")
    if "@angular/core" in dep_names:
        add_framework("angular", "package.json:@angular/core", "javascript")
    if "@nestjs/core" in dep_names:
        add_framework("nestjs", "package.json:@nestjs/core", "javascript")
    if "express" in dep_names:
        add_framework("express", "package.json:express", "javascript")

for gradle_name in ("build.gradle", "build.gradle.kts"):
    gradle_path = root / gradle_name
    if gradle_path.exists():
        text = gradle_path.read_text(encoding="utf-8", errors="ignore").lower()
        if "spring-boot" in text or "org.springframework.boot" in text:
            add_framework("spring-boot", gradle_name, "java")

pom_xml = root / "pom.xml"
if pom_xml.exists():
    text = pom_xml.read_text(encoding="utf-8", errors="ignore").lower()
    if "spring-boot" in text:
        add_framework("spring-boot", "pom.xml", "java")

pyproject = root / "pyproject.toml"
if pyproject.exists():
    text = pyproject.read_text(encoding="utf-8", errors="ignore").lower()
    if "fastapi" in text:
        add_framework("fastapi", "pyproject.toml:fastapi", "python")
    if "django" in text:
        add_framework("django", "pyproject.toml:django", "python")
    if "flask" in text:
        add_framework("flask", "pyproject.toml:flask", "python")

requirements = root / "requirements.txt"
if requirements.exists():
    text = requirements.read_text(encoding="utf-8", errors="ignore").lower()
    if "fastapi" in text:
        add_framework("fastapi", "requirements.txt:fastapi", "python")
    if "django" in text:
        add_framework("django", "requirements.txt:django", "python")
    if "flask" in text:
        add_framework("flask", "requirements.txt:flask", "python")

gemfile = root / "Gemfile"
if gemfile.exists():
    text = gemfile.read_text(encoding="utf-8", errors="ignore").lower()
    if "rails" in text:
        add_framework("rails", "Gemfile:rails", "ruby")

go_mod = root / "go.mod"
if go_mod.exists():
    add_framework("go-module", "go.mod", "go")

configured = bool(frameworks)

result = {
    "configured": configured,
    "setup_needed": not configured,
    "frameworks": frameworks,
    "languages": sorted(languages),
    "signals": signals,
}

if json_mode:
    print(json.dumps(result, ensure_ascii=False))
else:
    print(", ".join(frameworks) if frameworks else "no recognized app framework")
PY
