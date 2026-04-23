# 01 저장소 정렬 및 실행 기반 정비

## 워크스트림

`구현 기반 정렬`

## 목표

부산 이음길 MVP가 Spring Boot + PostGIS + ETL + GraphHopper 기준선 위에서 일관되게 진행되도록 저장소 구조, 실행 경계, 이름 규칙을 정리한다.

## 범위

- `PostgreSQL + PostGIS`를 정규 데이터 저장소로 고정
- `poc/`를 백엔드 시작점으로 명확화
- `etl/` 파이썬 런타임과 스키마/스크립트 골격 정리
- `graphhopper-plugin/` 및 Docker 실행 경계 정리
- 장애 유형, 경로 옵션, GraphHopper 프로필 명명 규칙 확정
- MVP 범위와 V2 범위 분리

## 비목표

- 전체 경로 API 구현
- 실제 ETL 적재 로직 완성
- Android 앱 완성

## 입력 근거

- `docs/prd.md`
- `docs/기능명세서.md` 또는 현재 기능 명세 문서
- `docs/erd.md`
- `docs/erd_v2.md`
- `.env`
- `poc/`
- `etl/raw/`

## 성공 기준

- [x] 런타임 기준선이 `PostgreSQL + PostGIS`로 고정되었다.
- [x] 백엔드, ETL, GraphHopper 경계가 저장소에서 명시된다.
- [x] `DisabilityType`, `RouteOption`, GraphHopper 프로필 명명 규칙이 구현 기준으로 정리되었다.
- [x] GraphHopper는 HTTP 서비스로 취급되고 `road_segments`가 이후 워크스트림의 네트워크 기준 테이블로 유지된다.
- [x] Docker Compose 기준 전체 기동 검증이 통과했다.

## 구현 계획

- [x] 기본 Spring Boot 식별자를 부산 이음길 기준으로 치환했다.
  - `group`: `kr.ssafy.ieumgil`
  - 애플리케이션 이름: `ieumgil-backend`
  - Java 패키지: `kr.ssafy.ieumgil.backend`
- [x] 백엔드 기준 의존성과 런타임 설정을 정리했다.
  - `spring-boot-starter-actuator`
  - `hibernate-spatial`
  - `jts-core`
  - datasource, health, GraphHopper base URL 설정
- [x] 백엔드 컨테이너 패키징을 추가했다.
  - `poc/Dockerfile`
  - `/actuator/health` 기반 healthcheck
- [x] ETL 실행 골격을 추가했다.
  - `etl/requirements.txt`
  - `etl/common/db.py`
  - 번호형 ETL 스크립트 진입점
  - `etl/sql/schema.sql`
- [x] 리뷰 후 보정 사항을 반영했다.
  - 기본 `com/example/poc` 패키지 잔재 제거
  - Hibernate 6 기준으로 dialect 강제 설정 제거
  - 주요 테이블 PK를 `GENERATED ALWAYS AS IDENTITY`로 정리
  - `hazard_reports.user_id` 외래키 추가
  - Docker host Postgres 포트를 `25432`로 조정
  - psycopg3와 `pyshp` 기반 ETL 런타임으로 정리
- [x] GraphHopper 모듈과 실행 골격을 추가했다.
  - `graphhopper-plugin/`
  - `docker/graphhopper/Dockerfile`
  - GraphHopper 설정 및 엔트리포인트
- [x] 저장소 루트 서비스 오케스트레이션을 정리했다.
  - `docker-compose.yml`
  - `postgres`, `graphhopper`, `backend` 연동
  - `etl/raw/`, `etl/sql/schema.sql` 마운트
- [x] 구현 시점 이름 규칙을 확정했다.
  - 사용자 축: `VISUAL | MOBILITY`
  - 경로 옵션: `SAFE | SHORTEST | PUBLIC_TRANSPORT`
  - GraphHopper 프로필: `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast`
- [x] V2 범위를 분리했다.
  - 완전한 Android 앱
  - LLM UI
  - 계정 동기화 및 운영 자동화
- [x] 장소 CSV 입력 기준을 확정했다.
  - `place_merged_broad_category_final.csv`를 정규 입력으로 사용

## 검증 계획

- [x] `scripts/verify.sh` 구조 검증 통과
- [x] `scripts/smoke.sh` 스모크 검증 통과
- [x] `python -m compileall etl` 통과
- [x] `docker compose config` 통과
- [x] `docker compose up -d postgres graphhopper backend` 통과
- [x] 주요 place CSV 헤더 일치 확인

## 위험 및 열린 질문

- 템플릿 저장소 흔적이 남아 있으면 이후 계획과 코드가 실제 제품 맥락과 어긋날 수 있다.
- 로컬 환경이 Windows + Git Bash 기준이므로 Bash 스크립트가 이를 견뎌야 한다.
- 운영형 서비스보다는 로컬 검증형 POC가 우선이므로 과도한 인프라 자동화는 보류한다.

## 의존성

- `.env`의 로컬 포트 및 DB 접속 정보
- Docker Desktop 또는 동등한 컨테이너 실행 환경

## 핸드오프

- Build skill: `implement-feature`
- Validation skill: `check`
- Ship readiness note: 이후 워크스트림은 이 저장소 경계와 런타임 기준선을 전제로 진행한다.
