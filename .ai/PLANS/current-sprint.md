# Current Sprint

## Goal

최신 `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`와 현재 저장소 상태만으로 부산이음길 MVP POC를 구현 가능한 수준의 실행 계획으로 정리한다. 이번 스프린트는 `docs/plans/` 없이도 진행 가능해야 하며, 기존 `busan.osm.pbf` 선적재 대신 국토교통부 SHP 도로 중심선을 기준 네트워크로 재정의한 뒤 `etl/data/raw`의 CSV와 BIMS API를 통해 접근성·시설·대중교통 참조 데이터를 보강하고, 그 결과를 GraphHopper와 Spring Boot API에 연결하는 순서로 진행한다.

## Request Mode

- Primary mode: spec-driven planning from canonical `docs/`
- Secondary inputs: current repository state, `.env`, `poc/`, `etl/data/raw/`
- Planning rule: `docs/plans/`를 제거해도 구현이 가능하도록 현재 계획은 canonical source 없이 독립적으로 읽혀야 한다

## Structured State

- Narrative plan: this file
- Machine-readable progress: `.ai/PLANS/progress.json`
- Quality and readiness metrics: `.ai/EVALS/metrics.json`
- Workstream subplans: `.ai/PLANS/current-sprint/`

## Checklist Status Rule

- `[ ]` not started
- `[~]` in progress
- `[x]` completed successfully
- `[!]` blocked, risky, or requires strategy change

## Planning Inputs

- Product specs: `docs/prd.md`, `docs/기능명세서.md`
- Data and schema spec: `docs/erd.md`
- Current environment and code:
  - `.env`
  - `poc/`
  - `etl/data/raw/N3L_A0020000_26.shp`
  - `etl/data/raw/N3L_A0020000_26.shx`
  - `etl/data/raw/N3L_A0020000_26.dbf`
  - `etl/data/raw/N3L_A0020000_26.prj`
  - `etl/data/raw/place_merged_broad_category_final.csv`
  - `etl/data/raw/place_accessibility_features_merged_final.csv`
  - `etl/data/raw/stg_audio_signals_ready.csv`
  - `etl/data/raw/stg_crosswalks_ready.csv`
  - `etl/data/raw/slope_analysis_staging.csv`
  - `etl/data/raw/subway_station_elevators_erd_ready.csv`

## Cross-Validation Notes

- PRD의 기술 스택에는 `MySQL`, `Kotlin/Jetpack`, `RabbitMQ`가 적혀 있지만, 최신 ERD는 `GEOMETRY`, `JSONB`, PostGIS 친화 스키마를 전제로 한다. 이번 계획은 최신 ERD와 실제 원시 데이터 형식을 우선하여 `PostgreSQL + PostGIS`를 기준으로 잡는다.
- PRD와 기능명세서는 local-first를 강조하므로, 로그인 기반 사용자 기능은 MVP POC의 핵심 경로가 아니다. `users`, `bookmarks`, `favorite_routes`는 테이블 설계는 유지하되 구현 우선순위는 뒤로 둔다.
- 최신 ERD는 저상버스 예약 API를 만들지 않고 외부 화면 연동을 전제로 한다. 따라서 MVP의 대중교통 구현은 `low_floor_bus_routes` 적재와 경로 후보 필터링에 집중한다.
- `subway_station_elevators_erd_ready.csv`는 실제 확인 결과 ERD와 동일한 6개 컬럼(`elevatorId`, `stationId`, `stationName`, `lineName`, `entranceNo`, `point`)만 가진 적재 준비본이다. 231건, `stationId`/`point` 공란 0건이므로 별도 보강 단계를 전제하지 않고 바로 적재하는 기준으로 계획한다.
- 같은 `stationId + entranceNo + point` 조합의 중복 레코드가 일부 존재하므로, ETL은 raw row를 그대로 적재하기보다 중복 제거 또는 사전 검증 단계를 포함해야 한다.
- `lineName` 값은 현재 `1`, `2`, `3`, `4`만 존재하므로 이번 MVP 엘리베이터 범위는 부산 도시철도 1~4호선 기준으로 명시한다. 동해선, 부산김해경전철까지 보장하는 계획은 현재 데이터셋만으로는 세우지 않는다.
- `slope_analysis_staging.csv`는 세그먼트 수준 결과가 아니라 폴리곤 기반 staging 성격이 강하므로, `road_segments`와의 공간 매칭 단계가 ETL 핵심이다. 좌표계는 EPSG:5179(한국 TM)와 WGS84 두 컬럼이 모두 제공되며, ETL은 반드시 `geometry_wkt_4326` 컬럼을 사용해야 한다. `avgSlopePercent` 소스 컬럼은 `metric_mean`이다.
- 자동화는 MVP V2로 미루고, 이번 스프린트는 수동 실행 가능하고 재실행 안전한 ETL과 구현 순서 정리에 집중한다.

