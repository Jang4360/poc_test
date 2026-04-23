# 04 GraphHopper 라우팅 프로필 V2

## 워크스트림

`road_segments 직접 import 기반 GraphHopper 구성`

## 목표

`OSMReader`와 `*.osm.pbf` 의존을 제거하고, `road_nodes`, `road_segments`만으로 GraphHopper 내부 그래프를 구성해 `VISUAL`, `MOBILITY` 사용자 축에 맞는 4개 프로필을 운영할 수 있게 한다.

## 범위

- `road_nodes`, `road_segments` direct graph import 구조 정의
- GraphHopper custom encoded value와 custom model 정의
- `edgeId` 중심 import artifact 및 lookup 설계
- snap, route geometry, path details, encoded value 노출 구조 설계
- 성능 및 실패 모드 검증 계획 정리

## 비목표

- Spring Boot API 전체 구현
- 운영 자동 import 완성
- CH/LM 최종 튜닝 완료
- SHP와 OSM을 혼합하는 하이브리드 graph import

## 입력 근거

- `.ai/PLANS/current-sprint/02-osm-schema-and-network-load.md`
- `.ai/PLANS/current-sprint/03-csv-etl-and-reference-data.md`
- `docs/erd.md`
- `docs/erd_v2.md`
- `poc/src/main/resources/application.yaml`
- `graphhopper-plugin/`

## 성공 기준

- [ ] GraphHopper가 OSM PBF 없이 `road_nodes`, `road_segments`만으로 그래프를 구성하는 구조가 정의되어 있다.
- [ ] `edgeId`를 기준으로 GraphHopper edge와 정규 세그먼트를 연결하는 artifact 구조가 정의되어 있다.
- [ ] `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast` 4개 프로필의 규칙이 정의되어 있다.
- [ ] snap, route geometry, path details에 어떤 encoded value를 태울지 명시되어 있다.
- [ ] 구현 순서와 검증 순서가 실제 build 단계로 바로 옮길 수 있을 정도로 구체적이다.

## 설계 전환

- 기존 레거시 방향:
  - `OSM PBF -> OSMReader -> GraphHopper graph`
  - `road_segments`는 OSM edge에 보강값을 매핑하는 side table 성격
- 현재 V2 방향:
  - `road_nodes + road_segments -> DirectGraphImporter -> GraphHopper BaseGraph`
  - `road_segments`가 그래프 source of truth
  - OSM은 import 필수 입력이 아님

## 구현 계획

- [ ] DB에서 `road_nodes`, `road_segments`를 bulk load하는 추출 단계를 만든다.
  - per-edge DB query를 금지한다.
  - 추출 결과는 import 전용 DTO 또는 snapshot artifact로 만든다.
- [ ] import 전용 artifact 구조를 정의한다.
  - `ImportNode(vertexId, lat, lon)`
  - `ImportEdge(edgeId, fromVertexId, toVertexId, geometry, distanceMeter, accessibility payload)`
- [ ] Graph build 단계를 정의한다.
  - `road_nodes`를 GraphHopper vertex로 배치
  - `road_segments`를 edge로 변환
  - geometry, distance, 방향성, encoded value 동시 반영
- [ ] 다음 encoded value 세트를 직접 graph import에 연결한다.
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
- [ ] 4개 프로필을 custom model로 정의한다.
  - `visual_safe`
  - `visual_fast`
  - `wheelchair_safe`
  - `wheelchair_fast`
- [ ] 프로필 매핑 규칙을 고정한다.
  - `VISUAL + SAFE -> visual_safe`
  - `VISUAL + SHORTEST -> visual_fast`
  - `MOBILITY + SAFE -> wheelchair_safe`
  - `MOBILITY + SHORTEST -> wheelchair_fast`
- [ ] 현재 데이터 공백에 대응하는 POC 규칙을 정의한다.
  - `UNKNOWN`은 즉시 배제보다 보수적 penalty 우선
  - 특정 값이 비어 있어도 전체 경로 탐색이 깨지지 않도록 fallback 유지
- [ ] import 결과 artifact에 `edgeId -> ghEdgeId` 매핑을 남긴다.

## 검증 계획

- [ ] 동일한 출발/도착점에서 4개 프로필 결과가 실제로 분기되는지 확인한다.
- [ ] direct import 루프에서 DB round trip이 없는지 확인한다.
- [ ] GraphHopper vertex 수와 `road_nodes` 수, import edge 수와 `road_segments` 수를 비교한다.
- [ ] `edgeId`와 GraphHopper edge 간 매핑 누락/중복이 없는지 확인한다.
- [ ] 데이터 공백이 있는 구간에서도 profile divergence가 과도하게 무너지지 않는지 샘플 검증한다.

## 위험 및 열린 질문

- direct import는 OSMReader 경로보다 구현 복잡도가 높다.
- encoded value가 많아질수록 import 메모리 사용량과 디버깅 비용이 커진다.
- `surfaceState`, `curbRampState`, `elevatorState` 같은 속성은 아직 데이터 밀도가 낮아 프로필 차이가 약할 수 있다.

## 의존성

- `02`의 정규 네트워크 적재 결과
- `03`의 접근성 속성 보강 결과
- `graphhopper-plugin/` 모듈과 GraphHopper 실행 환경

## 핸드오프

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: GraphHopper는 더 이상 OSM natural key에 의존하지 않고 `edgeId`와 direct import artifact를 기준으로 동작해야 한다.
