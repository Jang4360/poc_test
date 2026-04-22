#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="open"
OPEN_BROWSER=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --text)
      MODE="text"
      OPEN_BROWSER=0
      shift
      ;;
    --no-open)
      OPEN_BROWSER=0
      shift
      ;;
    *)
      echo "usage: scripts/dashboard.sh [--text] [--no-open]" >&2
      exit 1
      ;;
  esac
done

"$ROOT_DIR/scripts/update-progress.sh" >/dev/null
"$ROOT_DIR/scripts/update-metrics.sh" >/dev/null

python3 - <<'PY' "$ROOT_DIR" "$MODE" "$OPEN_BROWSER"
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

root = Path(sys.argv[1])
mode = sys.argv[2]
open_browser = sys.argv[3] == "1"

progress = json.loads((root / ".ai" / "PLANS" / "progress.json").read_text(encoding="utf-8"))
metrics = json.loads((root / ".ai" / "EVALS" / "metrics.json").read_text(encoding="utf-8"))
current_sprint = (root / ".ai" / "PLANS" / "current-sprint.md").read_text(encoding="utf-8")
project_md = (root / ".ai" / "PROJECT.md").read_text(encoding="utf-8")
smoke_sh = (root / "scripts" / "smoke.sh").read_text(encoding="utf-8")
release_md = (root / ".ai" / "RUNBOOKS" / "release.md").read_text(encoding="utf-8")
rollback_md = (root / ".ai" / "RUNBOOKS" / "rollback.md").read_text(encoding="utf-8")
retry_path = root / ".ai" / "EVALS" / "retry-log.jsonl"

stage_map = {
    "Think": "사고",
    "Plan": "계획",
    "Build": "구현",
    "Review": "리뷰",
    "Test": "테스트",
    "Ship": "출시",
    "Reflect": "회고",
}
stage_order = list(stage_map.keys())
stage_skill = {
    "Think": "office-hours",
    "Plan": "autoplan",
    "Build": "start",
    "Review": "check",
    "Test": "check",
    "Ship": "ship",
    "Reflect": "learn",
}

goal = "목표가 아직 정리되지 않았습니다."
goal_match = re.search(r"^## Goal\s*$\n+(.+)$", current_sprint, flags=re.MULTILINE)
if goal_match:
    goal = goal_match.group(1).strip()

# ── Parsing ──────────────────────────────────────────────────────────────────
SC_SECTION = "Success Criteria"
WS_SECTION = "Workstream Index"

checklist_re = re.compile(r"^\s*[-*]\s*\[([ xX~!])\]\s+(.+)$")
# Matches: - [x] [filename.md](path) — description
ws_link_re = re.compile(r"^\s*[-*]\s*\[([ xX~!])\]\s*\[([^\]]+)\]\([^)]+\)\s*(?:[—\-]+\s*(.+))?$")
heading_re = re.compile(r"^##\s+(.+?)\s*$")
STATUS_MAP = {"x": "done", "~": "doing", "!": "failed", " ": "todo"}

current_section = None
checklists = []       # stage-based items (Think → Reflect)
success_criteria = [] # ## Success Criteria items
workstreams_idx = []  # ## Workstream Index items

for raw_line in current_sprint.splitlines():
    hm = heading_re.match(raw_line)
    if hm:
        current_section = hm.group(1).strip()
        continue

    if current_section == SC_SECTION:
        m = checklist_re.match(raw_line)
        if m:
            status = STATUS_MAP.get(m.group(1).lower(), "todo")
            success_criteria.append({"title": m.group(2).strip(), "status": status})

    elif current_section == WS_SECTION:
        m = ws_link_re.match(raw_line)
        if m:
            status = STATUS_MAP.get(m.group(1).lower(), "todo")
            name = m.group(2).strip()
            if name.endswith(".md"):
                name = name[:-3]
            desc = (m.group(3) or "").strip().strip("`")
            workstreams_idx.append({"name": name, "description": desc, "status": status})
        else:
            m2 = checklist_re.match(raw_line)
            if m2:
                status = STATUS_MAP.get(m2.group(1).lower(), "todo")
                workstreams_idx.append({"name": m2.group(2).strip(), "description": "", "status": status})

    elif current_section in stage_order:
        m = checklist_re.match(raw_line)
        if m:
            status = STATUS_MAP.get(m.group(1).lower(), "todo")
            checklists.append({"stage": current_section, "title": m.group(2).strip(), "status": status})

