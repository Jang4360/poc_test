# 04 GraphHopper Routing Profiles V2

## Workstream

`road_segments direct graph import 기반 GraphHopper 재설계`

## Goal

`OSMReader`와 `datareader.file=/data/*.osm.pbf` 전제를 제거하고, `road_nodes` / `road_segments`만으로 GraphHopper internal graph를 구성해 `VISUAL`과 `MOBILITY` 사용자를 위한 4개 프로필 라우팅을 가능하게 한다.

## Why This Variant Exists

- 기존 [04-graphhopper-routing-profiles.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/.ai/PLANS/current-sprint/04-graphhopper-routing-profiles.md)는 `OSMReader`가 만든 GraphHopper edge에 DB 보강값을 매핑하는 구조다.
- 현재 `02`는 canonical network source를 `busan.osm.pbf`에서 `N3L_A0020000_26` SHP 기반 `road_segments`로 전환하는 방향으로 재설계되고 있다.
- 이 경우 `sourceWayId + sourceOsmFromNodeId + sourceOsmToNodeId + segmentOrdinal` 같은 OSM natural key는 더 이상 안정적인 import key가 아니다.
- 따라서 `GraphHopper import`도 `OSM 기반 edge 생성 -> DB 보강`이 아니라 `DB/SHP-derived edge 생성 -> GraphHopper graph build` 구조로 재설계해야 한다.

## Scope

- `road_segments` direct graph import 전략 정의
- GraphHopper custom bootstrap/application 구조 정의
- `road_nodes`, `road_segments`를 GraphHopper `BaseGraph` / `LocationIndexTree`로 전개하는 로직 설계
- custom encoded value와 4개 custom model을 direct graph import 구조에 맞게 재배치
- import artifact, validation, failure mode, 성능 기준 정의

## Non-goals

- Spring Boot API 전체 구현
- 대중교통 오케스트레이션 구현
- 운영 자동 재import 완성
- CH/LM 최적화의 최종 튜닝
- SHP와 OSM을 동시에 merge하는 하이브리드 graph import 구현

## Source Inputs

- Request: GraphHopper import 자체를 `road_segments` 기반으로 재작성
- Docs:
  - [docs/erd.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/docs/erd.md)
  - [2026-04-12_경로_API_명세.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/docs/API/보행_네트워크_도메인/2026-04-12_경로_API_명세.md)
- Code and architecture references:
  - [02-osm-schema-and-network-load.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/.ai/PLANS/current-sprint/02-osm-schema-and-network-load.md)
  - [03-csv-etl-and-reference-data.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/.ai/PLANS/current-sprint/03-csv-etl-and-reference-data.md)
  - [04-graphhopper-routing-profiles.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/.ai/PLANS/current-sprint/04-graphhopper-routing-profiles.md)
  - [application.yaml](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/poc/src/main/resources/application.yaml)
  - `graphhopper-plugin/` planned module boundary from workstream `01`

## Success Criteria

- [ ] GraphHopper가 `PBF/OSMReader` 없이 `road_nodes` / `road_segments`만으로 그래프를 구성하는 설계가 정의된다.
- [ ] `edgeId`를 canonical handoff key로 사용하는 import artifact와 runtime lookup 구조가 정의된다.
- [ ] `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast` 4개 프로필이 direct graph import 구조에서도 유지된다.
- [ ] `snap`, `route geometry`, `path details`, `encoded values`가 어떤 계층에서 채워지는지 명시된다.
- [ ] `road_nodes`가 실제 Graph vertex로 사용할 수 있는지와 `road_segments`가 vertex-to-vertex 분해를 만족하는지 검증 전략이 정의된다.
- [ ] 구현 순서와 validation path가 실제 build stage로 바로 넘길 수 있을 정도로 구체적이다.

## Design Shift

- 기존 구조:
  - `OSM PBF -> OSMReader -> GraphHopper graph`
  - `road_segments`는 OSM edge에 EV를 붙이기 위한 side table
- 새 구조:
  - `road_nodes + road_segments -> DirectGraphImporter -> GraphHopper BaseGraph`
  - `road_segments`가 graph source of truth
  - OSM은 더 이상 import 필수 입력이 아니다

## Target Architecture

### 1. Data Extraction Stage

