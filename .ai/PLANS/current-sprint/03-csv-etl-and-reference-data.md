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

- 2026-04-22 canonical DB bootstrap completed from `etl/sql/schema.sql` after stopping the legacy snake_case container on `localhost:5432` and recreating `poc_test-postgresql-1` with a fresh Postgres volume.
- Validation on the canonical camelCase DB now shows the intended tables and counts: `road_nodes=96,169`, `road_segments=115,080`, `places=13,564`, `place_accessibility_features=42,368`, `segment_features=120,357`, `subway_station_elevators=203`, `low_floor_bus_routes=146`, and `hasLowFloor=true` rows `=118`.
- `04_segment_features_load.py` completed on the canonical DB with `audio_signal_features=1,000`, `crosswalk_features=2,072`, `slope_features=117,285`, `audioSegmentsYes=248`, `crossingSegmentsTagged=1,841`, `avgSlopePercent tagged=34,871`, and `widthMeter tagged=35,904`.
- 2026-04-22 elevator-to-segment enrichment is now implemented on the canonical DB: `subway_elevator_features=102`, `elevatorSegmentsTagged=86`, `review_required=63`, `unmatched=66`. `stairsState` remains `UNKNOWN` because no source dataset for that attribute is loaded in this workstream.
- Workstream `03` is no longer blocked on low-floor source derivation. The remaining open work is implementation hardening: the documented `15m~30m` tie-break rule is still not implemented for audio/crosswalk datasets, audio `NO` is still not written back, and elevator `15m~30m` candidates are currently report-only without a manual review flow.
- 2026-04-22 implemented the planned static `low_floor_bus_routes` ETL slice in `06_bims_bus_load.py`: cp949 CSV aggregation by `인가노선`, exact-string `buslinenum -> lineid` mapping, unmatched hard-fail policy, and JSON report output under `etl/reports/`.
- Validation on 2026-04-22: `python3 -m unittest etl.tests.test_reference_loads` passed, and `06_bims_bus_load.py --dry-run --csv '/Users/jangjooyoon/Downloads/부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv'` validated `source_rows=2511`, `distinct_routes=146`, `matched_routes=146`, `unmatched_routes=0`, `low_floor_routes=118`.
- 2026-04-22 follow-up hardening: `06_bims_bus_load.py` now writes `status=dry_run|upserted|failed` into the JSON report, writes failure reports only after the actual outcome is known, and allows `--dry-run` to complete even when unmatched routes exist so the operator can inspect the report before deciding whether to skip or block.
- The earlier local DB blocker (`FATAL: role "ieumgil" does not exist`) was resolved by retiring the conflicting legacy Postgres target on `localhost:5432` and recreating the canonical local database from `etl/sql/schema.sql`.
- 2026-04-23 added a raw-PBF slope validation artifact: `etl/scripts/07_slope_match_visualize.py` now writes `runtime/etl/slope-match-v2-hotspots.html`, overlaying v2-eligible OSM edges with `slope_analysis_staging.csv` polygons and coloring them as `matched`, `review` (v2-only), or `unmatched` for manual map inspection.
- 2026-04-23 added a focused Centum City diagnostic: `etl/scripts/08_unmatched_v2_edges_centum_visualize.py` writes `runtime/etl/centum-unmatched-v2-edges.html`, showing only the v2-eligible OSM edges in the Centum City bbox that still do not intersect any slope polygon.
- 2026-04-23 added a SHP-based comparison diagnostic: `etl/scripts/09_shp_roads_visualize.py` renders a Leaflet HTML directly from 국토교통부 road-centerline SHP inputs such as `N3L_A0020000_26.shp`, making it possible to compare OSM-derived walkable edges against the official road-centerline geometry around Jangsan or other hotspots without rebuilding the DB.

## Implementation Plan

- [x] `place_merged_broad_category_final.csv`를 `places`에 적재한다.
  - `placeId -> placeId`
  - `name -> name`
  - `category -> category`
  - `address -> address`
  - `point -> point`
  - `providerPlaceId -> providerPlaceId`
