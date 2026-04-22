# 01 Setup And Repo Alignment

## Workstream

`구현 기반 정렬`

## Goal

최신 ERD와 현재 저장소 상태를 기준으로 MVP POC가 실제로 구현 가능한 디렉토리 구조, DB 선택, 실행 기준을 고정한다.

## Scope

- `PostgreSQL + PostGIS` 기준 확정
- `poc/`를 백엔드 출발점으로 사용할지 정리
- ETL, DB, GraphHopper, API의 실행 순서 정리
- 도메인 열거형과 내부/외부 프로필 명명 규칙 정리
- `road_segments`를 GraphHopper import의 source of truth로 고정
- V2로 미룰 범위 분리

## Non-goals

- 세부 API 구현
- ETL 자동화 구현
- 최종 모바일 앱 패키징

## Current Repository Baseline (2026-04-21 기준)

- `poc/`: Spring Boot 3.5.13 / Java 21 스캐폴드, `PocApplication.java` 하나만 존재. 패키지·도메인 코드 없음.
- `etl/`: `data/raw/` 이하 8개 원시 파일만 존재. Python 스크립트, `requirements.txt`, `venv` 없음.
- `scripts/`: 하니스 헬퍼 스크립트 존재. 프로젝트 전용 smoke 명령 미설정.
- `docker-compose.yml` 없음 — PostGIS, GraphHopper 컨테이너 미설정.
- `poc/build.gradle`: JPA, Web, Validation, Lombok, PostgreSQL 드라이버만 있음. Hibernate Spatial, GH 클라이언트 없음.

## Source Inputs

- Request: 현재 `ai/PLANS`를 `docs/plans` 없이 구현 가능한 계획으로 전면 재작성
- Docs: `docs/prd.md`, `docs/기능명세서.md`, `docs/erd.md`
- Code or architecture references: `.env`, `poc/`, `etl/data/raw/`

## Success Criteria

- [x] DB와 런타임 선택이 최신 ERD와 현재 리포에 맞게 정리된다.
- [x] 구현 순서가 OSM 적재부터 API 검증까지 자연스럽게 이어진다.
- [x] `DisabilityType`, `RouteOption`, GH 내부 프로필 명칭 규칙이 구현 전 기준으로 고정된다.
- [x] GraphHopper import가 DB direct query 방식이 아니라 `road_segments` bulk load 기반이라는 점이 구현 전 기준으로 고정된다.
- [x] V2 범위가 분리되어 현재 계획이 과도하게 부풀지 않는다.

## Implementation Plan

- [x] PRD의 MySQL 기재 대신 ERD와 WKT/GEOMETRY 요구를 근거로 `PostgreSQL + PostGIS`를 표준으로 고정한다.
- [x] `poc/`를 Spring Boot 백엔드 시작점으로 두고, 필요 시 패키지와 모듈 구조를 서비스명 기준으로 재정리한다.
- [x] `etl/`은 Python ETL 전용 디렉토리로 유지하고, DB 연결과 공통 설정 유틸을 둔다.
- [x] GraphHopper 관련 코드는 별도 디렉토리 또는 모듈로 분리한다.
- [x] 구현 시작 전에 열거형 기준을 고정한다.
  - 외부 API/DB: `DisabilityType = VISUAL | MOBILITY`
  - 외부 API/DB: `RouteOption = SAFE | SHORTEST | PUBLIC_TRANSPORT`
  - GraphHopper 내부 프로필: `visual_safe`, `visual_fast`, `wheelchair_safe`, `wheelchair_fast`
  - 외부 `MOBILITY`는 내부에서 `wheelchair_*` 프로필로 매핑한다.
- [x] GraphHopper import의 데이터 흐름을 구현 전 기준으로 고정한다.
  - source of truth: `road_segments`
  - import 직전: `road_segments` bulk load
  - bulk load 결과를 OSM way 분해 기준으로 메모리 lookup map으로 2차 가공
  - import loop에서는 그 map으로 EV를 채움
  - per-edge DB query는 허용하지 않음
- [x] 운영 자동화, 계정 동기화, LLM UI, 완전한 Android 앱은 V2 또는 후속 단계로 격리한다.

### 인프라 사전 작업 (구현 착수 전 완료 필수)

- [x] `docker-compose.yml`을 루트에 생성한다.
  - `postgres:15-alpine` + PostGIS 2.5 이상 이미지 (예: `postgis/postgis:15-3.4`)
  - GraphHopper 독립 컨테이너: stage-01에서는 공식 GraphHopper 8.0 web jar를 다운로드하는 전용 Dockerfile 사용
  - `.env`의 `POSTGRES_*`, `BACKEND_PORT`, `GRAPHHOPPER_PORT` 값을 그대로 참조
  - `etl/data/raw/`와 GH config 디렉토리를 volume으로 마운트
