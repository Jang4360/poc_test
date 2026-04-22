# AI Harness Engineering

이 저장소는 AI 개발 프로세스를 채팅에만 남기지 않고, 문서와 계획, 검증 흐름까지 저장소 아티팩트로 남기기 위한 하네스 템플릿입니다. 핵심은 `docs/`에 명세를 두고 `.ai/`에 계획, 검증, 운영 규칙을 유지하면서 같은 흐름으로 기획부터 구현, 검증, 회고까지 이어지게 만드는 것입니다.

---

## 빠른 시작

```bash
bash scripts/bootstrap-template.sh "My Project"
export HARNESS_SMOKE_COMMAND="npm run lint && npm test"
bash scripts/verify.sh
bash scripts/dashboard.sh
```

PowerShell에서는 `export` 대신 아래처럼 설정하면 됩니다.

```powershell
$env:HARNESS_SMOKE_COMMAND = "npm run lint && npm test"
```

### smoke command는 무엇을 기준으로 정하나

프로젝트의 smoke command는 전체 CI를 대체하는 것이 아니라, 변경 이후 최소한의 신뢰를 빠르게 확인하는 명령이어야 합니다.

예시:

- Vue: `npm run lint && npm run test:unit && npm run build`
- React: `npm run lint && npm test -- --runInBand && npm run build`
- Next.js: `npm run lint && npm test -- --runInBand && npm run build`
- Spring Boot: `./gradlew test bootJar`
- FastAPI: `pytest -q tests/smoke && python -m compileall app`

---

## 최소한 직접 채워야 하는 파일

- `.ai/PROJECT.md`
  이 저장소가 실제로 무엇을 만드는지 적으면 됩니다.
  포함할 내용:
  - 프로젝트 한 줄 설명
  - 핵심 사용자
  - 해결하려는 문제
  - 이번 저장소의 비목표

- `.ai/ARCHITECTURE.md`
  현재 시스템 구조와 중요한 경계를 적으면 됩니다.
  포함할 내용:
  - 주요 레이어나 모듈
  - 데이터 흐름
  - 외부 연동 지점
  - 인증, 권한, 상태 같은 핵심 경계

---

## 권장 사용 순서

### 1. 명세가 없거나 부족하면 먼저 문서를 만든다

```text
/docs
주문 기능 PRD, ERD, API 문서를 먼저 만들어줘. 기존 문서가 있으면 재사용하고 부족한 것만 생성해줘.
```

이 단계는 `docs/PRD`, `docs/ERD`, `docs/API`를 먼저 채우거나 보강하는 단계입니다.

### 2. 명세가 있으면 구현 계획을 만든다

```text
/plan
docs의 최신 PRD, ERD, API와 .ai/DECISIONS를 읽고 구현 계획을 세부 워크스트림으로 나눠줘.
```

결과물:

- 상위 계획: `.ai/PLANS/current-sprint.md`
- 세부 계획: `.ai/PLANS/current-sprint/*.md`

각 세부 계획은 최소한 아래를 포함해야 합니다.

- `Success Criteria`
- `Implementation Plan`
- `Validation Plan`

프레임워크가 아직 없는 저장소라면 이 단계에서 `framework-setup` 워크스트림이 자동으로 계획에 들어갑니다.

### 2-1. 범위와 제품 가치를 점검하고 싶으면 plan-ceo를 쓴다

```text
/plan-ceo
현재 스프린트 계획을 제품 범위와 사용자 가치 관점에서 점검해줘.
```

### 2-2. 기술 구조를 점검하고 싶으면 plan-eng를 쓴다

```text
/plan-eng
현재 스프린트 계획을 아키텍처, 실패 모드, 신뢰 경계, 테스트 전략 관점에서 점검해줘.
```

### 2-3. UX 상태와 정보 구조를 점검하고 싶으면 plan-design을 쓴다

```text
/plan-design
현재 스프린트 계획을 인터랙션 상태와 정보 구조 관점에서 점검해줘.
```

### 3. 문서부터 계획까지 한 번에 하고 싶으면 autoplan을 쓴다

```text
/autoPlan
결제 플로우를 모바일 웹에 추가하려고 해. 문서가 없으면 PRD, ERD, API부터 만들고 있으면 그걸 기반으로 구현 계획까지 이어줘.
```

`/autoPlan`은 문서가 부족하면 먼저 보강하고, 충분하면 바로 계획으로 이어집니다.

### 4. 구현과 검증을 한 번에 하고 싶으면 기본 진입점은 start다

```text
/start
로그인 에러 토스트 중복 노출 버그를 수정해줘.
```

이 명령은 구현만 하고 멈추지 않습니다. 구현 후 `check` 단계까지 이어지는 기본 경로입니다.

### 5. 검증만 다시 하고 싶으면 check를 쓴다