# ── Stats ─────────────────────────────────────────────────────────────────────
total_checklists = len(checklists)
done_items   = [i for i in checklists if i["status"] == "done"]
doing_items  = [i for i in checklists if i["status"] == "doing"]
failed_items = [i for i in checklists if i["status"] == "failed"]
todo_items   = [i for i in checklists if i["status"] == "todo"]
started_count = len(done_items) + len(doing_items) + len(failed_items)

completion_rate = round((len(done_items) / total_checklists) * 100, 1) if total_checklists else 0.0
success_rate    = completion_rate
failure_rate    = round((len(failed_items) / total_checklists) * 100, 1) if total_checklists else 0.0

sc_total = len(success_criteria)
sc_done  = sum(1 for sc in success_criteria if sc["status"] == "done")
sc_rate  = round((sc_done / sc_total) * 100, 1) if sc_total else 0.0

ws_total = len(workstreams_idx)
ws_done  = sum(1 for ws in workstreams_idx if ws["status"] == "done")

# ── Retry clusters ─────────────────────────────────────────────────────────────
retry_clusters = Counter()
window_start = datetime.now(timezone.utc) - timedelta(hours=24)
if retry_path.exists():
    for line in retry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            sig  = item.get("signature", "")
            ts   = item.get("timestamp", "")
            note = item.get("note", "")
            if not sig or sig == "placeholder" or note:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= window_start:
                retry_clusters[sig] += 1
        except Exception:
            continue

hot_clusters = {sig: cnt for sig, cnt in retry_clusters.items() if cnt >= 3}

# ── Warnings (for next-actions only, not risks) ───────────────────────────────
warnings = []
if total_checklists == 0:
    warnings.append("current-sprint.md에 체크리스트가 없습니다")
if "Template Project" in project_md:
    warnings.append("프로젝트 정체성이 아직 템플릿 기본값입니다")
if "TODO(project)" in smoke_sh:
    warnings.append("smoke 커맨드가 아직 placeholder 상태입니다")
if "TODO(project)" in release_md:
    warnings.append("release 런북이 아직 placeholder 상태입니다")
if "TODO(project)" in rollback_md:
    warnings.append("rollback 런북이 아직 placeholder 상태입니다")
if metrics.get("release_readiness_confidence") is None:
    warnings.append("release readiness confidence가 아직 기록되지 않았습니다")

# ── Risks (real risks only) ────────────────────────────────────────────────────
risk_items = []
for sig, cnt in sorted(hot_clusters.items(), key=lambda x: -x[1]):
    risk_items.append({"title": sig, "detail": f"최근 24시간 동안 {cnt}회 실패했습니다. learn 스킬로 승격 판단이 필요합니다.", "tone": "danger"})
for item in failed_items:
    risk_items.append({"title": item["title"], "detail": f"{stage_map.get(item['stage'], item['stage'])} 단계 체크리스트가 실패 또는 차단 상태입니다.", "tone": "warning"})

# ── Next actions ───────────────────────────────────────────────────────────────
next_actions = []
if hot_clusters:
    top_sig, top_cnt = sorted(hot_clusters.items(), key=lambda x: -x[1])[0]
    next_actions.append({"title": f"반복 실패 정리: {top_sig}", "detail": f"최근 24시간 동안 {top_cnt}회 실패했습니다. learn으로 원인을 승격하세요.", "skill": "learn"})
