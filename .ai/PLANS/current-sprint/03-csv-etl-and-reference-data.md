# 03 CSV ETL And Reference Data

## Workstream

`CSV 및 BIMS 기반 보강 적재`

## Goal

`etl/data/raw`의 CSV와 BIMS API를 읽어 핵심 시설, 접근성, 세그먼트 보강, 지하철 엘리베이터, 저상버스 참조 데이터를 DB에 반영한다.

## Scope

- 장소 CSV 적재
- 접근성 feature CSV 적재
- 세그먼트 공간 매칭 ETL
- 지하철 엘리베이터 적재
- BIMS 기반 저상버스 참조 테이블 적재

## Non-goals

- 운영 자동화
- GraphHopper 분기 로직 구현
- 전체 API 구현

## Source Inputs

- Request: 원시 CSV를 읽고 어떤 ETL 설계가 필요한지 계획에 반영
- Docs: `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`
- Code or architecture references:
  - `etl/data/raw/place_merged_broad_category_final.csv`
  - `etl/data/raw/place_accessibility_features_merged_final.csv`
  - `etl/data/raw/stg_audio_signals_ready.csv`
  - `etl/data/raw/stg_crosswalks_ready.csv`
  - `etl/data/raw/slope_analysis_staging.csv`
  - `etl/data/raw/subway_station_elevators_erd_ready.csv`
  - `.env`

## Success Criteria

- [ ] 각 CSV가 어느 테이블과 컬럼을 채우는지 명시된다.
- [ ] `road_segments`와 `segment_features` 보강 ETL 설계가 정의된다.
- [ ] `low_floor_bus_routes`는 BIMS API 기반 적재 전략이 정의된다.
- [ ] 품질이 미완성인 데이터셋에 대한 보강 또는 기본값 전략이 정리된다.

## Current Status

- 2026-04-22 validation rerun completed `02_places_load.py`, `03_accessibility_features_load.py`, `04_segment_features_load.py`, `05_subway_elevators_load.py`, and `06_bims_bus_load.py` end-to-end against the local Postgres target.
- Verified counts after rerun: `places=13,564`, `place_accessibility_features=42,368`, `segment_features=120,357`, `subway_station_elevators=203`, `low_floor_bus_routes=290`.
- The `06_bims_bus_load.py` hang was fixed by switching `busInfo` ingestion to a single fetch. The current Busan BIMS `busInfo` endpoint ignores `pageNo`, so paginated loops never terminate.
- Workstream `03` remains blocked, not completed. The current BIMS payload exposes `bustype` only and does not expose a reliable low-floor indicator field, so the rerun loaded `low_floor_bus_routes=290` with `hasLowFloor=true` rows equal to `0`.
- To close `03`, the team needs a confirmed source or derivation rule for `hasLowFloor` that is valid for real service operation.

## Implementation Plan

- [ ] `place_merged_broad_category_final.csv`를 `places`에 적재한다.
  - `placeId -> placeId`
  - `name -> name`
  - `category -> category`
  - `address -> address`
  - `point -> point`
  - `providerPlaceId -> providerPlaceId`
- [ ] `place_accessibility_features_merged_final.csv`를 `place_accessibility_features`에 적재한다.
  - `id -> id`
  - `placeId -> placeId`
  - `featureType -> featureType`
  - `isAvailable -> isAvailable`
- [ ] `stg_audio_signals_ready.csv`는 각 `point`가 포함되는 기존 `road_segments.geom` 레코드를 찾아 `road_segments.audioSignalState`를 업데이트한다.
  - **CSV 실제 헤더**: `sourceId, sigungu, location, address, point, lat, lng, audioSignalState, stat, place, confirmDate`
  - `stat` 컬럼이 `정상동작`인 레코드만 `audioSignalState=YES`로 업데이트하고, 나머지(`고장`, 빈값 등)는 업데이트하지 않는다.
  - `audioSignalState` 컬럼에 이미 `YES/NO` 값이 들어 있으므로 CSV 값을 그대로 사용한다.
  - 공간 조건은 `ST_DWithin(road_segments.geom, csv.point::geometry, 0.00015)` (약 15m)를 기준으로 가장 가까운 세그먼트 1개에 귀속시킨다.
  - 원천 레코드는 `segment_features`에 `featureType='AUDIO_SIGNAL'`, `geom=POINT(...)`로 그대로 저장한다.
