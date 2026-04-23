# 04 GraphHopper 라우팅 프로필 레거시 계획

## 워크스트림

`OSM 기반 GraphHopper 프로필 실험안`

## 목표

OSM import 이후 DB 보강값을 덧입히는 방식으로 GraphHopper custom encoded value와 4개 프로필을 구성하는 초기 실험안을 보존한다.

## 범위

- OSM import 기반 GraphHopper 실험 구조 기록
- custom encoded value 정의 초안
- 4개 custom model 초안
- 이후 `04-graphhopper-routing-profiles_v2.md`와 대비되는 레거시 설계 근거 보관

## 비목표

- 현재 정규 구현안으로 채택
- 전체 API 구현
- 운영 자동 import

## 입력 근거

- `etl/raw/busan.osm.pbf`
- `docs/prd.md`
- `docs/erd.md`
- `.env`
- `poc/`

## 성공 기준

- [ ] OSM 중심 import 방식을 사용했던 초기 설계 의도를 문서로 남긴다.
- [ ] `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast`의 초안 기준을 남긴다.
- [ ] 현재 V2 설계와 어떤 점이 다른지 비교할 수 있다.

## 구현 계획

- [ ] OSM edge를 기준으로 DB 보강값을 join하는 초기 import 방식을 정리한다.
- [ ] encoded value 후보 필드를 정리한다.
  - `brailleBlockState`
  - `audioSignalState`
  - `curbRampState`
  - `widthState`
  - `surfaceState`
  - `stairsState`
  - `elevatorState`
  - `crossingState`
  - `avgSlopePercent`
- [ ] 4개 custom model의 초기 가정값을 기록한다.
- [ ] 이 문서는 현재 구현 기준이 아니라 레거시 참고안이라는 점을 명시한다.

## 검증 계획

- [ ] 현재 정규안과의 차이를 검토한다.
- [ ] OSM natural key 의존이 왜 문제였는지 설명 가능해야 한다.
- [ ] 이 문서를 실행 기준으로 오인하지 않도록 README나 상위 계획과 충돌이 없는지 확인한다.

## 위험 및 열린 질문

- OSM natural key 기반 join은 SHP 우선 구조로 전환된 현재 계획과 맞지 않는다.
- 레거시 문서를 그대로 두면 잘못된 구현 경로를 다시 선택할 위험이 있다.

## 의존성

- `busan.osm.pbf`
- GraphHopper OSM import 실험 환경

## 핸드오프

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 이 문서는 참고 자료일 뿐이며, 실제 구현은 `04-graphhopper-routing-profiles_v2.md`를 따라야 한다.