- [x] GraphHopper 배포 방식을 고정한다.
  - **결정: GH를 독립 프로세스(Docker 컨테이너)로 운영하고 Spring Boot는 HTTP로 호출한다.**
  - GH custom encoded value·custom model은 GH config YAML과 Java SPI 플러그인으로 주입한다.
  - stage-01은 GraphHopper runtime scaffold와 `graphhopper-plugin/` 모듈 경계만 만든다. 실제 custom EV 주입은 workstream `04`가 소유한다.
  - 플러그인 JAR은 별도 Gradle 모듈 (`graphhopper-plugin/`) 또는 `etl/` 하위 Python이 아닌 Java 프로젝트로 분리한다.
  - GH 버전은 **8.x** 계열로 고정한다 (custom model JSON 지원이 안정화된 최신 계열).

### Python ETL 런타임 기반

- [x] `etl/requirements.txt`를 생성한다.
  - 필수: `psycopg2-binary`, `shapely`, `pyosmium`, `pandas`, `python-dotenv`, `tqdm`
  - 좌표 변환: `pyproj` (EPSG:5179 → 4326 변환에 필요, `slope_analysis_staging.csv` 처리 시)
- [x] `etl/db.py` 또는 `etl/common/db.py`에 `.env` 기반 DB 연결 유틸을 둔다.
- [x] ETL 스크립트 디렉토리 구조를 고정한다.
  - `etl/scripts/01_osm_load.py`
  - `etl/scripts/02_places_load.py`
  - `etl/scripts/03_accessibility_features_load.py`
  - `etl/scripts/04_segment_features_load.py`
  - `etl/scripts/05_subway_elevators_load.py`
  - `etl/scripts/06_bims_bus_load.py`
  - `etl/sql/schema.sql` — DDL 파일

### Spring Boot `poc/build.gradle` 추가 의존성

- [x] 다음 의존성을 `build.gradle`에 추가한다.
  - `org.hibernate.orm:hibernate-spatial` — PostGIS GEOMETRY 컬럼 JPA 매핑
  - `org.locationtech.jts:jts-core` — Geometry 타입
  - Spring의 `RestClient` 또는 `WebClient`는 GH HTTP 호출에 기본 사용 (별도 의존성 불필요)

### 원시 데이터 파일 사용 기준 고정

- [x] `etl/data/raw/place_merged_final.csv`와 `place_merged_broad_category_final.csv`는 헤더가 동일하다.
  - ETL에서 사용할 파일은 `place_merged_broad_category_final.csv`로 단일화한다.
  - `place_merged_final.csv`는 카테고리 분류 전 원본일 가능성이 있으므로, 두 파일의 행 수를 비교한 뒤 데이터가 동일하면 `place_merged_broad_category_final.csv`만 사용한다.
  - 검증 결과 두 파일 모두 `13564`행으로 동일했다.

## Validation Plan

- [x] 최신 ERD의 geometry, JSONB, enum/varchar 정책이 PostGIS 기준과 맞는지 확인한다.
- [x] `poc/` 기반으로 진행할 때 문서와 코드 경로가 지나치게 어긋나지 않는지 확인한다.
- [x] 구조 변경 후 `scripts/verify.sh`를 실행한다.
- [x] `docker-compose up -d`로 PostGIS와 GH 컨테이너가 기동되는지 확인한다.
  - 로컬 표준 포트 `5432`, `8080`은 다른 스택이 이미 사용 중이라 검증은 `POSTGRES_PORT=25432`, `BACKEND_PORT=28080`, `GRAPHHOPPER_PORT=28989`로 수행했다.
  - 결과: PostGIS healthy, GraphHopper `/health` 200, backend `/actuator/health` = `{"status":"UP"}`
- [x] `place_merged_final.csv`와 `place_merged_broad_category_final.csv`의 행 수를 비교해 중복 여부를 확인한다.

## Risks and Open Questions

- PRD의 기술 스택 표와 실제 저장소 기반 기술이 다르다.
- `poc/`를 유지하면 빠르지만 서비스명과 패키지명이 나중에 정리 대상이 된다.
- 외부 용어는 `MOBILITY`로 통일하지만 GH 내부 용어는 `wheelchair_*`를 유지하므로 명명 혼동을 초기에 차단해야 한다.
- 표준 호스트 포트 `5432`, `8080`은 로컬에 이미 사용 중일 수 있으므로, 검증이나 병행 실행 시 일시적 포트 override가 필요할 수 있다.

## Dependencies

- `.env`에 정의된 Postgres, ODsay, BIMS 관련 키
- 최신 `docs/erd.md`

## Handoff

- Build skill: `start`
- Validation skill: `check`
- Ship readiness note: 이후 모든 ETL과 API 계획이 이 실행 기반을 전제로 읽혀야 한다