- DB에서 `road_nodes`, `road_segments` 전체를 bulk load 한다.
- 이 단계는 GraphHopper import loop 안에서 per-edge DB query를 하지 않는다.
- 추출 결과는 메모리 객체 또는 optional snapshot artifact로 만든다.

필수 추출 필드:
- `road_nodes`
  - `vertexId`
  - `point`
- `road_segments`
  - `edgeId`
  - `fromNodeId`
  - `toNodeId`
  - `geom`
  - `lengthMeter`
  - `walkAccess`
  - `brailleBlockState`
  - `audioSignalState`
  - `curbRampState`
  - `widthState`
  - `surfaceState`
  - `stairsState`
  - `elevatorState`
  - `crossingState`
  - `avgSlopePercent`
  - `widthMeter`

### 2. Import Artifact Stage

- GraphHopper import 전에 `graph_import_edges` 수준의 internal artifact를 만든다.
- 이 artifact는 DB schema가 아니라 import 전용 DTO/record다.

권장 구조:
- `ImportNode`
  - `vertexId`
  - `lat`
  - `lon`
- `ImportEdge`
  - `edgeId`
  - `fromVertexId`
  - `toVertexId`
  - `geometry`
  - `distanceMeter`
  - `isBidirectional` 또는 `forwardAllowed/backwardAllowed`
  - accessibility fields

핵심 규칙:
- GraphHopper 내부 edge와 `road_segments.edgeId` 사이의 1:1 대응을 유지한다.
- import 중 새 surrogate natural key를 만들지 않는다.
- `edgeId -> ghEdgeId` 매핑 테이블을 import 결과 artifact로 남긴다.

### 3. Graph Build Stage

- `OSMReader` 대신 custom builder가 `BaseGraph`에 직접 node/edge를 추가한다.
- 필요한 구성요소:
  - `EncodingManager`
  - custom encoded values
  - `BaseGraph`
  - `NodeAccess`
  - `LocationIndexTree`

계획된 흐름:
1. `road_nodes`를 순회하며 `NodeAccess`에 lat/lon을 설정
2. `road_segments`를 순회하며 GraphHopper edge 생성
3. edge distance와 directionality 설정
4. edge geometry를 fetchWayGeometry용 point list로 저장
5. custom encoded value를 `road_segments` 값으로 채움
6. import 후 `LocationIndexTree` 생성

주의:
- GraphHopper의 edge id는 내부적으로 다시 부여될 수 있으므로 `edgeId -> ghEdgeId` map이 필요하다.
- 반환 payload의 세그먼트 단위 설명은 여전히 `road_segments.edgeId`를 기준으로 복원해야 한다.
- direct import 이전에 `road_nodes` / `road_segments`가 실제 라우팅 가능한 topology인지 먼저 검증해야 한다.
  - `road_nodes`가 단순 endpoint 모음이 아니라 교차/분기 지점을 대표하는 vertex인지 확인 필요
  - `road_segments`가 반드시 `fromNodeId -> toNodeId` 단위로 닫힌 선분인지 확인 필요

### 4. Snap Stage

- 클라이언트 입력 좌표는 더 이상 OSM edge에 snap하지 않는다.
- `LocationIndexTree`가 direct graph import 결과 위에서 nearest edge를 찾는다.
- snap 결과는 `ghEdgeId`로 나오므로, 응답 조립 단계에서 다시 `edgeId` 또는 `road_segments` row로 복원한다.

### 5. Route Response Reconstruction

- Path 계산 결과의 GraphHopper edge sequence를 `edgeId` sequence로 역매핑한다.
- API 응답의 `segments[].geometry`, 상태 필드, `avgSlopePercent`는 `road_segments`를 source of truth로 사용한다.
- GraphHopper는 비용 계산 엔진이고, 응답 직렬화의 canonical source는 `road_segments`다.

## Encoded Value Strategy

- 기존 workstream `04`의 custom encoded values는 유지하되 source가 바뀐다.
- Import source:
  - before: OSM edge + DB lookup
  - after: direct `road_segments`

필수 EV:
- `brailleBlockState`
- `audioSignalState`
- `curbRampState`
- `widthState`
- `surfaceState`
- `stairsState`
- `elevatorState`
- `crossingState`
- `avgSlopePercent`

추가 후보:
- `walkAccess`
- `widthMeter`