## Success Criteria

- [ ] `docs/plans/` 없이도 어떤 순서로 구현할지 `.ai/PLANS`만 보고 따라갈 수 있다.
- [x] `docs/plans/` 없이도 어떤 순서로 구현할지 `.ai/PLANS`만 보고 따라갈 수 있다.
- [ ] OSM 선적재 후 CSV/BIMS 기반 보강 적재 순서와 책임 테이블이 명확하다.
- [ ] `etl/data/raw` 각 파일이 어떤 테이블과 컬럼을 채우는지, 그리고 point/polygon이 기존 `road_segments.geom`에 어떻게 매칭되는지 계획에 명시되어 있다.
- [ ] GraphHopper import 시 custom encoded value와 4개 custom model을 추가하는 구현 방향이 정리되어 있다.
- [ ] 데이터셋이 아직 완전하지 않은 POC 상태를 고려한 유연한 기준과, 원래 엄격한 기준을 주석으로 유지하는 전략이 반영되어 있다.
- [ ] 현재 `poc/` 기반 Spring Boot 구조에서 구현해야 할 API와 검증 흐름이 단계화되어 있다.

## Workstream Index

- [ ] [01-setup-and-repo-alignment.md](.ai/PLANS/current-sprint/01-setup-and-repo-alignment.md)
- [x] [01-setup-and-repo-alignment.md](.ai/PLANS/current-sprint/01-setup-and-repo-alignment.md)
- [~] [02-osm-schema-and-network-load.md](.ai/PLANS/current-sprint/02-osm-schema-and-network-load.md)
- [~] [03-csv-etl-and-reference-data.md](.ai/PLANS/current-sprint/03-csv-etl-and-reference-data.md)
- [ ] [04-graphhopper-routing-profiles.md](.ai/PLANS/current-sprint/04-graphhopper-routing-profiles.md)
- [ ] [05-backend-api-and-orchestration.md](.ai/PLANS/current-sprint/05-backend-api-and-orchestration.md)
- [ ] [06-validation-demo-and-v2-boundary.md](.ai/PLANS/current-sprint/06-validation-demo-and-v2-boundary.md)

Validation note on 2026-04-23: the previous OSM snapshot validation remains available only as legacy evidence. Workstream `02` has been reopened because the canonical network source is shifting from `busan.osm.pbf` to `N3L_A0020000_26` SHP, which requires a source-agnostic schema and a new `edgeId` handoff contract.

Validation note on 2026-04-22: Workstream `03` was reloaded on a fresh canonical `schema.sql` database after retiring the legacy snake_case Postgres target on `localhost:5432`. The current canonical counts are `places=13,564`, `place_accessibility_features=42,368`, `segment_features=120,357`, `subway_station_elevators=203`, and `low_floor_bus_routes=146` with `118` rows where `hasLowFloor = true`.
Validation note on 2026-04-22: Workstream `03` now also enriches `road_segments.elevatorState` from `subway_station_elevators`, producing `102` `SUBWAY_ELEVATOR` features and `86` segments tagged `elevatorState=YES`. The workstream remains in progress because the documented `15m~30m` segment tie-break rule and audio `NO` propagation are still not implemented.

Implementation guard for real service: all downstream ETL, GraphHopper import, and verification flows must use the same canonical `edgeId` handoff contract, and the network load stage must stay split as `preflight -> extract -> topology-audit -> load-db` so schema drift or graph connectivity defects fail before long-running downstream work is wasted.

## Ordered Delivery Plan

1. `01`에서 저장소 구조, DB 선택, 실행 경로를 고정한다.
2. `02`에서 PostGIS 스키마를 source-agnostic 형태로 바꾸고 `N3L_A0020000_26` SHP를 `road_nodes`, `road_segments`에 적재한다.
3. `03`에서 CSV와 BIMS API로 `places`, `place_accessibility_features`, `road_segments`, `segment_features`, `subway_station_elevators`, `low_floor_bus_routes`를 보강 적재한다.
4. `04`에서 GraphHopper import, custom encoded values, 4개 custom model과 분기 로직을 구현한다.
5. `05`에서 Spring Boot API와 대중교통 오케스트레이션을 붙인다.
6. `06`에서 POC 검증 흐름, smoke, 시연 범위와 V2 경계를 정리한다.

