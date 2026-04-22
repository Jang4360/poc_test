#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/.ai/SKILLS"
ADAPTERS_DIR="$ROOT_DIR/.ai/ADAPTERS"
CLAUDE_DIR="$ROOT_DIR/.claude/skills"
AGENTS_DIR="$ROOT_DIR/.agents/skills"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "missing canonical skills directory: $SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -d "$ADAPTERS_DIR" ]]; then
  echo "missing canonical adapters directory: $ADAPTERS_DIR" >&2
  exit 1
fi

SKILL_DIRS=()
while IFS= read -r skill_dir; do
  SKILL_DIRS+=("$skill_dir")
done < <(find "$SOURCE_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

sync_target() {
  local target_dir="$1"
  mkdir -p "$target_dir"

  while IFS= read -r existing_dir; do
    rm -rf "$existing_dir"
  done < <(find "$target_dir" -mindepth 1 -maxdepth 1 -type d | sort)

  local skill_dir
  local skill_name
  for skill_dir in "${SKILL_DIRS[@]}"; do
    skill_name="$(basename "$skill_dir")"
    mkdir -p "$target_dir/$skill_name"
    cp -R "$skill_dir/." "$target_dir/$skill_name/"
  done
}

sync_target "$CLAUDE_DIR"
sync_target "$AGENTS_DIR"

mkdir -p "$ROOT_DIR/.claude" "$ROOT_DIR/.agents" "$ROOT_DIR/.codex"
cp "$ADAPTERS_DIR/claude/settings.json" "$ROOT_DIR/.claude/settings.json"
cp "$ADAPTERS_DIR/claude/README.md" "$ROOT_DIR/.claude/README.md"
cp "$ADAPTERS_DIR/agents/README.md" "$ROOT_DIR/.agents/README.md"
cp "$ADAPTERS_DIR/codex/config.toml" "$ROOT_DIR/.codex/config.toml"
cp "$ADAPTERS_DIR/codex/hooks.json" "$ROOT_DIR/.codex/hooks.json"
cp "$ADAPTERS_DIR/codex/README.md" "$ROOT_DIR/.codex/README.md"

echo "synced ${#SKILL_DIRS[@]} canonical skills and adapter files into .claude, .agents, and .codex"