- [ ] `stg_crosswalks_ready.csv`는 각 `point`가 속하는 기존 `road_segments.geom` 레코드를 찾아 `road_segments.crossingState`를 업데이트한다.
  - **CSV 실제 헤더**: `sourceId, districtGu, districtDong, locationLabel, point, lat, lng, widthMeter, lengthMeter, areaSquareMeter, crossingState`
  - `crossingState` 컬럼이 이미 `TRAFFIC_SIGNALS` 등 값으로 있으므로 CSV 값을 그대로 사용한다.
  - `segment_features`에는 `featureType='CROSSWALK'`, `geom=POINT(...)`로 그대로 저장한다.
  - `point`가 공란인 레코드는 적재 대상에서 제외한다 (적재 전 `point IS NULL OR point = ''` 필터).
  - `widthMeter`는 `slope_analysis_staging.csv`가 값을 채우지 않은 `road_segments`에 한해서만 보조 업데이트 대상으로 사용한다.
- [ ] `slope_analysis_staging.csv`는 polygon-to-line 공간 매칭으로 기존 `road_segments.geom`와 겹치는 레코드를 찾아 `road_segments.avgSlopePercent`, `widthMeter`, 필요 시 `stairsState` 보조 판단값을 업데이트한다.
  - **CSV 실제 헤더 (주요)**: `source_type, width_meter, metric_mean, metric_max, metric_min, stairs_data_status, stairs_source, geometry_wkt, geometry_wkt_4326`
  - **좌표계 주의**: `geometry_wkt`는 EPSG:5179 (한국 TM), `geometry_wkt_4326`은 WGS84. **반드시 `geometry_wkt_4326` 컬럼을 사용한다.** `pyproj` 불필요.
  - `avgSlopePercent` 매핑: CSV의 `metric_mean` 컬럼을 사용한다 (경사도 평균값).
  - `widthMeter` 매핑: CSV의 `width_meter` 컬럼을 사용한다 (공란이 많으므로 NULL 허용).
  - 공간 매칭: `ST_Intersects(road_segments.geom, slope_polygon::geometry)`로 겹치는 세그먼트 전체에 적용한다.
  - `segment_features`에는 `featureType='SLOPE_ANALYSIS'`으로 `geom=MULTIPOLYGON(...)` (geometry_wkt_4326)을 그대로 저장한다.
  - `widthMeter`는 `slope_analysis_staging.csv` 값을 우선한다. `stg_crosswalks_ready.csv`는 이 단계에서 채워지지 않은 `widthMeter`에 대해서만 보조 업데이트를 수행한다.
  - `stairs_data_status`가 `MISSING_SOURCE`인 경우 계단 판단은 확정하지 않고 보수적으로 `UNKNOWN` 유지가 기본이다.
- [ ] `subway_station_elevators_erd_ready.csv`를 `subway_station_elevators`에 적재한다.
  - **CSV 실제 헤더**: `elevatorId, stationId, stationName, lineName, entranceNo, point`
  - 실제 확인 결과 총 231건이며 `stationId`, `point` 공란은 0건이다. 따라서 “팀원 보강 완료본 대기” 전제는 제거한다.
  - `lineName` 값은 `1`, `2`, `3`, `4`만 존재하므로 MVP 보장 범위는 부산 도시철도 1~4호선으로 명시한다.
  - 같은 `stationId + entranceNo + point` 조합의 중복 레코드가 일부 존재하므로, 적재 전 중복 검출 리포트를 만들고 기본 적재 규칙을 `SELECT DISTINCT` 또는 staging dedupe로 고정한다.
  - 현재 계획에서는 CSV의 6개 컬럼을 ERD 컬럼에 그대로 적재한다.
  - `isOperating` 컬럼이 없으므로 ETL과 오케스트레이션 어디에서도 운영 상태 필터를 사용하지 않는다.