- [x] `place_accessibility_features_merged_final.csv`를 `place_accessibility_features`에 적재한다.
  - `id -> id`
  - `placeId -> placeId`
  - `featureType -> featureType`
  - `isAvailable -> isAvailable`
- [x] `stg_audio_signals_ready.csv`는 각 `point`가 포함되는 기존 `road_segments.geom` 레코드를 찾아 `road_segments.audioSignalState`를 업데이트한다.
  - **CSV 실제 헤더**: `sourceId, sigungu, location, address, point, lat, lng, audioSignalState, stat, place, confirmDate`
  - `stat` 컬럼이 `정상동작`인 레코드만 `audioSignalState=YES`로 업데이트하고, 나머지(`고장`, 빈값 등)는 업데이트하지 않는다.
  - `audioSignalState` 컬럼에 이미 `YES/NO` 값이 들어 있으므로 CSV 값을 그대로 사용한다.
  - 공간 조건은 `ST_DWithin(road_segments.geom, csv.point::geometry, 0.00015)` (약 15m)를 기준으로 가장 가까운 세그먼트 1개에 귀속시킨다.
  - 원천 레코드는 `segment_features`에 `featureType='AUDIO_SIGNAL'`, `geom=POINT(...)`로 그대로 저장한다.
- [x] `stg_crosswalks_ready.csv`는 각 `point`가 속하는 기존 `road_segments.geom` 레코드를 찾아 `road_segments.crossingState`를 업데이트한다.
  - **CSV 실제 헤더**: `sourceId, districtGu, districtDong, locationLabel, point, lat, lng, widthMeter, lengthMeter, areaSquareMeter, crossingState`
  - `crossingState` 컬럼이 이미 `TRAFFIC_SIGNALS` 등 값으로 있으므로 CSV 값을 그대로 사용한다.
  - `segment_features`에는 `featureType='CROSSWALK'`, `geom=POINT(...)`로 그대로 저장한다.
  - `point`가 공란인 레코드는 적재 대상에서 제외한다 (적재 전 `point IS NULL OR point = ''` 필터).
  - `widthMeter`는 `slope_analysis_staging.csv`가 값을 채우지 않은 `road_segments`에 한해서만 보조 업데이트 대상으로 사용한다.
- [x] `slope_analysis_staging.csv`는 polygon-to-line 공간 매칭으로 기존 `road_segments.geom`와 겹치는 레코드를 찾아 `road_segments.avgSlopePercent`, `widthMeter`, 필요 시 `stairsState` 보조 판단값을 업데이트한다.
  - **CSV 실제 헤더 (주요)**: `source_type, width_meter, metric_mean, metric_max, metric_min, stairs_data_status, stairs_source, geometry_wkt, geometry_wkt_4326`
  - **좌표계 주의**: `geometry_wkt`는 EPSG:5179 (한국 TM), `geometry_wkt_4326`은 WGS84. **반드시 `geometry_wkt_4326` 컬럼을 사용한다.** `pyproj` 불필요.
  - `avgSlopePercent` 매핑: CSV의 `metric_mean` 컬럼을 사용한다 (경사도 평균값).
  - `widthMeter` 매핑: CSV의 `width_meter` 컬럼을 사용한다 (공란이 많으므로 NULL 허용).
  - 공간 매칭: `ST_Intersects(road_segments.geom, slope_polygon::geometry)`로 겹치는 세그먼트 전체에 적용한다.
  - `segment_features`에는 `featureType='SLOPE_ANALYSIS'`으로 `geom=MULTIPOLYGON(...)` (geometry_wkt_4326)을 그대로 저장한다.
  - `widthMeter`는 `slope_analysis_staging.csv` 값을 우선한다. `stg_crosswalks_ready.csv`는 이 단계에서 채워지지 않은 `widthMeter`에 대해서만 보조 업데이트를 수행한다.
  - `stairs_data_status`가 `MISSING_SOURCE`인 경우 계단 판단은 확정하지 않고 보수적으로 `UNKNOWN` 유지가 기본이다.