## Think

- [ ] MVP POC의 핵심은 `경로 탐색`, `시설 조회`, `익명 제보`, `접근성 데이터 적재`로 고정한다.
- [x] 사용자 유형은 `VISUAL`, `MOBILITY` 두 축으로 고정한다.
- [x] 경로 옵션은 `SAFE_WALK`, `FAST_WALK`, `ACCESSIBLE_TRANSIT`으로 고정한다.
- [ ] 운영 자동화와 완전한 계정 기능은 V2로 분리한다.

## Plan

- [x] PostGIS 중심 스키마와 current repo 구조를 정렬한다.
- [x] ETL을 `OSM 선적재 -> CSV/BIMS 보강 적재 -> GraphHopper import` 순서로 정의한다.
- [ ] 데이터 부족 상태에서는 유연한 POC 기준을 적용하고, 원래 엄격 기준은 주석으로 남기는 전략을 확정한다.
- [ ] API와 검증 시나리오를 구현 순서에 맞춰 끊는다.

## Build

- [ ] DB 스키마와 OSM 적재기를 구현한다.
- [~] CSV/BIMS ETL을 구현한다.
- [ ] GraphHopper 플러그인과 custom model을 구현한다.
- [ ] Spring Boot API와 검증용 UI 또는 시연 흐름을 구현한다.

## Review

- [ ] 최신 ERD와 실제 적재 대상 컬럼 사이 불일치를 점검한다.
- [ ] 공간 매칭 ETL이 과도하게 추정에 의존하지 않는지 점검한다.
- [ ] GraphHopper 분기 기준이 현재 데이터 가용성에 맞는지 점검한다.

## Test

- [x] 문서 변경 후 `scripts/verify.sh`를 통과한다.
- [ ] OSM 적재, CSV 적재, GraphHopper import, API 호출 순서의 smoke를 정의한다.
- [ ] 휠체어 경로, 시각장애 경로, 시설 조회, 저상버스 필터링, 익명 제보의 핵심 시나리오를 검증한다.

## Ship

- [ ] 로컬 실행 순서를 runbook 수준으로 정리한다.
- [ ] 시연용 최소 데이터 범위와 실패 시 대체 경로를 정리한다.

## Reflect

- [ ] 반복 보정이 필요한 공간 매칭 규칙은 `.ai/MEMORY/` 또는 `.ai/EVALS/`로 승격한다.
- [ ] V2로 미뤄진 자동화와 운영 기능은 backlog로 격리한다.

## Risks and Open Questions

- [ ] `subway_station_elevators_erd_ready.csv`의 실제 헤더와 중복 규칙이 적재 계획에 반영된다.
- [ ] `slope_analysis_staging.csv`는 용량이 크고 폴리곤 기반이라 공간 조인 비용이 높을 수 있다.
- [ ] `stg_audio_signals_ready.csv`, `stg_crosswalks_ready.csv`는 포인트 feature라 `road_segments` 업데이트 기준 반경과 우선순위가 필요하다.
- [ ] PRD의 플랫폼 기술 서술과 현재 저장소 구현 상태가 다르므로, MVP POC는 현재 리포 기준 웹/API 우선 검증이 현실적이다.
- [ ] `place_merged_final.csv`와 `place_merged_broad_category_final.csv` 두 파일이 `etl/data/raw/`에 모두 존재하며 헤더가 동일하다. 실제 행 수를 비교해 `place_merged_broad_category_final.csv`로 단일화 여부를 확인해야 한다.
- [ ] `poc/build.gradle`에 Hibernate Spatial이 없으므로 GEOMETRY 컬럼을 JPA 엔티티로 매핑하려면 의존성 추가가 필수다.
- [ ] `docker-compose.yml`이 없으므로 PostGIS와 GH 컨테이너 설정이 구현 착수 전 선행 작업이다.
- [x] `docker-compose.yml`이 없으므로 PostGIS와 GH 컨테이너 설정이 구현 착수 전 선행 작업이다.
- [x] 표준 호스트 포트 `5432`, `8080`은 기존 로컬 스택이 사용 중이므로, stage-01 컨테이너 검증은 `25432`, `28080`, `28989` 임시 포트로 수행했다.
- [ ] GraphHopper custom encoded value는 Java SPI 플러그인을 별도 모듈(`graphhopper-plugin/`)로 작성해야 한다. 이 모듈은 현재 `poc/`에 없다.
