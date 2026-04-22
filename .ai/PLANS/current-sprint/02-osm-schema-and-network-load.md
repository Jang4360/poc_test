# 02 OSM Schema And Network Load

## Workstream

`OSM 원천 데이터 기반 보행 네트워크 생성`

## Goal

`busan.osm.pbf`를 먼저 적재해 `road_nodes`와 `road_segments`를 만들고, 이후 CSV ETL과 GraphHopper가 공통으로 참조할 기준 테이블을 준비한다.

## Scope

- PostGIS 스키마 생성
- `road_nodes`, `road_segments`, `segment_features` 기본 구조 생성
- OSM way 필터링, anchor node 규칙, segment 분해 규칙 구현
- OSM parsing과 DB load를 분리한 적재 흐름 구현
- 이후 CSV ETL과 GraphHopper가 재사용할 수 있는 식별자와 인덱스 고정

## Non-goals

- CSV 보강 ETL
- GraphHopper import
- BIMS 참조 데이터 적재

## Source Inputs

- Request: OSM 데이터를 먼저 DB에 적재하고 이후 ETL로 보강
- Docs: `docs/prd.md`, `docs/erd.md`
- Code and data references:
  - `etl/data/raw/busan.osm.pbf`
  - `etl/sql/schema.sql`
  - `etl/scripts/01_osm_load.py`

## Success Criteria

- [x] PostGIS 기준 테이블이 생성된다.
- [x] `busan.osm.pbf`에서 `road_nodes`, `road_segments`가 적재된다.
- [x] OSM way 필터, anchor node 규칙, segment 분해 규칙이 코드로 고정된다.
- [x] 이후 CSV ETL이 사용할 초기 상태와 식별 규칙이 정리된다.

## What This Workstream Implements

- `road_nodes` 생성
  - anchor node만 vertex로 채택
  - `vertexId`, `osmNodeId`, `point` 생성
- `road_segments` 생성
  - walkable OSM way만 포함
  - anchor node 기준으로 segment 분해
  - `fromNodeId`, `toNodeId`, `geom`, `lengthMeter`, source OSM 식별자 저장
- 스키마/제약/인덱스 정의
  - `road_nodes("osmNodeId")` unique
  - `road_segments("geom")` GIST index
  - `road_segments` natural key 고정
- ETL 실행 구조 분리
  - `--preflight-only`
  - `--parse-only`
  - `--load-snapshot`

## Key Design Decisions

- OSM parser: `pyosmium`
- 적재 구조: `preflight -> parse-only snapshot -> load-snapshot`
- canonical segment identity:
  - `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`
- `edgeId`는 내부 surrogate key로 유지
- `road_segments`는 이후 CSV ETL과 GraphHopper import의 source of truth

## Implementation Plan

- [x] `etl/sql/schema.sql`에 PostGIS 테이블, 제약, 인덱스를 정의한다.
- [x] `etl/scripts/01_osm_load.py`에 walkable way 필터와 anchor node 규칙을 구현한다.
- [x] OSM way를 anchor 기준으로 분해해 `road_segments`를 만든다.
- [x] `road_nodes`와 `road_segments`에 bulk insert를 적용한다.
- [x] ETL 시작 전에 DB preflight를 수행한다.
- [x] `parse-only`와 `load-snapshot`를 분리한다.
- [x] `parse-only`를 child-process snapshot flow로 바꿔 parser teardown 문제를 격리한다.
- [x] natural key를 4컬럼으로 고정해 실제 OSM loop 케이스를 보존한다.

## Validation Plan

- [x] 단위 테스트 통과
- [x] DB preflight 통과
- [x] `parse-only`가 lingering Python process 없이 종료
- [x] `load-snapshot --truncate`로 적재 성공
- [x] geometry invalid row 0건 확인
- [x] 4컬럼 natural key duplicate row 0건 확인
- [x] snapshot segment count와 DB 적재 count 일치 확인

## Current Status

- Status: completed for the current POC scope on 2026-04-22
- Main deliverables:
  - `etl/sql/schema.sql`
  - `etl/scripts/01_osm_load.py`
  - `etl/tests/test_osm_load.py`
- Validation evidence:
  - `road_nodes`: 96,169
  - `road_segments`: 115,080
  - invalid geometries: 0
  - duplicate 4-column natural-key rows: 0

## Hardening Notes For Real Service

- 실제 서비스에서도 3컬럼 source key로 되돌아가지 않는다.
  - canonical key는 `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`이다.
- 장시간 parsing과 DB insert를 한 프로세스에 섞지 않는다.
  - `parse-only`는 snapshot과 completion marker만 만든다.
  - `load-snapshot`만 DB mutate를 담당한다.
- 성공 기준은 단순 프로세스 종료가 아니라 snapshot과 marker durability까지 포함한다.
- DB drift는 볼륨 삭제가 아니라 migration으로 해결한다.
  - 로컬 disposable DB만 볼륨 재생성 허용
  - 서비스/공유 환경은 명시적 constraint and index migration 사용
- Validation은 적재 성공 여부만 보지 않고 정합성까지 본다.
  - snapshot count vs DB count
  - 4컬럼 natural key uniqueness
  - geometry validity

## Dependencies

- PostGIS 실행 환경
- `etl/data/raw/busan.osm.pbf`

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: `road_segments`가 이후 CSV ETL과 GraphHopper import의 안정적인 기준 테이블이어야 한다.
