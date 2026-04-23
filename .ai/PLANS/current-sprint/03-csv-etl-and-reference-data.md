# 03 CSV ETL 및 참조 데이터 적재

## 워크스트림

`CSV, BIMS, 연속수치지도 기반 접근성 보강 적재`

## 목표

`etl/raw/`의 CSV, BIMS 연계 정보, 그리고 새로 추가된 `drive-download-20260423T052307Z-3-001` 번들 데이터를 사용해 기존 `road_segments`, `segment_features`를 보강하고, 대중교통 및 시설 참조 테이블을 정리한다.

## 범위

- 장소 및 시설 접근성 CSV 적재
- 음향신호기, 횡단보도, 경사도, 엘리베이터 보강
- `road_segments`와 `segment_features` 공간 매칭 규칙 정리
- `low_floor_bus_routes` 적재
- `drive-download-20260423T052307Z-3-001` 기반 보조 레이어 적재 계획 수립

## 비목표

- 운영 자동화
- GraphHopper import 구현
- 전체 API 구현

## 입력 근거

- `etl/raw/place_merged_broad_category_final.csv`
- `etl/raw/place_accessibility_features_merged_final.csv`
- `etl/raw/stg_audio_signals_ready.csv`
- `etl/raw/stg_crosswalks_ready.csv`
- `etl/raw/slope_analysis_staging.csv`
- `etl/raw/subway_station_elevators_erd_ready.csv`
- `etl/raw/부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv`
- `etl/raw/drive-download-20260423T052307Z-3-001/`
- `docs/prd.md`
- `docs/erd.md`
- `docs/erd_v2.md`
- `.env`

## 성공 기준

- [ ] 각 입력 데이터가 어떤 테이블과 컬럼을 채우는지 한국어 기준으로 명확히 정리되어 있다.
- [ ] 기존 CSV/BIMS 적재와 새 연속수치지도 번들 적재가 충돌 없이 같은 `edgeId` 중심 규칙을 사용한다.
- [ ] `road_segments` 직접 업데이트 대상과 `segment_features` 증적 적재 대상을 구분했다.
- [ ] 검증 시 source row 수, 매칭 수, 미매칭 수, 다중 후보 충돌 수를 남기는 계획이 정의되어 있다.

## 기존 검증 근거

- 2026-04-22 기준 정규 DB 부트스트랩과 주요 ETL 실행이 완료되어, 기존 camelCase 스키마 기준 검증 경로가 확보되었다.
- `04_segment_features_load.py`는 audio, crosswalk, slope 보강의 기준 수치를 남겼다.
- 엘리베이터-세그먼트 보강도 한 차례 구현되었으나, review-required와 unmatched 처리가 남아 있다.
- 저상버스 적재는 정적 CSV + BIMS `routeId` 매핑 구조로 한 차례 검증되었다.
- 2026-04-23 기준 SHP 비교 시각화 스크립트가 추가되어 OSM 대비 정규 SHP 도형 비교가 가능하다.
- 2026-04-23 기준 `etl/scripts/04_segment_features_load.py`를 부산 전체 적재 기준으로 보정하고 재실행해 `segment_features` 5,073건을 다시 적재했다.
  - `AUDIO_SIGNAL` 1,223건 적재, 1,837건 미매칭, `road_segments.audio_signal_state='YES'` 326건 반영
  - `CROSSWALK` 3,737건 적재, 75건 미매칭, `road_segments.crossing_state='TRAFFIC_SIGNALS'` 3,485건 반영
  - `SUBWAY_ELEVATOR` 113건 적재, 90건 미매칭, `road_segments.elevator_state='YES'` 98건 반영
  - 전체 적재 리포트는 `runtime/etl/busan-segment-features-load-report.json`에 남겼다.
- 같은 날 `etl/scripts/10_jangsan_network_features_visualize.py`는 DB 전체 적재 결과를 유지한 채 장산역 반경 5km만 잘라 `runtime/etl/jangsan-road-segments-and-segment-features.html`로 시각화했다.

## 구현 계획

- [ ] `place_merged_broad_category_final.csv`를 `places`에 적재한다.
  - `placeId -> place_id`
  - `name -> name`
  - `category -> category`
  - `address -> address`
  - `point -> point`
  - `providerPlaceId -> provider_place_id`
- [ ] `place_accessibility_features_merged_final.csv`를 `place_accessibility_features`에 적재한다.
  - `placeId`를 외래키로 연결한다.
  - `featureType`, `isAvailable`를 보존한다.