- [ ] `low_floor_bus_routes`는 BIMS API 호출로 적재한다.
  - `.env`의 `BUSAN_BIMS_*` 값을 사용한다.
  - routeId, routeNo, hasLowFloor를 정규화해 저장한다.
- [ ] 적재 순서는 `places -> place_accessibility_features -> road_segments/segment_features 보강 -> subway_station_elevators -> low_floor_bus_routes`로 유지한다.
- [ ] ETL 매칭 거리 규칙은 DB 필드가 아니라 ETL 내부 규칙으로만 유지한다.
  - `<= 15m`: update
  - `15m ~ 30m`: update 여부는 속성별로 결정
  - `> 30m`: skip, `UNKNOWN` 유지

## Validation Plan

- [ ] 각 CSV의 헤더와 ERD 컬럼 간 누락/추가 컬럼을 점검한다.
- [ ] 공간 매칭 반경, 우선순위, 다중 매칭 충돌 규칙을 점검한다.
- [ ] `subway_station_elevators_erd_ready.csv`는 적재 전 `stationId`, `point` 누락 0건과 중복 조합 존재 여부를 검증한다.
- [ ] 적재 후 대표 샘플 구간에 대해 `road_segments`와 `segment_features`가 함께 채워지는지 확인한다.

## Risks and Open Questions

- `slope_analysis_staging.csv`는 세그먼트 직접 키가 없어 공간 매칭 성능과 정확도 모두 검증이 필요하다.
- `stg_audio_signals_ready.csv`와 `stg_crosswalks_ready.csv`는 포인트 feature라 교차로 인접 세그먼트 중 어떤 세그먼트에 귀속시킬지 기준이 필요하다.
- `subway_station_elevators_erd_ready.csv`는 누락보다 중복 관리가 핵심 리스크다. 동일 출입구/좌표 중복을 그대로 적재하면 역별 엘리베이터 수와 최근접 선택 로직이 왜곡될 수 있다.
- 현재 CSV는 `lineName`이 1~4호선만 포함하므로, 동해선/경전철 엘리베이터 접근성을 요구하는 시나리오는 이번 범위에서 제외하거나 별도 데이터 확보가 필요하다.
- surface/curb_ramp/elevator 등 후속 데이터셋이 추가되면 현재 POC 규칙과 충돌 없이 동일한 confidence 체계에 편입돼야 한다.

## Additional Blocker

- Busan BIMS `busInfo` currently returns `bustype` categories such as `일반버스`, `마을버스`, and `급행버스`, but no explicit low-floor flag. The service needs either a different endpoint, a second reference source, or an approved derivation rule before `low_floor_bus_routes.hasLowFloor` can be trusted.

## Dependencies

- `02`에서 생성한 `road_segments`와 공간 인덱스
- BIMS API 접속 정보

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: GraphHopper와 백엔드가 바로 사용할 수 있도록 ETL 결과가 재실행 가능하고 추적 가능해야 한다

## Hardening Notes For Real Service

- Downstream CSV ETL must not re-identify `road_segments` with the 3-column source key. The canonical segment identity is `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`.
- After spatial matching picks a target segment, the ETL should switch to `edgeId` immediately and use that key for updates and for `segment_features.edgeId`.
- CSV ETL may enrich accessibility attributes, but it must not rewrite OSM segment identity columns. Treat `sourceWayId`, `sourceOsmFromNodeId`, `sourceOsmToNodeId`, and `segmentOrdinal` as immutable.
- Matching should be implemented as `candidate search -> ranking -> final assignment`, not as a single update query with hidden tie-breaking.
- Every ETL run should emit a small matching report with: source row count, geometry parse failure count, unmatched count, multi-candidate conflict count, update count, and `segment_features` insert count.