- [x] `subway_station_elevators_erd_ready.csv`를 `subway_station_elevators`에 적재한다.
  - **CSV 실제 헤더**: `elevatorId, stationId, stationName, lineName, entranceNo, point`
  - 실제 확인 결과 총 231건이며 `stationId`, `point` 공란은 0건이다. 따라서 “팀원 보강 완료본 대기” 전제는 제거한다.
  - `lineName` 값은 `1`, `2`, `3`, `4`만 존재하므로 MVP 보장 범위는 부산 도시철도 1~4호선으로 명시한다.
  - 같은 `stationId + entranceNo + point` 조합의 중복 레코드가 일부 존재하므로, 적재 전 중복 검출 리포트를 만들고 기본 적재 규칙을 `SELECT DISTINCT` 또는 staging dedupe로 고정한다.
  - 현재 계획에서는 CSV의 6개 컬럼을 ERD 컬럼에 그대로 적재한다.
  - `isOperating` 컬럼이 없으므로 ETL과 오케스트레이션 어디에서도 운영 상태 필터를 사용하지 않는다.
- [x] `subway_station_elevators_erd_ready.csv`의 `point`를 기존 `road_segments.geom`에 공간 매칭해 `road_segments.elevatorState`를 보강한다.
  - 이 단계의 의미는 “지하철역 엘리베이터 출입구에 직접 접속 가능한 보행 세그먼트”를 `elevatorState=YES`로 표시하는 것이다. `subway_station_elevators` 원천 포인트 전체를 곧바로 역 주변 모든 세그먼트에 확장하지 않는다.
  - 매칭 후보는 `ST_DWithin(road_segments.geom, elevator.point, 15m)` 이내 세그먼트로 제한한다.
  - 1차 규칙: `<= 15m`에서 가장 가까운 세그먼트 1개를 기본 대상로 선택한다.
  - 2차 규칙: 동일 거리 또는 거의 동일한 후보가 여러 개면 `candidate search -> ranking -> final assignment` 흐름을 사용하고, tie-break는 `distance ASC`, `lengthMeter ASC`, `edgeId ASC` 순으로 고정한다.
  - `15m ~ 30m`는 자동 업데이트하지 않고 `review_required` 리포트로만 남긴다. 이 구간은 후속 구현에서 수동 점검 또는 별도 alias 규칙이 승인되기 전까지 `UNKNOWN` 유지가 기본이다.
  - `> 30m` 또는 후보 없음은 skip 하고 `elevatorState`를 변경하지 않는다.
  - `road_segments.elevatorState`는 `YES`만 명시적으로 업데이트한다. 음수 근거가 없으므로 `NO`를 대량 기록하지 않는다.
  - 원천 포인트는 `segment_features`에 `featureType='SUBWAY_ELEVATOR'`, `geom=POINT(...)`로 함께 기록한다.
  - 하나의 엘리베이터 포인트가 이미 `YES`로 마킹된 같은 세그먼트에 다시 매칭되면 중복 insert 대신 idempotent upsert 또는 dedupe로 처리한다.
  - 이 단계는 `05_subway_elevators_load.py`와 분리된 후속 ETL 슬라이스로 구현한다. 이유는 원천 적재와 공간 보강의 실패 원인과 재실행 조건이 다르기 때문이다.