- [ ] `stg_audio_signals_ready.csv`를 이용해 `road_segments.audio_signal_state`와 `segment_features`를 보강한다.
  - `stat='정상동작'`인 건만 `YES` 후보로 사용한다.
  - 공간 매칭은 `candidate search -> ranking -> final assignment`로 수행한다.
  - 원본 포인트는 `segment_features.feature_type='AUDIO_SIGNAL'`로 남긴다.
- [ ] `stg_crosswalks_ready.csv`를 이용해 `road_segments.crossing_state`, `width_meter` 보조 업데이트, `segment_features` 적재를 수행한다.
  - `point`가 없는 레코드는 적재 대상에서 제외한다.
  - 횡단보도 원본 포인트는 `segment_features.feature_type='CROSSWALK'`로 남긴다.
- [ ] `slope_analysis_staging.csv`를 이용해 `road_segments.avg_slope_percent`, `width_meter`를 보강한다.
  - 좌표계는 반드시 `geometry_wkt_4326` 기준으로 사용한다.
  - 교차한 polygon은 `segment_features.feature_type='SLOPE_ANALYSIS'`로 남긴다.
  - `stairs_data_status='MISSING_SOURCE'`는 `stairs_state`를 섣불리 채우지 않는다.
- [ ] `subway_station_elevators_erd_ready.csv`를 `subway_station_elevators`에 적재한다.
  - `stationId + entranceNo + point` 기준 중복 제거 규칙을 명시한다.
  - `stationId`, `point` 결측 여부를 별도 검증한다.
- [ ] `subway_station_elevators_erd_ready.csv`의 포인트를 `road_segments`와 매칭해 `elevator_state`를 보강한다.
  - `<= 15m`는 자동 반영 후보
  - `15m ~ 30m`는 review-required
  - `> 30m`는 skip
  - 원본 포인트는 `segment_features.feature_type='SUBWAY_ELEVATOR'`로 남긴다.
- [ ] 저상버스 등록 CSV와 BIMS를 이용해 `low_floor_bus_routes`를 적재한다.
  - 정적 CSV는 저상버스 여부 판단 근거로 사용한다.
  - BIMS는 `routeId` 보강과 실시간 `lowplate` override 참고값으로만 사용한다.
  - `routeId`를 알 수 없는 노선은 synthetic key를 만들지 않고 별도 리포트로 분리한다.

## 신규 연속수치지도 번들 적재 계획

### 목적

`etl/raw/drive-download-20260423T052307Z-3-001/`에 추가된 구별 연속수치지도 레이어를 기존 `road_segments`, `segment_features` 보강 흐름에 연결한다. 이 작업은 정규 네트워크를 새로 정의하는 `02`가 아니라, 이미 적재된 네트워크를 보강하는 `03`의 범위로 다룬다.

### 레이어 분류

| 레이어 코드 | Geometry | 전역 건수 | 1차 적재 대상 | 계획 메모 |
| --- | --- | ---: | --- | --- |
| `N3L_A0020000` | `POLYLINE` | `252,315` | `road_segments` 비교/대체 후보 | 현재 정규 도로 중심선과 같은 계열이므로, 기존 `N3L_A0020000_26`와 차이 비교 후에만 교체 여부를 결정한다 |
| `N3L_A0033320` | `POLYLINE` | `36,311` | `segment_features` 우선, 일부 `road_segments` 승격 후보 | 보도성 선형 레이어로 추정되며 폭, 품질 정보를 가진다 |
| `N3A_A0080000` | `POLYGON` | `255` | `segment_features` | 교차로/교차영역 계열로 추정, 원본 polygon 보존 우선 |
| `N3A_C0390000` | `POLYGON` | `3,939` | `segment_features` | 구조물성 polygon 레이어로 추정, 직접 상태값 승격 금지 |
| `N3A_A0063321` | `POLYGON` | `187` | `segment_features` | 소규모 구조물 polygon, 타입 코드 검증 전에는 증적 적재만 수행 |
| `N3A_A0070000` | `POLYGON` | `1,352` | `segment_features` | 교량/구조물 계열로 추정, 증적 적재 우선 |
| `N3L_A0123373` | `POLYLINE` | `168` | `segment_features` | 터널 계열 선형 레이어로 추정, `영도구`에는 레이어가 없음 |
| `N3L_A0010000` | `POLYLINE` | `44,838` | 보류 | 라우팅 의미가 아직 불명확하므로 코드 사전 확인 전 보류 |
| `N3L_F0010000` | `POLYLINE` | `17,870` | 보류 | 등고선/표고 선형 정보로 보이며 직접 접근성 상태값으로 사용하지 않음 |
| `N3P_F0020000` | `POINT` | `44,754` | 보류 | 표고 점 계열로 보이며 1차 적재 대상에서 제외 |

### 적재 전략

