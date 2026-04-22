# POC ETL 결과 요약

측정일: 2026-04-23  
대상 DB: `poc_test-postgresql-1` (localhost:5432, ieumgil)  
ETL 대상 workstream: 03 (CSV ETL and Reference Data)

---

## 테이블별 적재 결과

| 테이블 | 적재 건수 |
|---|---|
| `places` | 13,564 |
| `place_accessibility_features` | 42,368 |
| `road_nodes` | 96,169 |
| `road_segments` | 115,080 |
| `segment_features` | 120,459 |
| `subway_station_elevators` | 203 |
| `low_floor_bus_routes` | 146 (has_low_floor=true: 118) |

---

## CSV 원본수 vs DB 적재수

| CSV 파일 | 원본 행수 | DB 적재수 | 차이 | 이유 |
|---|---|---|---|---|
| `place_merged_broad_category_final.csv` | 13,564 | 13,564 | 0 | 1:1 직접 INSERT, 필터 없음 |
| `place_accessibility_features_merged_final.csv` | 42,368 | 42,368 | 0 | 1:1 직접 INSERT, 필터 없음 |
| `stg_audio_signals_ready.csv` | 3,060 | 1,000 | -2,060 | 공간매칭 실패 + `stat='정상동작'` 필터 |
| `stg_crosswalks_ready.csv` | 3,815 | 2,072 | -1,743 | point 공란 3건 제외 + 공간매칭 실패 1,740건 |
| `slope_analysis_staging.csv` | 163,008 | 117,285 | -45,723 | 공간교차 없는 polygon 제외 |
| `subway_station_elevators_erd_ready.csv` | 231 | 203 | -28 | dedupe (동일 stationId+entranceNo+point 중복 제거) |
| `부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv` | 2,511 (차량 단위) | 146 (노선 단위) | - | 인가노선 기준 집계 후 BIMS routeId 매핑 |

> audio/crosswalk/slope/elevator의 차이는 공간매칭 미히트로 설계상 정상.  
> elevator 28건 탈락만 dedupe에 의한 중복 제거.  
> `stg_crosswalks_ready.csv` point 공란 예시: `crosswalk:700` (북구 만덕동, lat/lng/point 전부 없음)

---

## segment_features vs road_segments 업데이트 건수

여러 feature가 같은 세그먼트에 매핑될 수 있어 segment_features 건수 > road_segments 업데이트 건수.

| featureType | segment_features | road_segments 업데이트 컬럼 | 업데이트 건수 |
|---|---|---|---|
| `AUDIO_SIGNAL` | 1,000 | `audioSignalState=YES` | 248 segments |
| `CROSSWALK` | 2,072 | `crossingState` | 1,841 segments |
| `SLOPE_ANALYSIS` | 117,285 | `avgSlopePercent`, `widthMeter` | 34,871 / 35,904 segments |
| `SUBWAY_ELEVATOR` | 102 | `elevatorState=YES` | 86 segments |

---

## road_segments 컬럼별 채움 현황 (전체 115,080개 기준)

| 컬럼 | 채워진 수 | 비율 | 소스 |
|---|---|---|---|
| `walkAccess` | 115,080 | 100% | OSM (01_osm_load.py) |
| `avgSlopePercent` | 34,871 | 30.3% | slope CSV |
| `widthMeter` | 35,904 | 31.2% | slope CSV + crosswalk 보조 |
| `crossingState` | 1,841 | 1.6% | crosswalk CSV |
| `audioSignalState` | 248 | 0.2% | audio CSV |
| `elevatorState` | 86 | 0.07% | subway elevator |
| `stairsState` | 0 | 0% | 소스 없음 (stairs_data_status=MISSING_SOURCE) |
| `brailleBlockState` | 0 | 0% | 소스 없음 |
| `curbRampState` | 0 | 0% | 소스 없음 |
| `surfaceState` | 0 | 0% | 소스 없음 |
| `widthState` | 0 | 0% | widthMeter 파생 규칙 미구현 |

---

## 잔여 공백 및 후속 과제

- `widthState`: `widthMeter` 값(35,904건)이 있으나 enum 파생 규칙이 구현되지 않아 전부 UNKNOWN
- `brailleBlockState`, `curbRampState`, `surfaceState`: 현재 데이터 소스 미확보, 이번 workstream 범위 밖
- `stairsState`: 원천 CSV의 `stairs_data_status=MISSING_SOURCE`로 보수적 UNKNOWN 유지
- 엘리베이터 매칭률: 203 포인트 → 86 세그먼트 (43%), 잔여 117포인트는 15m 이내 매칭 세그먼트 없음