- [x] `low_floor_bus_routes`는 정적 CSV를 주 소스로 적재하고, BIMS는 `routeId` 매핑과 실시간 보조 근거로만 사용한다.
  - **정적 주 소스 파일**: `부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv`
  - **실제 헤더 / 인코딩**: `운수사, 인가노선, 차량번호, 운행구분, 상용구분, 차량구분, 연료, 연식` / `cp949`
  - CSV는 차량 단위 데이터이므로 `인가노선`을 `routeNo`로 보고 노선 단위로 집계한다.
  - `hasLowFloor` 집계 규칙은 `같은 routeNo의 차량 중 운행구분='저상'이 1대라도 있으면 true`로 고정한다.
  - `운행구분='일반'|'고급'|'좌석'`만 존재하는 노선은 `hasLowFloor=false`로 적재한다.
  - `routeId`는 CSV에 없으므로 `.env`의 `BUSAN_BIMS_*` 값을 사용해 BIMS `busInfo`의 `buslinenum -> lineid` 매핑을 받아 채운다.
  - 매핑 전 정규화 규칙은 보수적으로 고정한다. CSV `인가노선`과 BIMS `buslinenum`은 둘 다 문자열로 읽고 `trim()`만 적용한 뒤 exact match 한다. 숫자 변환, `'번'` suffix 제거, 임의 대소문자 변환, 하이픈/접미사 치환은 승인된 alias 규칙 없이는 금지한다.
  - 현재 확인 결과 BIMS `busInfo` 샘플 payload의 `buslinenum`은 `'10'`처럼 문자열 텍스트로 관측됐고, `buslinenum -> lineid`는 1:1이었다. 단, 이 검증은 사전 확인 단계이므로 ETL 본 실행에서도 동일 조건을 다시 검증하고 리포트에 남긴다.
  - 심야/마을/군·구 노선 등 CSV에 없는 BIMS 노선은 이번 테이블 적재 범위에서 제외한다.
  - 노선명 정규화 규칙은 ETL 내부에 명시한다. 예: `88-1A`처럼 접미사가 붙은 노선은 CSV 원본 값을 우선 유지하고, 별도 alias 규칙 없이는 임의로 `88-1`로 치환하지 않는다.
  - `low_floor_bus_routes`의 PK는 `routeId`이므로, BIMS 매핑 실패 노선은 synthetic key를 만들지 않고 INSERT 대상에서 제외한다. 대신 `routeNo`, `lowFloorVehicleCount`, `totalVehicleCount`, `unmatchedReason`을 unmatched 리포트에 남기고 경고를 출력한다.
  - 매핑 실패 노선이 1건 이상이면 ETL은 기본적으로 실패(exit non-zero)시키고, 승인된 alias 맵 또는 대체 소스가 준비될 때까지 workstream `03`을 blocked로 유지한다. 운영상 임시 적재가 필요할 때만 `--allow-unmatched-skip` 같은 명시적 예외 모드로 skip을 허용한다.
  - BIMS `busInfo`의 `bustype`는 `hasLowFloor` 판단 근거로 사용하지 않는다. `busInfo`는 정적 노선 카탈로그와 `routeId` 보강 용도만 허용한다.
  - BIMS `stopArrByBstopid.lowplate1/lowplate2`, `busInfoByRouteId.lowplate`는 실시간 차량 관측값이므로 `low_floor_bus_routes`의 정적 진실값으로 승격하지 않는다. 후속 오케스트레이션에서 trip 단위 override 근거로만 사용한다.
  - 최종 적재 컬럼은 `routeId, routeNo, hasLowFloor`다. `lowFloorVehicleCount`, `totalVehicleCount`는 DB 컬럼이 아니라 ETL 산출 리포트 필드로만 유지한다.
  - ETL 산출물은 최소 2개로 남긴다: `stdout` 요약과 `etl/reports/low_floor_bus_routes_<run-date>.json` 리포트. 이 리포트에는 `sourceRowCount`, `distinctRouteCount`, `matchedRouteCount`, `unmatchedRouteCount`, `routes[]`(`routeNo`, `routeId`, `hasLowFloor`, `lowFloorVehicleCount`, `totalVehicleCount`)를 포함한다.
