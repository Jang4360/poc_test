# 04 GraphHopper Routing Profiles

## Workstream

`GraphHopper import와 4개 분기 프로필`

## Goal

OSM과 DB 보강 결과를 바탕으로 GraphHopper import 시 custom encoded value를 추가하고, `VISUAL`과 `MOBILITY` 사용자를 위한 4개 custom model 분기를 구성한다.

## Scope

- GraphHopper import 구조
- custom encoded value 추가
- 4개 custom model
- POC용 유연 기준과 기존 엄격 기준 주석 유지

## Non-goals

- 전체 API 완성
- 운영 자동 재import
- 고도화된 프로필 튜닝 완료

## Source Inputs

- Request: GraphHopper import 시 encoded value 추가, custom model 4개 생성, 분기 처리
- Docs: `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`
- Code or architecture references: `etl/data/raw/busan.osm.pbf`, `etl/data/raw/*.csv`, `.env`, `poc/`

## Success Criteria

- [ ] GraphHopper가 접근성 관련 custom encoded value를 읽는다.
- [ ] `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast` 4개 분기가 정의된다.
- [ ] 데이터셋 부족 상태에서도 POC가 동작하도록 완화 기준이 있다.
- [ ] 기존 엄격 기준은 주석으로 보존되어 나중에 복원 가능하다.

## GraphHopper 버전 및 플러그인 배포 방식 결정

- **GH 버전: 8.x 고정** (custom model JSON + LM 가속이 안정화된 계열).
- **배포 방식: GH 독립 컨테이너.** Spring Boot는 `http://graphhopper:8989/route` HTTP API를 호출한다.
- **custom encoded value 주입**: GH의 `CustomEncodedValuesFactory` SPI를 통해 Java 플러그인 JAR로 주입한다.
  - 플러그인 모듈: `graphhopper-plugin/` (루트에 별도 Gradle 모듈로 생성).
  - 빌드 결과 JAR을 GH 컨테이너의 classpath에 마운트한다 (Docker volume 또는 커스텀 이미지).
- **custom model JSON**: 4개 프로필 각각을 `graphhopper-plugin/src/main/resources/custom_models/` 하위에 JSON 파일로 작성한다.
- **import 트리거**: GH 컨테이너 시작 시 자동 import 또는 `POST /change` API 호출로 트리거한다.

## Implementation Plan

- [ ] GraphHopper import 시 다음 값을 반영할 encoded value 체계를 정의한다.
  - `brailleBlockState`
  - `audioSignalState`
  - `curbRampState`
  - `widthState`
  - `surfaceState`
  - `stairsState`
  - `elevatorState`
  - `crossingState`
  - `avgSlopePercent`
- [ ] import 단계의 데이터 주입 방식은 `road_segments` bulk load 후 메모리 lookup 방식으로 고정한다.
  - source of truth는 `road_segments`다.
  - import 직전에 `road_segments` 전체를 한 번에 bulk load 한다.
  - bulk load 결과를 OSM way 분해 기준으로 메모리 map으로 2차 가공한다.
  - OSM edge 처리 중에는 그 map만 조회해 EV를 채운다.
  - per-edge DB query는 금지한다.
  - `sourceWayId + sourceOsmFromNodeId + sourceOsmToNodeId + segmentOrdinal` 기반으로 후보를 구분한다.
- [ ] import 전용 artifact를 별도 파일로 영속화하는 것은 현재 단계의 필수 요구사항이 아니다.
  - 필요하면 나중에 추가할 수 있지만, 현재 기준은 DB bulk load -> in-memory lookup이다.
- [ ] custom model 4개를 만든다.
  - `visual_safe`
  - `visual_fast`
  - `wheelchair_safe`
  - `wheelchair_fast`
- [ ] 라우팅 엔진 가속 전략은 `CH 비활성 + LM 활성`을 기준으로 한다.
  - CH는 custom model 런타임 분기와 충돌하므로 사용하지 않는다.
  - LM은 4개 프로필 모두에 대해 준비한다.
- [ ] 외부 요청과 내부 프로필 매핑을 구현 기준으로 고정한다.
  - `VISUAL + SAFE -> visual_safe`
  - `VISUAL + SHORTEST -> visual_fast`
  - `MOBILITY + SAFE -> wheelchair_safe`
  - `MOBILITY + SHORTEST -> wheelchair_fast`