1. 번들 manifest를 만든다.
   - 16개 구 폴더를 모두 순회해 레이어 존재 여부, 경로, geometry 타입, row 수를 기록한다.
   - 결과는 `runtime/etl/continuous-map-load/` 아래 JSON으로 남긴다.
   - `영도구`의 `N3L_A0123373` 부재처럼 선택적 누락은 경고로만 기록한다.
2. source identity를 번들 기준으로 정규화한다.
   - `source_dataset='drive-download-20260423T052307Z-3-001:N3L_A0033320'`처럼 번들명과 레이어 코드를 함께 기록한다.
   - `source_feature_id`는 `구명 + UFID` 조합으로 만들어 구별 tile 간 충돌을 피한다.
3. `N3L_A0020000`는 즉시 교체하지 않는다.
   - 현재 `02`에서 적재한 `N3L_A0020000_26` 결과와 row count, geometry sample, source identity 차이를 비교한다.
   - 비교 리포트가 준비되기 전까지는 `road_segments` 정규 소스를 교체하지 않는다.
4. 비정규 레이어는 `segment_features` 우선으로 적재한다.
   - `N3L_A0033320`, `N3A_A0080000`, `N3A_C0390000`, `N3A_A0063321`, `N3A_A0070000`, `N3L_A0123373`를 1차 대상으로 본다.
   - `feature_type`은 `CONTINUOUS_MAP_<레이어코드>`처럼 원본 레이어를 명시하는 형태를 사용한다.
5. `road_segments` 직접 승격은 고신뢰 후보만 허용한다.
   - 1차 승격 후보는 `N3L_A0033320`이다.
   - 단일 세그먼트에 명확히 매칭된 경우에만 `width_meter`, 향후 `walk_access` 보조 판단 근거로 사용한다.
   - `braille_block_state`, `curb_ramp_state`, `stairs_state`, `elevator_state`는 코드 사전 검증 전까지 이 번들에서 직접 채우지 않는다.

### 매칭 규칙

- 선형 레이어는 `road_segments.geom`과의 겹침 길이 기반 ranking을 사용한다.
- polygon 레이어는 `ST_Intersects`와 겹침 비율 기준을 함께 사용한다.
- point 레이어를 이후 활성화할 경우에만 `ST_DWithin` 거리 제한을 사용한다.
- 어떤 레이어든 최종 업데이트와 외래키 연결은 `edgeId`로 마무리한다.

### 검증 게이트

- [ ] 16개 구 manifest가 생성되고 레이어별 row 수가 기록된다.
- [ ] `N3L_A0020000`의 번들 버전과 기존 정규 적재본 비교 리포트가 생성된다.
- [ ] 각 `segment_features.feature_type`별로 source 수, 매칭 수, 미매칭 수, 다중 후보 수가 기록된다.
- [ ] `N3L_A0033320` 승격 시 `width_meter` 업데이트 건수와 skip 이유가 리포트에 남는다.

## 검증 계획

- [ ] 각 CSV와 SHP 번들 레이어의 실제 헤더/필드와 적재 대상 컬럼을 대조한다.
- [ ] 공간 매칭 규칙별로 샘플 검증을 수행한다.
- [ ] `subway_station_elevators_erd_ready.csv`의 결측 및 중복 검증 결과를 남긴다.
- [ ] 저상버스 적재 시 `routeId` 미매칭 노선을 별도 리포트로 남긴다.
- [ ] `drive-download-20260423T052307Z-3-001` 적재 시 레이어별 source/matched/unmatched/conflict 리포트를 남긴다.

## 위험 및 열린 질문

- `N3L_A0033320`, `N3A_A0063321`, `N3A_A0070000`, `N3A_A0080000`, `N3A_C0390000`의 공식 코드 사전 없이는 상태값 승격이 위험하다.
- 새 번들의 `N3L_A0020000`를 기존 정규 네트워크의 대체 소스로 볼지, 보조 비교 소스로 볼지 아직 결정되지 않았다.
- 저상버스 CSV와 BIMS 노선명의 exact match 의존성이 깨질 경우 수동 alias 정책이 필요할 수 있다.
- point 기반 데이터와 polygon 기반 데이터의 공간 매칭 품질 차이를 같은 지표로 비교하면 오판 가능성이 있다.

## 의존성

- `02`에서 적재된 `road_segments`, 공간 인덱스, `edgeId`
- BIMS API 접속 정보
- PostGIS가 켜진 로컬 검증 DB

## 핸드오프

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 이 워크스트림은 새 데이터셋을 포함한 모든 보강 적재를 `edgeId` 중심 규칙으로 묶어야 하며, 정규 네트워크 재정의는 `02`의 범위를 침범하지 않아야 한다.