```text
/check
현재 diff를 기준으로 코드리뷰와 사용자 플로우 검증을 해줘.
```

이 명령은 코드리뷰와 QA를 하나의 검증 게이트로 묶습니다.

### 6. 현재 상태를 보고 싶으면 dashboard를 쓴다

```text
/dashboard
```

또는:

```bash
bash scripts/dashboard.sh
```

---

## 상황별 추천 명령

| 상황 | 추천 명령 | 의미 |
|---|---|---|
| 명세가 비어 있다 | `/docs` | PRD/ERD/API 문서 생성 또는 보강 |
| 명세는 있고 계획만 필요하다 | `/plan` | 상위 계획 + 세부 작업 계획 작성 |
| 계획의 범위와 제품 가치를 점검하고 싶다 | `/plan-ceo` | 제품 범위, 웨지, 비목표 점검 |
| 계획의 기술 구조를 점검하고 싶다 | `/plan-eng` | 아키텍처, 실패 모드, 테스트 전략 점검 |
| 계획의 UX 상태를 점검하고 싶다 | `/plan-design` | 인터랙션 상태와 정보 구조 점검 |
| 문서부터 계획까지 한 번에 하고 싶다 | `/autoPlan` | 기획과 계획 오케스트레이션 |
| 구현과 검증을 한 번에 끝내고 싶다 | `/start` | 구현 + 검증 기본 경로 |
| 코드리뷰와 QA를 다시 돌리고 싶다 | `/check` | 통합 검증 게이트 |
| 원인 분석이 먼저 필요하다 | `/investigate` | 증거 기반 조사 |
| 반복 실패를 학습으로 승격하고 싶다 | `/learn` | MEMORY/EVAL/SKILL/ADR 승격 |
| 현재 상태를 보고 싶다 | `/dashboard` | 브라우저 대시보드 생성 |

---

## README에서 알아야 하는 운영 규칙

- 명세는 `docs/PRD`, `docs/ERD`, `docs/API`에 둡니다.
- 명세 파일은 덮어쓰기보다 `_v1`, `_v2`처럼 버전으로 관리합니다.
- 구현 계획은 상위 계획과 세부 계획으로 나눕니다.
- 구현이 끝났다고 바로 done이 아니고, `check` 같은 검증 게이트를 지나야 done입니다.
- 반복 실패는 같은 시도를 계속하지 말고 `learn`으로 승격합니다.

---

## 자주 쓰는 기본 명령

```bash
scripts/check-dangerous-command.sh "<command>"
scripts/record-retry.sh <signature>
scripts/check-circuit-breaker.sh <signature>
scripts/verify.sh
scripts/dashboard.sh
```

의미:

- `check-dangerous-command.sh`: 위험한 명령 실행 전 차단
- `record-retry.sh`: 실패 기록 + circuit breaker 확인
- `check-circuit-breaker.sh`: 같은 실패를 다시 시도해도 되는지 확인
- `verify.sh`: 저장소 구조와 adapter sync 상태 검증
- `dashboard.sh`: 상태 대시보드 생성

---

## 주요 파일 구조

```text
docs/
├── PRD/                 # 제품 명세
├── ERD/                 # 데이터/도메인 명세
└── API/                 # API/계약 명세

.ai/
├── PROJECT.md
├── ARCHITECTURE.md
├── WORKFLOW.md
├── DECISIONS/
├── PLANS/
│   ├── current-sprint.md
│   ├── current-sprint/
│   └── progress.json
├── EVALS/
├── MEMORY/
├── RUNBOOKS/
└── SKILLS/

.claude/skills/          # Claude adapter
.agents/skills/          # Codex adapter
scripts/                 # helper scripts
```

canonical 변경 순서:

1. `.ai/SKILLS/` 또는 `.ai/` canonical 파일 수정
2. `bash scripts/sync-adapters.sh`
3. `bash scripts/verify.sh`

---

## 운영 규칙 한 줄 요약

- 문서가 없으면 먼저 만든다.
- 계획은 상위 계획과 세부 계획으로 나눈다.
- 구현은 계획 기준으로 진행한다.
- 완료 판단은 검증 이후에 한다.
- 반복 실패는 학습으로 승격한다.

관련 문서:

- [AGENTS.md](C:/Users/SSAFY/harness_engineering/AGENTS.md)
- [CLAUDE.md](C:/Users/SSAFY/harness_engineering/CLAUDE.md)
- [.ai/WORKFLOW.md](C:/Users/SSAFY/harness_engineering/.ai/WORKFLOW.md)
- [.ai/ARCHITECTURE.md](C:/Users/SSAFY/harness_engineering/.ai/ARCHITECTURE.md)
- [.ai/AUTOMATION.md](C:/Users/SSAFY/harness_engineering/.ai/AUTOMATION.md)
