# 06 Validation Demo And V2 Boundary

## Workstream

`POC 검증, 시연 범위, V2 경계`

## Goal

현재 저장소 기준으로 어떤 방식으로 MVP POC를 검증하고 시연할지 정하고, 자동화와 확장 기능을 V2로 명확히 분리한다.

## Scope

- 최소 시연 흐름
- smoke와 수동 QA 기준
- 현재 단계에서 구현하지 않을 항목 정의
- V2 backlog 경계 정리

## Non-goals

- 운영 자동화 구현
- 완전한 Android 앱 완성
- 계정 동기화 구현

## Source Inputs

- Request: 자동화는 지금 단계에서 제외하고 MVP V2로 분리
- Docs: `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`
- Code or architecture references: `poc/`, `.ai/EVALS/smoke-checklist.md`, `etl/data/raw/`

## Success Criteria

- [ ] 현재 POC에서 시연할 핵심 흐름이 정의된다.
- [ ] smoke와 검증 포인트가 실행 순서에 맞게 정리된다.
- [ ] 자동화와 확장 기능이 V2로 명확히 분리된다.

## Implementation Plan

- [ ] 최소 시연 흐름을 다음 순서로 고정한다.
  - 시설 조회
  - 휠체어 경로 탐색
  - 시각장애 경로 탐색
  - 접근성 대중교통 후보 확인
  - 익명 제보 저장
- [ ] smoke 순서를 `DB 기동 -> OSM 적재 -> CSV/BIMS ETL -> GraphHopper import -> API 호출`로 정리한다.
- [ ] 결과 검증용 샘플 구간과 대표 시설을 정한다.
  - **smoke 기준 좌표**: 출발 `(35.1013, 129.0353)` (중앙동주민센터 — `places` 첫 번째 레코드), 도착 `(35.1023, 129.0318)` (근대역사관 인근 음향신호기).
  - 두 지점 모두 `place_merged_broad_category_final.csv`와 `stg_audio_signals_ready.csv`에 실제 존재하는 데이터이므로 적재 후 바로 검증 가능하다.
  - 지하철 시연 시: ODsay 부산 지하철 1호선 노포역(`stationId` 보강 완료 후) → 서면역 경로 사용.
- [ ] V2로 넘길 항목을 명시한다.
  - ETL 자동 감지/승인 자동화
  - 계정 동기화
  - LLM 대화형 UI
  - 완전한 Android 앱 구현
  - 운영형 캐싱/모니터링 고도화

## Validation Plan

- [ ] 각 단계별 실패 시 어떤 대체 검증을 할지 정리한다.
- [ ] `scripts/smoke.sh`에 실제 프로젝트 명령을 반영할 준비 항목을 정리한다.
- [ ] 시연 중 필수 데이터가 비어 있을 때 설명 가능한 fallback 시나리오를 준비한다.

## Risks and Open Questions

- 현재 프론트 코드가 없어 시연은 API 또는 얇은 검증 UI 중심이 될 수 있다.
- 일부 데이터셋은 공란과 불완전 매핑이 있어 시연 구간을 선별해야 할 수 있다.

## Dependencies

- `01`부터 `05`까지의 구현 산출물

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 팀이 같은 순서로 재현 가능한 시연 흐름과 V2 경계를 공유해야 한다