if failed_items:
    for item in failed_items[:2]:
        next_actions.append({"title": f"실패 항목 처리: {item['title']}", "detail": f"{stage_map.get(item['stage'], item['stage'])} 단계의 막힌 원인을 제거하고 체크리스트를 갱신하세요.", "skill": stage_skill.get(item["stage"], "dashboard")})
elif doing_items:
    for item in doing_items[:3]:
        next_actions.append({"title": f"진행 중 항목 계속: {item['title']}", "detail": f"{stage_map.get(item['stage'], item['stage'])} 단계 체크리스트를 완료 상태로 이동할 근거를 남기세요.", "skill": stage_skill.get(item["stage"], "dashboard")})
else:
    for item in todo_items[:3]:
        next_actions.append({"title": f"다음 시작 항목: {item['title']}", "detail": f"{stage_map.get(item['stage'], item['stage'])} 단계의 첫 작업으로 진행하세요.", "skill": stage_skill.get(item["stage"], "dashboard")})
if any("smoke 커맨드" in w for w in warnings):
    next_actions.append({"title": "smoke 커맨드 설정", "detail": "scripts/smoke.sh에 실제 프로젝트 smoke 검증 커맨드를 연결하세요.", "skill": "dashboard"})

# ── Text mode ─────────────────────────────────────────────────────────────────
if mode == "text":
    print("하네스 대시보드")
    print("")
    print("개요")
    print(f"- 스프린트: {progress.get('sprint_name', 'unknown')}")
    print(f"- 목표: {goal}")
    print(f"- 성공 기준: {sc_done}/{sc_total} 달성")
    print(f"- 워크스트림: {ws_done}/{ws_total} 완료")
    print(f"- Stage 체크리스트: {len(done_items)}/{total_checklists}")
    print(f"- 진행 중: {len(doing_items)}")
    print(f"- 실패/차단: {len(failed_items)}")
    print(f"- 성공률: {success_rate}%")
    print(f"- 실패율: {failure_rate}%")
    print(f"- 반복 실패 수: {metrics.get('retry_count')}")
    print("")
    if risk_items:
        print("리스크")
        for r in risk_items:
            print(f"- [{r['tone'].upper()}] {r['title']}: {r['detail']}")
        print("")
    print("다음 작업")
    for idx, action in enumerate(next_actions[:5], start=1):
        print(f"{idx}. {action['title']} | skill: {action['skill']}")
        print(f"   {action['detail']}")
    sys.exit(0)

# ── HTML generation ───────────────────────────────────────────────────────────
generated_dir = root / ".ai" / ".generated"
generated_dir.mkdir(parents=True, exist_ok=True)
dashboard_path = generated_dir / "dashboard.html"

def metric_card(label, value, tone="neutral"):
    return f"""
    <article class="metric-card {tone}">
      <div class="metric-label">{escape(label)}</div>
      <div class="metric-value">{escape(str(value))}</div>
    </article>"""

summary_cards = [
    metric_card("성공 기준", f"{sc_done} / {sc_total}", "accent"),
    metric_card("워크스트림", f"{ws_done} / {ws_total}", "neutral"),
    metric_card("Stage 완료", f"{len(done_items)} / {total_checklists}", "neutral"),
    metric_card("하네스 상태", metrics.get("harness_health_score"), "neutral"),
]

performance_cards = [
    metric_card("성공률", f"{success_rate}%", "neutral"),
    metric_card("실패율", f"{failure_rate}%", "neutral"),
    metric_card("반복 실패 수", metrics.get("retry_count"), "neutral"),
]

# ── Success Criteria markup ────────────────────────────────────────────────────
sc_icon_map = {"done": ("✓", "done"), "doing": ("~", "doing"), "failed": ("✗", "failed"), "todo": ("○", "todo")}
sc_items_html = []
for sc in success_criteria:
    icon, cls = sc_icon_map.get(sc["status"], ("○", "todo"))
    sc_items_html.append(f"""
      <li class="sc-item {cls}">
        <span class="sc-icon">{icon}</span>
        <span class="sc-title">{escape(sc['title'])}</span>
      </li>""")

