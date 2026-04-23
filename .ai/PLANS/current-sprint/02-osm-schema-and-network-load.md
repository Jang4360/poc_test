# 02 OSM 스키마 전환 및 네트워크 적재

## 워크스트림

`SHP 우선 정규 네트워크 적재`

## 목표

기존 OSM 중심 네트워크 식별 방식을 `etl/raw/N3L_A0020000_26.shp` 기반 SHP 우선 구조로 전환하고, 이후 CSV ETL과 GraphHopper가 `road_nodes`, `road_segments`를 공통 기준선으로 사용하도록 만든다.

## 범위

- 공식 도로 중심선 SHP를 PostGIS 정규 그래프 테이블로 적재
- OSM natural key 의존 제거
- SHP 종단점 기반 결정적 노드 식별 생성
- preflight, snapshot, topology audit, DB load 단계 분리
- 후속 워크스트림의 기준 키를 `edgeId`로 고정

## 비목표

- CSV 접근성 ETL 구현
- GraphHopper import 구현
- SHP와 OSM을 적재 시점에 혼합하는 하이브리드 로직
- 최종 보행 가능성 판정 규칙 완성

## 입력 근거

- `etl/raw/N3L_A0020000_26.shp`
- `etl/raw/N3L_A0020000_26.shx`
- `etl/raw/N3L_A0020000_26.dbf`
- `etl/raw/N3L_A0020000_26.prj`
- `etl/sql/schema.sql`
- `docs/erd.md`
- `docs/erd_v2.md`
- `.ai/PLANS/current-sprint/03-csv-etl-and-reference-data.md`

## 성공 기준

- [x] `N3L_A0020000_26`이 `road_segments`의 정규 네트워크 소스로 고정되었다.
- [x] OSM 전용 식별 컬럼이 소스 비종속 스키마로 대체되었다.
- [x] SHP에서 `road_nodes`, `road_segments`를 결정적으로 파생하는 규칙이 구현되었다.
- [x] topology audit와 DB load가 명시적 단계로 분리되었다.
- [x] 후속 워크스트림은 `edgeId` 중심 핸드오프를 사용한다.

## 주요 설계 결정

- 워크스트림 `02`의 정규 네트워크 소스는 `busan.osm.pbf`가 아니라 `N3L_A0020000_26` SHP다.
- 기존 OSM 식별자 조합은 더 이상 정규 키가 아니다.
  - 기존: `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`
  - 신규: `(sourceDataset, sourceFeatureId, sourcePartOrdinal)`
- `road_nodes`의 정체성은 OSM node id가 아니라 정규화된 SHP 좌표에서 파생한다.
- `walkAccess`는 적재 시점에 `UNKNOWN`으로 유지하고, 후속 보강 단계가 별도로 판단한다.
- topology audit는 라인 적재와 분리된 독립 단계로 유지한다.

## 구현 계획

- [x] `etl/sql/schema.sql`을 SHP 우선 구조로 정리했다.
  - `road_nodes.source_node_key`를 필수로 만들었다.
  - `road_segments.source_dataset`, `source_feature_id`, `source_part_ordinal`를 필수로 만들었다.
  - `(source_dataset, source_feature_id, source_part_ordinal)` 유니크 인덱스를 유지한다.
- [x] `etl/common/centerline_loader.py`를 추가했다.
  - SHP sidecar 파일 검증
  - `EPSG:5179` CRS 검증
  - `cp949 -> euc-kr -> utf-8` 순서의 인코딩 fallback
  - 결정적 endpoint key 생성과 안정적인 `vertexId` 해시
  - snapshot CSV와 topology audit 산출물 생성
  - rerun-safe PostGIS truncate and reload 흐름
- [x] `etl/scripts/01_centerline_load.py`를 추가했다.
  - `preflight`, `extract-shp`, `topology-audit`, `load-db`, `full` 단계 제공
  - snapshot CSV가 있으면 `load-db` 단계에서 SHP 재파싱 없이 재적재 가능
- [x] `etl/scripts/01_osm_load.py`를 정규 진입점에서 제외했다.
  - 현재는 `01_centerline_load.py`가 정규 로더라는 메시지만 출력한다.
- [x] 핸드오프 문서를 갱신했다.
  - `docs/erd.md`
  - `docs/erd_v2.md`
  - `.ai/PLANS/current-sprint/03-csv-etl-and-reference-data.md`

## 실행 산출물

- 산출물 디렉터리: `runtime/etl/centerline-load/`
- 주요 산출물:
  - `centerline_snapshot.json`
  - `centerline_topology_audit.json`
  - `road_nodes_snapshot.csv`
  - `road_segments_snapshot.csv`

## 검증 계획

- `python -m compileall etl`: 통과
- `python -m pytest etl/tests/test_db.py etl/tests/test_centerline_loader.py -q`: `7 passed`
- `python etl/scripts/01_centerline_load.py --stage preflight`: 통과
  - SHP sidecar 존재 확인
  - CRS `EPSG:5179` 확인
  - DBF 인코딩 `cp949` 확인
  - 원본 레코드 수 `248,425`
- `python etl/scripts/01_centerline_load.py --stage topology-audit`: 통과
  - part-expanded segments `248,458`
  - derived nodes `229,133`
  - invalid geometries `0`
  - duplicate source identities `0`
  - orphan endpoints `0`
  - citywide connected components `1,241`
- `docker compose up -d postgres`: 통과
- `python etl/scripts/01_centerline_load.py --stage full`: 통과
  - `road_nodes` 적재 `229,133`
  - `road_segments` 적재 `248,458`
  - orphan reference `0`
  - duplicate source key `0`
- 적재 후 DB 검증
  - `SELECT COUNT(*) FROM road_nodes` -> `229133`
  - `SELECT COUNT(*) FROM road_segments` -> `248458`
  - `SELECT COUNT(*) FROM road_segments WHERE source_dataset = 'N3L_A0020000_26'` -> `248458`

## 위험 및 열린 질문

- `N3L_A0020000_26`은 보도 전용이 아니라 도로 중심선 데이터다.
- `RDDV`, `DVYN`, `ONSD` 값은 현재 trace용 참고 정보이며, 직접적인 라우팅 규칙은 아니다.
- 연결 컴포넌트와 near-miss endpoint 수치를 보면 라우팅 품질 개선은 `04`에서 계속 다뤄야 한다.
- `03`의 실제 접근성 CSV와 `edgeId` 기반 공간 매칭 검증은 다음 워크스트림 과제로 남아 있다.

## 의존성

- PostGIS가 활성화된 로컬 DB
- `.env`의 DB 연결 정보

## 핸드오프

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 정규 네트워크 적재와 `edgeId` 중심 핸드오프가 확정되었으므로, 후속 워크스트림은 이 기준을 깨지 않고 보강만 수행해야 한다.
