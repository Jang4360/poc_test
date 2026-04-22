# 02 OSM Schema And Network Load

## Workstream

`국토교통부 SHP 기반 도로 중심선 적재와 네트워크 재정의`

## Goal

`busan.osm.pbf` 선적재를 canonical source에서 제외하고, `N3L_A0020000_26` SHP를 기준으로 `road_nodes`와 `road_segments`를 다시 정의해 이후 CSV ETL과 GraphHopper가 공통으로 참조할 기준 테이블을 준비한다.`

## Scope

- SHP 기반 선형 geometry 적재 전략 수립
- OSM 전용 스키마를 source-agnostic 네트워크 스키마로 재정의
- `road_nodes`, `road_segments`, `segment_features`가 SHP 중심선 입력으로도 유지되도록 schema migration 방향 정의
- SHP 로드와 topology audit를 분리한 적재 흐름 정의
- 이후 CSV ETL과 GraphHopper가 재사용할 수 있는 `edgeId` 중심 식별 규칙 고정

## Non-goals

- CSV 보강 ETL 구현
- GraphHopper import 구현
- OSM PBF와 SHP를 동시에 merge하는 하이브리드 로더 구현
- 도로 중심선만으로 보행 가능 여부를 최종 확정하는 규칙 구현

## Source Inputs

- Request: 기존 `busan.osm.pbf` 적재를 제외하고 `N3L_A0020000_26` 기반 edge 데이터를 canonical source로 전환
- Docs: `docs/prd.md`, `docs/erd.md`
- Code and data references:
  - `etl/data/raw/N3L_A0020000_26.shp`
  - `etl/data/raw/N3L_A0020000_26.shx`
  - `etl/data/raw/N3L_A0020000_26.dbf`
  - `etl/data/raw/N3L_A0020000_26.prj`
  - `etl/sql/schema.sql`
  - `etl/scripts/09_shp_roads_visualize.py`

## Success Criteria

- [ ] `N3L_A0020000_26` SHP를 기준으로 `road_segments` 적재 전략이 명시된다.
- [ ] OSM 전용 컬럼(`osmNodeId`, `sourceWayId`, `sourceOsmFromNodeId`, `sourceOsmToNodeId`)을 대체할 source-agnostic schema 전략이 정의된다.
- [ ] SHP 선형을 `road_nodes` / `road_segments`로 전개하는 deterministic 규칙이 정의된다.
- [ ] topology audit와 load를 분리한 실행 순서가 정의된다.
- [ ] 이후 `03` CSV ETL과 `04` GraphHopper가 어떤 식별자를 기준으로 이어받아야 하는지 고정된다.

## What This Workstream Implements

- `road_nodes` 생성
  - SHP 선형의 시작/종료점을 vertex 후보로 추출
  - exact coordinate 또는 tolerance-normalized endpoint를 기준으로 `vertexId`를 생성
  - 더 이상 `osmNodeId`를 canonical key로 사용하지 않는다
- `road_segments` 생성
  - SHP line feature의 part 단위를 기본 edge 후보로 사용
  - `UFID`를 원천 feature 식별자로 보관
  - `edgeId`, `fromNodeId`, `toNodeId`, `geom`, `lengthMeter`와 raw road hints(`RDDV`, `RDLN`, `RVWD`, `ONSD`, `DVYN`, `RDNM`, `NAME`)를 저장
- schema/제약/인덱스 재정의
  - OSM 전용 natural key를 제거하고 `(sourceDataset, sourceFeatureId, sourcePartOrdinal)` 기반 unique key로 전환
  - `road_segments.geom` GIST index 유지
  - `road_nodes.point` GIST index 유지
- ETL 실행 구조 분리
  - `preflight`
  - `extract-shp`
  - `topology-audit`
  - `load-db`

## Simulation Findings

- 2026-04-23 local simulation confirmed that `N3L_A0020000_26` is a usable SHP input set:
  - required files present: `.shp`, `.shx`, `.dbf`, `.prj`
  - coordinate system: `EPSG:5179`
  - total line records: `248,425`
  - fields: `UFID`, `RDNU`, `NAME`, `RDDV`, `STPT`, `EDPT`, `PVQT`, `DVYN`, `RDLN`, `RVWD`, `ONSD`, `REST`, `RDNM`, `SCLS`, `FMTA`
- Attribute distribution shows the dataset is road-centerline oriented, not pedestrian-only:
  - `RDDV` top counts: `RDD000=208,271`, `RDD009=19,937`, `RDD008=14,959`, `RDD002=3,271`, `RDD001=1,023`, `RDD003=964`
  - `RVWD` range: `0.5m ~ 85.0m`
  - `RDLN` range: `1 ~ 12`
- Jangsan station 5km bbox simulation captured `12,140` line features, proving the SHP has materially denser local line coverage than the current OSM-derived walkable edge subset.
- The simulation also confirms that the SHP does not contain explicit pedestrian-only semantics equivalent to OSM `footway/path/pedestrian`; therefore `walkAccess` must start from `UNKNOWN` or heuristic defaults, not from hard-coded `YES`.

## Key Design Decisions

- Canonical source for workstream `02` shifts from `busan.osm.pbf` to `N3L_A0020000_26` SHP.
- OSM-specific identity is no longer valid.
  - old identity: `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`
  - new planned identity: `(sourceDataset, sourceFeatureId, sourcePartOrdinal)`
- `edgeId` remains the internal surrogate key consumed downstream by `03` and `04`.
- `road_segments` stays the source of truth, but it becomes `source-agnostic`.
- `road_nodes` remains useful for graph topology, but node identity becomes derived from geometry, not from OSM node ids.
- SHP load must be split from topology audit.
  - loading line features alone is not enough to assume routing connectivity
  - the pipeline must separately detect disconnected crossings, unsnapped endpoints, and line intersections that do not share endpoints
- `walkAccess` must not be overstated during SHP migration.
  - default should remain conservative (`UNKNOWN` or dataset-driven heuristic)
  - route safety logic should not assume every centerline is pedestrian-usable

## Schema Delta Plan

- Replace OSM-specific node identity in `road_nodes`.
  - remove or deprecate `osmNodeId`
  - add a derived node identity such as `sourceNodeKey` or geometry-hash-based key
- Replace OSM-specific source columns in `road_segments`.
  - deprecate `sourceWayId`
  - deprecate `sourceOsmFromNodeId`
  - deprecate `sourceOsmToNodeId`
  - deprecate OSM-specific meaning of `segmentOrdinal`
- Add SHP-oriented source columns in `road_segments`.
  - `sourceDataset` e.g. `NGII_ROAD_CENTERLINE`
  - `sourceFeatureId` from `UFID`
  - `sourcePartOrdinal`
  - `roadClassCode` from `RDDV`
  - `laneCount` from `RDLN`
  - `roadWidthMeterSource` from `RVWD`
  - `oneWayCode` from `ONSD`
  - `dividerCode` from `DVYN`
  - `roadName` from `NAME`
  - `roadNumber` from `RDNM`
- Update unique constraint.
  - new unique key: `(sourceDataset, sourceFeatureId, sourcePartOrdinal)`
- Preserve downstream accessibility columns unchanged.
  - `avgSlopePercent`
  - `widthMeter`
  - `walkAccess`
  - `brailleBlockState`
  - `audioSignalState`
  - `curbRampState`
  - `widthState`
  - `surfaceState`
  - `stairsState`
  - `elevatorState`
  - `crossingState`

## Load Strategy

- `preflight`
  - verify `.shp/.shx/.dbf/.prj` all exist
  - verify `.prj` resolves to `EPSG:5179`
  - verify DB target is the canonical camelCase schema
- `extract-shp`
  - read SHP line features with `pyshp` or GDAL-compatible reader
  - split multipart lines into `sourcePartOrdinal`
  - convert geometry to `EPSG:4326`
  - compute `lengthMeter`
  - emit a deterministic snapshot artifact before DB mutation
- `derive-nodes`
  - extract first/last point of each line part
  - normalize to a deterministic node key
  - assign `fromNodeId`, `toNodeId`
- `topology-audit`
  - report exact duplicate features
  - report invalid geometries
  - report line intersections without shared endpoints
  - report endpoint clusters within tolerance that are not yet merged
  - report disconnected component counts for the citywide graph and hotspot bboxes
- `load-db`
  - bulk insert `road_nodes`
  - bulk insert `road_segments`
  - preserve rerun-safe truncate/reload flow for the disposable local DB

## Implementation Plan

- [ ] `etl/sql/schema.sql`을 OSM 전용 컬럼에서 source-agnostic 컬럼으로 migration 가능한 형태로 수정한다.
- [ ] `docs/erd.md`의 `road_nodes`, `road_segments` 명세를 SHP 기반 canonical source에 맞게 수정한다.
- [ ] `etl/scripts/01_osm_load.py`를 더 이상 canonical loader로 두지 않는다.
  - 선택지 A: `01_centerline_load.py` 신설
  - 선택지 B: `01_osm_load.py`를 general network loader로 재작성
  - 현재 계획은 변경 범위를 명확히 하기 위해 `01_centerline_load.py` 신설을 우선한다.
- [ ] SHP preflight를 구현한다.
  - `.shp/.shx/.dbf/.prj` 존재 확인
  - 좌표계 확인
  - 필수 필드(`UFID`, `RDDV`, `RDLN`, `RVWD`) 존재 확인
- [ ] SHP feature snapshot flow를 구현한다.
  - raw feature count
  - part-expanded segment count
  - invalid geometry count
  - missing-attribute count
- [ ] endpoint-derived `road_nodes` 생성 규칙을 구현한다.
- [ ] `road_segments`를 `(sourceDataset, sourceFeatureId, sourcePartOrdinal)` 기준으로 적재한다.
- [ ] `walkAccess` 기본값 정책을 명시한다.
  - 초기값은 `UNKNOWN`
  - 필요 시 `RDDV` 기반 후보 분류를 별도 컬럼/리포트로만 남기고 즉시 라우팅 규칙으로 승격하지 않는다.
- [ ] topology audit artifact를 구현한다.
  - disconnected component count
  - line intersection without shared node
  - near-miss endpoint count
- [ ] `03`의 공간 매칭 ETL이 기존 `edgeId` 중심으로 계속 동작하도록 handoff 규칙을 수정한다.
- [ ] `04` GraphHopper workstream이 더 이상 OSM natural key를 전제하지 않도록 handoff 규칙을 수정한다.

## Validation Plan

- [ ] SHP preflight 통과
- [ ] `EPSG:5179 -> EPSG:4326` 변환 샘플 검증
- [ ] citywide raw feature count와 snapshot count 일치 확인
- [ ] multipart expansion 후 `(sourceDataset, sourceFeatureId, sourcePartOrdinal)` duplicate 0건 확인
- [ ] invalid geometry 0건 또는 explicit skip count 확인
- [ ] `road_nodes` 생성 후 orphan endpoint 0건 확인
- [ ] `road_segments` 적재 후 `edgeId` count와 snapshot segment count 일치 확인
- [ ] 장산역 5km bbox에서 SHP derived edge count가 simulation 수치와 근사하게 일치하는지 확인
  - baseline simulation: `12,140` line features in bbox
- [ ] topology audit에서 critical disconnected hotspot을 리포트한다.
- [ ] `03` CSV ETL 대표 샘플이 새 `edgeId` 체계에서도 정상적으로 매칭되는지 smoke 검증한다.

## Current Status

- Status: `in_progress` as of 2026-04-23 due to source strategy change.
- Legacy OSM loader implementation still exists in the repo, but it is no longer the intended canonical path for this sprint.
- `N3L_A0020000_26` SHP ingestion is feasible based on local simulation:
  - total SHP records: `248,425`
  - CRS: `EPSG:5179`
  - Jangsan 5km bbox line count: `12,140`
- A temporary visualization helper now proves the SHP can be clipped and rendered locally:
  - `etl/scripts/09_shp_roads_visualize.py`
  - `runtime/etl/jangsan-road-centerlines-shp-notile.html`
- Workstream `02` should therefore be treated as reopened.
  - previous OSM validation numbers remain useful only as legacy comparison evidence
  - they are not the acceptance target for the revised plan

## Risks and Open Questions

- `N3L_A0020000_26` is a road-centerline dataset, not a sidewalk-only network.
  - if loaded naively, it can overstate pedestrian reachability
- The code values (`RDDV`, `DVYN`, `ONSD`) need a formal codebook before they are promoted into routing rules.
- Centerline geometry may still miss private-complex walkways, internal mall connectors, or pedestrian shortcuts.
- Line intersections may not guarantee routable graph connectivity if the source lines are not split at every crossing.
- Existing downstream artifacts (`docs/erd.md`, `etl/sql/schema.sql`, `04-graphhopper-routing-profiles.md`, `current-sprint.md`) still describe OSM-based identity and must be updated to avoid split-brain behavior.
- `03` ETL currently relies mostly on `edgeId` and `geom`, which is good, but any remaining mention of OSM natural keys in validation or handoff logic must be removed.

## Dependencies

- PostGIS 실행 환경
- `etl/data/raw/N3L_A0020000_26.shp`
- `etl/data/raw/N3L_A0020000_26.shx`
- `etl/data/raw/N3L_A0020000_26.dbf`
- `etl/data/raw/N3L_A0020000_26.prj`

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: `road_segments`가 더 이상 OSM natural key를 전제하지 않도록 schema, loader, CSV ETL, GraphHopper handoff가 함께 바뀌어야 한다.

## Hardening Notes For Real Service

- `edgeId`를 유일한 downstream foreign key로 고정한다.
  - `03` CSV ETL은 source-specific natural key를 재식별하지 않는다
  - 모든 후속 적재는 candidate search 후 즉시 `edgeId`로 전환한다
- 로더는 raw source와 topology-derived graph를 분리한다.
  - source line import 성공이 곧바로 routing-grade graph 성공을 뜻하지 않는다
- SHP 적재는 geometry source of truth를 바꾸는 작업이므로, old OSM assumptions를 문서에서 먼저 제거해야 한다.
- 실서비스에서는 road-centerline source와 pedestrian-only source를 eventually hybrid로 운영할 수 있다.
  - 이번 workstream은 우선 canonical source를 SHP로 전환하고, 보행 특화 보강은 이후 workstream으로 분리한다.