if sc_items_html:
    sc_markup = f"<ul class='sc-list'>{''.join(sc_items_html)}</ul>"
else:
    sc_markup = '<div class="empty-panel">성공 기준이 아직 정의되지 않았습니다.<br>current-sprint.md의 ## Success Criteria 섹션에 추가하세요.</div>'

# ── Workstream markup ──────────────────────────────────────────────────────────
ws_label_map = {"done": ("완료", "done"), "doing": ("진행 중", "doing"), "failed": ("실패", "failed"), "todo": ("대기", "todo")}
ws_items_html = []
for ws in workstreams_idx:
    label, cls = ws_label_map.get(ws["status"], ("대기", "todo"))
    desc_html = f'<div class="ws-desc">{escape(ws["description"])}</div>' if ws["description"] else ""
    ws_items_html.append(f"""
      <div class="ws-item {cls}">
        <div class="ws-dot"></div>
        <div class="ws-info">
          <div class="ws-name">{escape(ws['name'])}</div>
          {desc_html}
        </div>
        <div class="ws-badge">{label}</div>
      </div>""")

if ws_items_html:
    ws_markup = f"<div class='ws-list'>{''.join(ws_items_html)}</div>"
else:
    ws_markup = '<div class="empty-panel">워크스트림이 아직 정의되지 않았습니다.<br>scripts/scaffold-plan.sh 또는 autoplan으로 생성하세요.</div>'

# ── Next actions markup ────────────────────────────────────────────────────────
action_cards_html = []
for idx, action in enumerate(next_actions[:4], start=1):
    action_cards_html.append(f"""
      <article class="action-card">
        <div class="action-index">{idx:02d}</div>
        <div class="action-main">
          <div class="action-title">{escape(action['title'])}</div>
          <div class="action-detail">{escape(action['detail'])}</div>
        </div>
        <div class="action-skill">{escape(action['skill'])}</div>
      </article>""")
if not action_cards_html:
    action_cards_html.append("""
      <article class="action-card">
        <div class="action-index">01</div>
        <div class="action-main">
          <div class="action-title">즉시 필요한 작업 없음</div>
          <div class="action-detail">체크리스트와 메트릭을 최신 상태로 유지하며 다음 단계 전환 시점을 판단하세요.</div>
        </div>
        <div class="action-skill">dashboard</div>
      </article>""")

# ── Risk markup ────────────────────────────────────────────────────────────────
if risk_items:
    risk_li = []
    for risk in risk_items:
        risk_li.append(f"""
        <li class="risk-item {escape(risk['tone'])}">
          <div class="risk-dot"></div>
          <div class="risk-copy">
            <div class="risk-title">{escape(risk['title'])}</div>
            <div class="risk-detail">{escape(risk['detail'])}</div>
          </div>
        </li>""")
    risk_markup = f"<ul class='risk-list'>{''.join(risk_li)}</ul>"
else:
    risk_markup = """
    <div class="empty-risk">
      <div class="empty-risk-title">현재 주요 리스크 없음</div>
      <div class="empty-risk-detail">체크리스트와 메트릭에서 즉시 처리할 위험 신호는 보이지 않습니다.</div>
    </div>"""

progress_degrees = max(0, min(360, round((completion_rate / 100) * 360)))
sc_degrees       = max(0, min(360, round((sc_rate / 100) * 360)))