- [ ] 현재 데이터셋이 완전하지 않은 POC 기준을 적용한다.
  - `UNKNOWN`을 즉시 탈락시키지 않고 감점 또는 보수적 통과 처리
  - `stairsState`, `elevatorState`, `audioSignalState`가 비어 있는 경우 완전 차단 대신 우선순위 패널티 적용
- [ ] 원래 의도한 엄격 기준은 주석으로 남긴다.
  - 예: `stairsState=YES` 즉시 탈락, `avgSlopePercent > 임계값` 즉시 탈락
  - 데이터셋이 추가되면 주석 해제 또는 설정 전환으로 복귀 가능하게 둔다
- [ ] custom model 분기 규칙을 구현 수준으로 명시한다.
  - `visual_safe`
    - HARD EXCLUDE: `avgSlopePercent > 8`, `brailleBlockState == NO`, `crossingState != NO && audioSignalState == NO`
    - PENALTY: `stairsState == YES`, `brailleBlockState == UNKNOWN`, `audioSignalState == UNKNOWN`, `avgSlopePercent > 5`
  - `visual_fast`
    - HARD EXCLUDE: `avgSlopePercent > 8`, `crossingState != NO && audioSignalState == NO`
    - PENALTY: `brailleBlockState == NO`, `stairsState == YES`, `avgSlopePercent > 5`, `brailleBlockState == UNKNOWN`
  - `wheelchair_safe`
    - HARD EXCLUDE: `stairsState == YES`, `surfaceState IN {GRAVEL, UNPAVED}`, `widthState == NARROW`, `avgSlopePercent > 3`, `crossingState != NO && curbRampState == NO`
    - PENALTY: `widthState == UNKNOWN`, `curbRampState == UNKNOWN`, `stairsState == UNKNOWN`
  - `wheelchair_fast`
    - HARD EXCLUDE: `stairsState == YES`, `surfaceState IN {GRAVEL, UNPAVED}`, `widthState == NARROW`, `avgSlopePercent > 5`
    - PENALTY: `avgSlopePercent > 3`, `widthState == UNKNOWN`, `stairsState == UNKNOWN`

## Validation Plan

- [ ] 같은 출발지/도착지에 대해 4개 프로필 결과가 실제로 분기되는지 확인한다.
- [ ] 데이터 부족 구간에서 POC 기준이 지나치게 낙관적이지 않은지 확인한다.
- [ ] bulk preload 방식이 import loop 중 DB round trip 없이 동작하는지 확인한다.
- [ ] LM 적용 후 4개 프로필 모두 import/load-only 운영이 가능한지 확인한다.
- [ ] 주석 처리된 엄격 기준이 나중에 되돌릴 수 있도록 코드에 명확히 남는지 검토한다.

## Risks and Open Questions

- GraphHopper가 DB 보강값을 import에 반영하는 구조는 복잡하지만, per-edge query를 허용하면 로딩 시간이 급격히 악화된다.
- 완화 기준이 너무 느슨하면 프로필 차이가 작아질 수 있다.
- 현재 POC 데이터셋으로는 `surfaceState`, `curbRampState`, `elevatorState` 등 일부 값이 충분히 채워지지 않을 수 있어, 실제 profile divergence를 측정하며 보정해야 한다.

## Dependencies

- `02`, `03`의 ETL 결과
- GraphHopper 실행 환경

## Handoff

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 백엔드가 HTTP로 호출 가능한 안정적인 프로필 라우팅 엔드포인트가 있어야 한다

## Hardening Notes For Real Service

- GraphHopper import must use the same canonical segment identity as ETL: `(sourceWayId, sourceOsmFromNodeId, sourceOsmToNodeId, segmentOrdinal)`. Do not fall back to the old 3-column key.
- The preload map should be built from `road_segments` once per import and keyed by the 4-column natural key, with `edgeId` and encoded-value payload attached to each entry.
- If an OSM edge cannot be matched to exactly one preloaded segment entry, import should count and report it explicitly instead of silently picking the first candidate.
- Pre-import validation should compare the preload artifact count with `road_segments` count and confirm that the 4-column unique constraint and `GIST` index still exist before GraphHopper starts its long-running import.
- Import logs should separate `exact match`, `no match`, and `ambiguous match` counts so route-quality regressions can be traced back to data identity problems rather than model tuning.