- [x] 적재 순서는 `places -> place_accessibility_features -> road_segments/segment_features 보강 -> subway_station_elevators -> low_floor_bus_routes`로 유지한다.
- [ ] ETL 매칭 거리 규칙은 DB 필드가 아니라 ETL 내부 규칙으로만 유지한다.
  - `<= 15m`: update
  - `15m ~ 30m`: update 여부는 속성별로 결정
  - `> 30m`: skip, `UNKNOWN` 유지

## Validation Plan

- [ ] 각 CSV의 헤더와 ERD 컬럼 간 누락/추가 컬럼을 점검한다.
- [ ] 공간 매칭 반경, 우선순위, 다중 매칭 충돌 규칙을 점검한다.
- [ ] `subway_station_elevators_erd_ready.csv`는 적재 전 `stationId`, `point` 누락 0건과 중복 조합 존재 여부를 검증한다.
- [ ] `subway_station_elevators_erd_ready.csv`의 elevator-to-segment 매칭 결과를 검증한다.
  - `road_segments.elevatorState='YES'` 개수와 `featureType='SUBWAY_ELEVATOR'` 개수를 함께 기록한다.
  - `<= 15m` 자동 반영 건수, `15m~30m` review-required 건수, `>30m` unmatched 건수를 분리해서 리포트한다.
  - 대표 역 샘플 3곳 이상에서 실제 엘리베이터 포인트가 역 출입구 인접 세그먼트에만 귀속되고 도로 반대편 세그먼트까지 번지지 않는지 수동 확인한다.
- [ ] `부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv`는 적재 전 `인가노선`, `운행구분` 누락 여부와 `운행구분='저상'` 분포를 검증한다.
- [ ] CSV에서 집계한 `routeNo`가 BIMS `busInfo.buslinenum`과 exact string match 되는지 검증하고, 매핑 실패 노선이 0건인지 확인한다.
- [ ] BIMS `busInfo.buslinenum`의 실제 페이로드 형식이 숫자 문자열(`'10'`)인지, suffix 포함 문자열(`'10번'`)인지 실행 리포트에 기록한다.
- [ ] `low_floor_bus_routes` 적재 후 `hasLowFloor=true` 비율이 비정상적으로 0% 또는 100%가 아닌지 점검하고, 부산시 저상버스 예외노선 공지와 대표 샘플(`38`, `88-1A`)을 교차 검증한다.
- [ ] `routeId` 매핑 실패 노선이 있으면 unmatched 리포트를 검토하고, alias 승인 없이 synthetic key를 생성하지 않았는지 점검한다.
- [ ] 적재 후 대표 샘플 구간에 대해 `road_segments`와 `segment_features`가 함께 채워지는지 확인한다.

## Risks and Open Questions