권장 사항:
- `widthMeter`는 직접 cost 계산보다 `widthState` 보조 검증용으로 유지
- `walkAccess`는 direct import 구조에서 매우 중요해지므로 EV 또는 import exclusion gate로 승격 검토

## Directionality Plan

- OSM처럼 명시적 `oneway`가 없는 source도 있을 수 있으므로 direct graph import에서 방향성 규칙을 분리한다.
- 초기 POC 기준:
  - 모든 `road_segments`를 양방향으로 적재
  - 단, `ONSD` 등 source direction code가 명확해지면 later hardening에서 일방통행/분리 보행 방향 적용
- 이 결정은 API correctness보다 false exclusion 회피를 우선한 POC 판단이다.

## Custom Model Plan

- 4개 모델은 유지한다.
  - `visual_safe`
  - `visual_fast`
  - `wheelchair_safe`
  - `wheelchair_fast`

- 차이는 import source가 아니라 EV 공급 방식이다.
- direct graph import 후에도 custom model JSON은 동일한 개념으로 유지 가능하다.

POC 정책:
- `UNKNOWN`을 즉시 탈락시키지 않고 penalty 중심
- direct graph import 초기에 `walkAccess`와 `surfaceState`가 충분히 채워지지 않으면 보수적 penalty로 시작

## Implementation Plan

- [ ] `04-graphhopper-routing-profiles_v2.md`를 기준으로 `graphhopper-plugin/` 또는 동등한 Java 모듈 경계를 확정한다.
- [ ] 기존 `datareader.file=/data/*.osm.pbf` 기반 bootstrap을 optional legacy path로 낮추고, direct graph import bootstrap을 새 canonical path로 설계한다.
- [ ] `RoadSegmentsGraphSnapshotBuilder`를 설계한다.
  - DB에서 `road_nodes`, `road_segments`를 bulk load
  - import DTO 생성
  - `edgeId -> import edge` map 구성
- [ ] topology validation stage를 `RoadSegmentsGraphSnapshotBuilder` 앞단 또는 내부에 설계한다.
  - `road_segments.fromNodeId`, `road_segments.toNodeId`가 모두 존재하는 `road_nodes.vertexId`를 참조하는지 확인
  - `fromNodeId == toNodeId` self-loop count를 집계
  - zero-length 또는 near-zero-length segment count를 집계
  - 동일 좌표의 중복 vertex cluster와 unsnapped near-miss endpoint를 집계
  - line intersection이 존재하지만 공유 vertex가 없는 crossing candidate를 집계
- [ ] `road_nodes`의 vertex 적합성 검증 규칙을 정의한다.
  - degree 1/2/3+ 분포를 집계
  - 대표 hotspot에서 교차로가 하나의 vertex로 묶였는지 확인
  - 과도한 degree-2 연속 vertex가 남아 있으면 segment 과분해 여부를 리포트
- [ ] `road_segments`의 vertex-to-vertex 분해 적합성 검증 규칙을 정의한다.
  - 모든 segment의 시작점/끝점이 각각 대응 vertex 좌표와 tolerance 내에서 일치하는지 확인
  - 중간 교차점이 있는데도 분해되지 않은 line을 탐지하는 규칙 정의
- [ ] `RoadSegmentsGraphImporter`를 설계한다.
  - `BaseGraph` 생성
  - `NodeAccess` 채움
  - GH edge 생성
  - `edgeId -> ghEdgeId` mapping 유지
- [ ] `fetchWayGeometry`에 필요한 edge geometry 저장 규칙을 정의한다.
- [ ] `LocationIndexTree` 생성과 snap API compatibility를 검증한다.
- [ ] custom encoded value writing 계층을 `OSMReader hook`가 아니라 `DirectGraphImporter` 단계로 이동한다.
- [ ] route response reconstruction 계층을 설계한다.
  - path edge sequence -> `edgeId` 복원
  - `road_segments` 조인
  - API 응답 shape 맞춤
- [ ] import artifact persistence 여부를 결정한다.
  - 권장안: 초기 구현은 메모리 기반
  - hardening: import summary JSON + edge map summary만 파일로 남김