html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>하네스 대시보드</title>
  <style>
    :root {{
      --bg: #f6f4ee;
      --panel: #ffffff;
      --ink: #1f261f;
      --muted: #728072;
      --line: rgba(26, 42, 27, 0.09);
      --green-900: #173b20;
      --green-800: #21562d;
      --green-700: #2f6b39;
      --green-500: #4f9b5f;
      --green-200: #d8ecd9;
      --gray-100: #f3f5f1;
      --gray-200: #e6ebe4;
      --blue-100: #e8f0ff;
      --blue-700: #2c59c4;
      --danger: #b85d3d;
      --warning: #c88d31;
      --shadow: 0 20px 48px rgba(24, 38, 22, 0.08);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 18px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(79, 155, 95, 0.12), transparent 26%),
        linear-gradient(180deg, #fbfcf8 0%, var(--bg) 100%);
      color: var(--ink);
      min-height: 100vh;
    }}
    .shell {{
      width: min(1340px, calc(100vw - 40px));
      margin: 22px auto 36px;
      display: grid;
      gap: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow);
    }}
    .panel-body {{ padding: 22px; }}
    .panel-title {{
      margin: 0 0 16px;
      font-size: 17px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .panel-count {{
      font-size: 13px;
      font-weight: 500;
      color: var(--muted);
      background: var(--gray-100);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 10px;
    }}

    /* ── Hero ── */
    .hero {{ padding: 26px 28px 22px; display: grid; gap: 18px; }}
    .hero-top {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; }}
    .hero-title {{ margin: 0; font-size: clamp(28px, 4vw, 42px); line-height: 1; font-weight: 700; }}
    .hero-goal {{ margin-top: 8px; color: var(--muted); line-height: 1.5; max-width: 72ch; }}
    .hero-badge {{ padding: 10px 16px; border-radius: 999px; background: var(--gray-100); border: 1px solid var(--line); font-size: 14px; color: var(--green-900); white-space: nowrap; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }}
    .metric-card {{ border-radius: var(--radius-lg); padding: 18px; border: 1px solid var(--line); background: var(--gray-100); }}
    .metric-card.accent {{ background: linear-gradient(180deg, var(--green-800), var(--green-900)); color: white; border-color: transparent; }}
    .metric-label {{ font-size: 13px; color: var(--muted); margin-bottom: 14px; }}
    .metric-card.accent .metric-label {{ color: rgba(255,255,255,0.72); }}
    .metric-value {{ font-size: clamp(26px, 3vw, 40px); font-weight: 700; line-height: 1; }}

    /* ── 2-col grid ── */
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
    .grid-wide {{ display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 18px; }}

    /* ── Success Criteria ── */
    .sc-list {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
    .sc-item {{
      display: grid;
      grid-template-columns: 24px 1fr;
      gap: 10px;
      align-items: start;
      padding: 12px 14px;
      border-radius: var(--radius-md);
      border: 1px solid var(--line);
      background: var(--gray-100);
    }}
    .sc-item.done {{ background: #f0f8f0; border-color: var(--green-200); }}
    .sc-item.doing {{ background: #f0f4ff; border-color: #c5d3f8; }}
    .sc-item.failed {{ background: #fff4f0; border-color: #f0c8bb; }}
    .sc-icon {{
      width: 24px; height: 24px;
      display: grid; place-items: center;
      border-radius: 50%;
      font-size: 13px; font-weight: 700;
      background: var(--gray-200); color: var(--muted);
      flex-shrink: 0;
    }}
    .sc-item.done .sc-icon {{ background: var(--green-200); color: var(--green-900); }}
    .sc-item.doing .sc-icon {{ background: var(--blue-100); color: var(--blue-700); }}
    .sc-item.failed .sc-icon {{ background: #f5d5c8; color: var(--danger); }}
    .sc-title {{ font-size: 14px; line-height: 1.45; padding-top: 4px; }}

    /* ── Workstream ── */
    .ws-list {{ display: grid; gap: 10px; }}
    .ws-item {{
      display: grid;
      grid-template-columns: 12px 1fr auto;
      gap: 12px;
      align-items: center;
      padding: 14px 16px;
      border-radius: var(--radius-md);
      border: 1px solid var(--line);
      background: var(--gray-100);
    }}
    .ws-item.done {{ background: #f0f8f0; border-color: var(--green-200); }}
    .ws-item.doing {{ background: #f0f4ff; border-color: #c5d3f8; }}
    .ws-item.failed {{ background: #fff4f0; border-color: #f0c8bb; }}
    .ws-dot {{ width: 12px; height: 12px; border-radius: 50%; background: var(--gray-200); flex-shrink: 0; }}
    .ws-item.done .ws-dot {{ background: var(--green-500); }}
    .ws-item.doing .ws-dot {{ background: var(--blue-700); }}
    .ws-item.failed .ws-dot {{ background: var(--danger); }}
    .ws-name {{ font-size: 14px; font-weight: 600; }}
    .ws-desc {{ font-size: 13px; color: var(--muted); margin-top: 3px; line-height: 1.4; }}
    .ws-badge {{
      font-size: 12px; font-weight: 600;
      padding: 4px 10px; border-radius: 999px;
      background: var(--gray-200); color: var(--muted);
      white-space: nowrap;
    }}
    .ws-item.done .ws-badge {{ background: var(--green-200); color: var(--green-900); }}
    .ws-item.doing .ws-badge {{ background: var(--blue-100); color: var(--blue-700); }}
    .ws-item.failed .ws-badge {{ background: #f5d5c8; color: var(--danger); }}

    /* ── Stage Progress ── */
    .progress-layout {{ display: grid; grid-template-columns: 200px 1fr; gap: 20px; align-items: center; }}
    .gauge-wrap {{ display: grid; place-items: center; }}
    .gauge {{
      width: 190px; aspect-ratio: 1; border-radius: 50%;
      background:
        radial-gradient(circle at center, white 0 56%, transparent 57%),
        conic-gradient(var(--green-800) 0deg {progress_degrees}deg, #dfe6dd {progress_degrees}deg 360deg);
      display: grid; place-items: center;
    }}
    .gauge-inner {{ display: grid; place-items: center; text-align: center; gap: 4px; }}
    .gauge-value {{ font-size: 40px; font-weight: 800; line-height: 1; color: var(--green-900); }}
    .gauge-caption {{ font-size: 12px; color: var(--muted); }}
    .mini-stats {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}
    .mini-card {{ border-radius: var(--radius-md); padding: 14px 16px; border: 1px solid var(--line); background: var(--gray-100); }}
    .mini-label {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; }}
    .mini-value {{ font-size: 26px; font-weight: 700; line-height: 1; }}

    /* ── Risk ── */
    .risk-list {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
    .risk-item {{
      display: grid; grid-template-columns: 12px 1fr; gap: 12px;
      padding: 14px 16px; border-radius: var(--radius-lg);
      border: 1px solid var(--line); background: var(--gray-100);
    }}
    .risk-dot {{ width: 12px; height: 12px; border-radius: 50%; margin-top: 4px; background: var(--warning); }}
    .risk-item.danger .risk-dot {{ background: var(--danger); }}
    .risk-title {{ font-weight: 700; margin-bottom: 4px; }}
    .risk-detail {{ color: var(--muted); font-size: 14px; line-height: 1.45; }}
    .empty-risk {{ border-radius: var(--radius-lg); border: 1px dashed var(--line); padding: 18px; background: #fbfcfa; }}
    .empty-risk-title {{ font-weight: 700; margin-bottom: 6px; }}
    .empty-risk-detail {{ color: var(--muted); font-size: 14px; line-height: 1.45; }}
    .empty-panel {{ color: var(--muted); font-size: 14px; line-height: 1.6; padding: 8px 0; }}

    /* ── Next Actions ── */
    .next-actions {{ display: grid; gap: 10px; }}
    .action-card {{
      display: grid; grid-template-columns: 48px 1fr auto;
      gap: 14px; align-items: center;
      padding: 14px 16px; border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #ffffff, #f6f8f4);
    }}
    .action-index {{
      width: 48px; height: 48px; display: grid; place-items: center;
      border-radius: 14px; background: var(--green-900); color: white;
      font-weight: 700; font-size: 15px;
    }}
    .action-title {{ font-weight: 700; margin-bottom: 4px; }}
    .action-detail {{ color: var(--muted); font-size: 13px; line-height: 1.45; }}
    .action-skill {{
      padding: 7px 12px; border-radius: 999px;
      background: var(--green-200); color: var(--green-900);
      font-size: 12px; font-weight: 600; white-space: nowrap;
    }}

    /* ── Performance ── */
    .performance-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }}

    /* ── Responsive ── */
    @media (max-width: 1100px) {{
      .grid2, .grid-wide {{ grid-template-columns: 1fr; }}
      .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 700px) {{
      .progress-layout {{ grid-template-columns: 1fr; }}
      .mini-stats, .performance-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .summary-grid {{ grid-template-columns: 1fr; }}
      .action-card {{ grid-template-columns: 48px 1fr; }}
      .action-skill {{ grid-column: 2; justify-self: start; }}
    }}
  </style>
</head>
<body>
  <main class="shell">

    <!-- Hero -->
    <section class="panel hero">
      <div class="hero-top">
        <div>
          <h1 class="hero-title">대시보드</h1>
          <div class="hero-goal">스프린트: <strong>{escape(progress.get('sprint_name', ''))}</strong><br>{escape(goal)}</div>
        </div>
        <div class="hero-badge">업데이트 {escape(str(metrics.get('updated_at', '')))} </div>
      </div>
      <section class="summary-grid">
        {''.join(summary_cards)}
      </section>
    </section>

    <!-- Success Criteria | Workstream Index -->
    <section class="grid2">
      <section class="panel panel-body">
        <h2 class="panel-title">
          성공 기준
          <span class="panel-count">{sc_done} / {sc_total} 달성</span>
        </h2>
        {sc_markup}
      </section>
      <section class="panel panel-body">
        <h2 class="panel-title">
          워크스트림
          <span class="panel-count">{ws_done} / {ws_total} 완료</span>
        </h2>
        {ws_markup}
      </section>
    </section>

    <!-- Stage Progress | Risks -->
    <section class="grid-wide">
      <section class="panel panel-body">
        <h2 class="panel-title">Stage 진행 현황</h2>
        <div class="progress-layout">
          <div class="gauge-wrap">
            <div class="gauge">
              <div class="gauge-inner">
                <div class="gauge-value">{completion_rate}%</div>
                <div class="gauge-caption">Stage 완료율</div>
              </div>
            </div>
          </div>
          <div class="mini-stats">
            <article class="mini-card">
              <div class="mini-label">시작됨</div>
              <div class="mini-value">{started_count}</div>
            </article>
            <article class="mini-card">
              <div class="mini-label">대기 중</div>
              <div class="mini-value">{len(todo_items)}</div>
            </article>
            <article class="mini-card">
              <div class="mini-label">하네스 상태</div>
              <div class="mini-value">{metrics.get('harness_health_score')}</div>
            </article>
          </div>
        </div>
      </section>
      <section class="panel panel-body">
        <h2 class="panel-title">리스크</h2>
        {risk_markup}
      </section>
    </section>

    <!-- Next Actions | Performance -->
    <section class="grid2">
      <section class="panel panel-body">
        <h2 class="panel-title">다음 작업</h2>
        <div class="next-actions">
          {''.join(action_cards_html)}
        </div>
      </section>
      <section class="panel panel-body">
        <h2 class="panel-title">성과 지표</h2>
        <section class="performance-grid">
          {''.join(performance_cards)}
        </section>
      </section>
    </section>

  </main>
</body>
</html>
"""

dashboard_path.write_text(html, encoding="utf-8")

if open_browser:
    target = str(dashboard_path.resolve())
    try:
        if os.name == "nt":
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{target}'"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif sys.platform == "darwin":
            subprocess.run(["open", target], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["xdg-open", target], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

print(f"dashboard: generated {dashboard_path}")
if open_browser:
    print("dashboard: opened in default browser")
PY