- `slope_analysis_staging.csv`는 세그먼트 직접 키가 없어 공간 매칭 성능과 정확도 모두 검증이 필요하다.
- `stg_audio_signals_ready.csv`와 `stg_crosswalks_ready.csv`는 포인트 feature라 교차로 인접 세그먼트 중 어떤 세그먼트에 귀속시킬지 기준이 필요하다.
- `subway_station_elevators_erd_ready.csv`는 누락보다 중복 관리가 핵심 리스크다. 동일 출입구/좌표 중복을 그대로 적재하면 역별 엘리베이터 수와 최근접 선택 로직이 왜곡될 수 있다.
- `subway_station_elevators_erd_ready.csv`는 역 출입구 포인트이지 보행 세그먼트 키가 아니므로, 잘못 매칭하면 역 주변 일반 세그먼트까지 `elevatorState=YES`가 퍼질 수 있다. 이 데이터는 “역 진입 접근 가능” 의미로만 보수적으로 반영해야 한다.
- 현재 CSV는 `lineName`이 1~4호선만 포함하므로, 동해선/경전철 엘리베이터 접근성을 요구하는 시나리오는 이번 범위에서 제외하거나 별도 데이터 확보가 필요하다.
- `부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv`는 시내버스 차량 등록 데이터라 BIMS 전체 노선(심야, 마을, 군·구 포함)을 모두 덮지 않는다. 이번 `low_floor_bus_routes`는 CSV로 확인 가능한 시내버스 노선만 우선 적재하고, 나머지는 별도 데이터 소스 확보 전까지 범위 밖으로 둔다.
- `88-1A`처럼 CSV와 부산시 공지의 노선 표기가 완전히 같지 않은 케이스가 있어 alias 규칙을 임의로 만들면 잘못된 노선으로 합쳐질 수 있다. 표기 차이는 검증 리포트로 드러내고, 별도 승인 전에는 원본 표기를 유지한다.
- CSV 인코딩이 `cp949`이므로 ETL이 기본 UTF-8 가정으로 열면 실행 환경에 따라 헤더 파싱이 깨질 수 있다. 인코딩은 하드코딩하거나 실패 시 명시적으로 중단해야 한다.
- `routeId`가 PK인 스키마에서 매핑 실패 노선을 억지로 적재하려 하면 잘못된 synthetic key 설계로 이어질 수 있다. 매핑 실패는 적재 성공이 아니라 blocker로 다뤄야 한다.
- surface/curb_ramp/elevator 등 후속 데이터셋이 추가되면 현재 POC 규칙과 충돌 없이 동일한 confidence 체계에 편입돼야 한다.

## Additional Blocker

- Busan BIMS `busInfo` currently returns `bustype` categories such as `일반버스`, `마을버스`, and `급행버스`, but no explicit low-floor flag. `low_floor_bus_routes.hasLowFloor` must therefore come from the static bus registration CSV, while BIMS remains limited to `routeId` mapping plus real-time `lowplate` override at request time.

## Dependencies

- `02`에서 생성한 `road_segments`와 공간 인덱스
- BIMS API 접속 정보
- `부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv`

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
- Local canonical bootstrap must validate the actual DB target before any ETL rerun.
  - Stop or isolate legacy containers that already bind `localhost:5432` before recreating the disposable local DB.
  - After `docker compose up`, verify `SELECT table_name ...` and `SELECT column_name ...` against `etl/sql/schema.sql` instead of assuming the new container is the one serving `localhost:5432`.
  - Treat `snake_case` columns, `segment_attribute_match_result`, or `subway_station_elevators.is_operating` as a sign that the session is still pointed at an old database.
- Local Docker execution must not assume `docker` is on PATH.
  - Resolve the actual CLI path first when needed, and ensure the Docker credential helper directory is on PATH before `docker compose up`.
  - If Docker Desktop is installed under `/Applications/Docker.app/Contents/Resources/bin`, include that directory when compose commands fail with `docker-credential-desktop` errors.
- ETL reruns must preserve dependency order and avoid unsafe parallel execution.
  - `02_places_load.py` and `03_accessibility_features_load.py` must not run in parallel because `place_accessibility_features.placeId` has a foreign key to `places.placeId`.
  - `05_subway_elevators_load.py` may run before the elevator-to-segment enrichment slice, but `road_segments.elevatorState` validation must wait until that enrichment finishes.
  - `04_segment_features_load.py` should run only after `01_osm_load.py` has confirmed `road_segments` existence on the current canonical DB.
- OSM source handling must be repo-local for repeatable reruns.
  - `01_osm_load.py` currently assumes repo-local paths when it prints stage banners, so sibling-repo inputs should be copied or symlinked into `etl/data/raw/` before execution.
  - When `runtime/etl/osm-network-snapshot.pkl.gz` is already present for the same canonical schema, prefer `--load-snapshot` for reruns instead of reparsing the PBF.
- Post-load validation should check actual committed state, not just process exit codes.
  - After each ETL stage, run a small count query on the target tables before starting the dependent stage.
  - For long-running loaders such as `04_segment_features_load.py`, treat “no active process” plus final DB counts as the source of truth if the terminal session ends before the buffered summary is printed.