- [ ] 4개 custom model JSON을 direct graph import 구조에서도 그대로 읽게 유지한다.
- [ ] 기존 [04-graphhopper-routing-profiles.md](/Users/jangjooyoon/Desktop/JooYoon/ssafy/poc_test/.ai/PLANS/current-sprint/04-graphhopper-routing-profiles.md)의 OSM natural key 가정 제거를 위한 follow-up diff 목록을 만든다.

## Validation Plan

- [ ] topology smoke
  - `road_segments.fromNodeId`, `road_segments.toNodeId` FK completeness 확인
  - self-loop 0건 또는 explicit allowlist 확인
  - zero-length segment 0건 확인
  - 교차 후보 중 shared vertex 없는 건수를 리포트
- [ ] vertex adequacy smoke
  - 대표 구역(장산역, 센텀시티, 서면)에서 실제 교차로가 vertex로 표현되는지 시각 검증
  - disconnected component count와 giant component 비율 확인
- [ ] graph build smoke
  - `road_nodes` count vs GH node count 비교
  - `road_segments` count vs imported GH edge count 비교
- [ ] mapping smoke
  - `edgeId -> ghEdgeId` bijection 또는 expected cardinality 확인
- [ ] snap smoke
  - 장산역, 센텀시티, 서면 등 대표 좌표에서 nearest edge가 실제 도로 구간에 snap되는지 확인
- [ ] route smoke
  - 같은 출발/도착지로 4개 프로필이 실제로 분기되는지 확인
- [ ] geometry smoke
  - GH path geometry와 `road_segments.geom` 기반 응답 geometry가 일관되는지 확인
- [ ] performance smoke
  - import 시간
  - preload 메모리 사용량
  - route latency
- [ ] regression smoke
  - direct graph import 사용 시 기존 `/routes/search` API 응답 shape가 깨지지 않는지 확인

## Validation Targets For First Prototype

- import complete without PBF
- `road_nodes` / `road_segments` 기반 graph build 성공
- 장산역 5km 범위 내 임의 start/end에서 최소 1개 경로 반환
- `wheelchair_safe`와 `wheelchair_fast`가 동일 경로만 반환하는 상태라도 오류 없이 분기 가능
- `edgeId -> ghEdgeId` 역매핑 누락 0건

## Risks and Open Questions

- 이 방식은 GraphHopper의 기본 OSM import path를 벗어나므로, 내부 API 버전 변경에 민감하다.
- `road_nodes`가 truly routable topology인지 `02`에서 보장되지 않으면 direct graph import가 성공해도 실제 경로 품질이 낮을 수 있다.
- `road_nodes`가 endpoint-derived 방식으로만 생성되면, 실제 교차점 split이 누락된 구간에서 GraphHopper가 연결되지 않은 graph를 만들 수 있다.
- `road_segments`가 vertex-to-vertex로 분해되지 않으면 snap은 되더라도 turn 가능성이 잘못 계산될 수 있다.
- `LocationIndexTree`와 edge geometry 저장 방식이 OSM import와 완전히 동일하지 않을 수 있어, snap 품질 검증이 필수다.
- `road_segments`가 양방향인지 단방향인지 source semantics가 약하면 경로가 과도하게 낙관적일 수 있다.
- `edgeId` 기준 응답 복원이 가능해도, turn instruction/TTS 품질은 OSM-derived naming보다 떨어질 수 있다.
- direct graph import가 가능하더라도 LM 준비 과정이 same-path로 동작하는지 별도 실험이 필요하다.

## Dependencies

- `02`의 source-agnostic `road_nodes`, `road_segments`
- `03`의 accessibility enrichment
- GraphHopper plugin/module scaffold
- PostGIS bulk load path

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 이 경로는 단순 설정 변경이 아니라 GraphHopper import subsystem 자체를 재작성하는 작업이므로, `02` schema delta와 함께 움직여야 한다.

## Hardening Notes For Real Service

- direct graph import의 canonical identity는 `edgeId`다.
- GraphHopper internal edge ids는 외부 API에 노출하지 않는다.
- import summary는 최소한 다음을 남긴다.
  - DB node count
  - DB edge count
  - imported GH node count
  - imported GH edge count
  - mapping 누락 수
  - snap 실패 수
- 장기적으로는 `road_segments` direct import와 OSM-derived metadata를 hybrid로 결합할 수 있지만, 첫 구현은 하나의 canonical source만 사용해야 디버깅 가능하다.
