# 05 Backend API And Orchestration

## Workstream

`Spring Boot API와 대중교통 경로 조합`

## Goal

현재 `poc/` Spring Boot 스캐폴드를 기반으로 도보 경로, 대중교통 보조 경로, 시설 조회, 익명 제보를 제공하는 API 흐름을 만든다.

## Scope

- 경로 탐색 API
- 시설 조회 API
- 익명 제보 API
- ODsay/BIMS 연동
- local-first MVP 범위 정리

## Non-goals

- 완전한 회원 기능
- 운영 자동화
- 관리자 백오피스

## Source Inputs

- Request: `poc` 기반 백엔드에 ETL과 GraphHopper 결과를 연결
- Docs: `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`
- Code or architecture references: `poc/`, `.env`, `etl/data/raw/`

## Success Criteria

- [ ] `SAFE`, `SHORTEST`, `PUBLIC_TRANSPORT`를 반환하는 API 경로가 정의된다.
- [ ] 시설 조회와 익명 제보 API의 테이블 사용 방식이 최신 ERD와 맞는다.
- [ ] 저상버스와 지하철 엘리베이터를 이용한 대중교통 후보 필터링이 정의된다.

## `poc/build.gradle` 추가 필요 의존성

- `org.hibernate.orm:hibernate-spatial` — GEOMETRY 컬럼 JPA 엔티티 매핑 필수
- `org.locationtech.jts:jts-core` — Point, LineString 등 Geometry 타입

## 최소 API 계약 (구현 전 고정)

```
POST /api/v1/routes/search
Request:  { "disabilityType": "VISUAL|MOBILITY", "startPoint": { "lat": float, "lng": float }, "endPoint": { "lat": float, "lng": float }, "routeOption": "SAFE|SHORTEST|PUBLIC_TRANSPORT" }
Response: { "options": [ { "routeOption": "SAFE|SHORTEST|PUBLIC_TRANSPORT", "segments": [...] } ] }

GET /api/v1/places?lat=&lng=&radius=&category=
Response: { "places": [ { "placeId": int, "name": str, "category": str, "point": {...}, "features": [...] } ] }

POST /api/v1/hazards/report
Request:  { "reportType": "CONSTRUCTION|OBSTACLE|DAMAGE|OTHER", "description": str, "lat": float, "lng": float, "address": str }
Response: { "reportId": int, "status": "PENDING" }
```

## Implementation Plan

- [ ] `poc/`에 `routing`, `transit`, `places`, `hazards`, `common` 패키지 구조를 만든다.
- [ ] `/routes/search` API는 사용자 유형과 출발/도착 좌표를 입력받아 3개 옵션을 반환한다.
- [ ] 도보 옵션은 GraphHopper 4개 프로필을 사용자 유형과 옵션 조합에 맞게 호출한다.
- [ ] `PUBLIC_TRANSPORT`는 ODsay 후보를 받아 저상버스와 엘리베이터 조건으로 재필터링한다.
  - `low_floor_bus_routes`로 버스 노선 적합성 확인
  - `subway_station_elevators`로 승하차역 접근성 확인
- [ ] 장소 조회 API는 `places`, `place_accessibility_features`를 함께 조회한다.
- [ ] 제보 API는 `hazard_reports`, `hazard_report_images`를 익명 기준으로 저장한다.
- [ ] local-first MVP 원칙에 따라 사용자 인증 의존 기능은 후순위로 둔다.

## Validation Plan

- [ ] 익명 제보가 사용자 계정과 연결되지 않는지 확인한다.
- [ ] 시설 조회 응답이 `places`와 `place_accessibility_features`를 일관되게 조합하는지 확인한다.
- [ ] `PUBLIC_TRANSPORT` 후보에서 저상버스/엘리베이터 조건 불충족 시 명시적으로 탈락하는지 확인한다.

## Risks and Open Questions

- `users`, `bookmarks`, `favorite_routes`는 ERD에 있지만 MVP POC의 핵심이 아니므로 구현 우선순위 분리가 필요하다.
- ODsay 응답과 DB의 station/route 식별자 정합성이 실제 난이도를 좌우한다.

## Dependencies

- `03`의 참조 데이터 적재
- `04`의 GraphHopper 라우팅 엔드포인트

## Handoff

- Build skill: `start`
- Validation skill: `check`
- Ship readiness note: 핵심 API가 최신 ERD의 테이블 관계와 충돌 없이 동작해야 한다
