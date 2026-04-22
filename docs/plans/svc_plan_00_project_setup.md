# svc_plan_00: 신규 레포 초기 세팅

> **작성일:** 2026-04-18  
> **목적:** `.env` + `busan.osm.pbf`만 가지고 개발을 시작할 수 있는 완전한 레포 뼈대 구성  
> **선행 조건:** 없음 (모든 plan의 시작점)  
> **후행 단계:** svc_plan_01 (보행 네트워크 파이프라인)

---

## 1. 레포 전체 디렉토리 구조

```
ieumgil-svc/
├── .env                          # 실제 시크릿 (git 제외)
├── .env.example                  # 환경변수 템플릿 (git 포함)
├── .gitignore
├── docker-compose.yml            # 전체 서비스 오케스트레이션
│
├── postgresql/
│   └── init/
│       └── 01_schema.sql         # DB 전체 DDL (svc_plan_01에서 작성)
│
├── graphhopper/
│   ├── Dockerfile
│   ├── config.yaml               # GH 메인 설정
│   └── custom_models/
│       ├── visual_safe.json
│       ├── visual_fast.json
│       ├── wheelchair_safe.json
│       └── wheelchair_fast.json
│
├── backend/                      # Spring Boot 프로젝트
│   ├── build.gradle
│   ├── settings.gradle
│   ├── gradlew
│   ├── Dockerfile
│   └── src/
│       └── main/
│           ├── java/com/ieumgil/
│           └── resources/
│               └── application.yml
│
├── frontend/                     # React 프로젝트 (별도 진행)
│   ├── Dockerfile
│   └── nginx.conf
│
└── etl/                          # Python ETL 스크립트
    ├── requirements.txt
    ├── build_network.py          # svc_plan_01
    ├── etl_slope.py              # svc_plan_02
    ├── etl_accessibility.py      # svc_plan_02
    ├── load_transit_ref.py       # svc_plan_05
    ├── coverage_report.py        # svc_plan_02
    └── data/
        └── raw/
            └── busan.osm.pbf     # 여기에 복사
```

---

## 2. .env.example (전체 환경변수 목록)

```bash
# .env.example — 이 파일은 git에 포함. 실제 값은 .env에 작성.

# ─── PostgreSQL ────────────────────────────────
POSTGRES_DB=ieumgil
POSTGRES_USER=ieumgil
POSTGRES_PASSWORD=                 # 필수. 최소 16자 이상 권장

# ─── Redis ─────────────────────────────────────
REDIS_PASSWORD=                    # 필수. 최소 16자 이상 권장

# ─── GraphHopper ───────────────────────────────
GRAPHHOPPER_PORT=8989

# ─── 외부 API 키 (필수 — 없으면 백엔드 기동 실패) ─
ODSAY_API_KEY=                     # https://lab.odsay.com 에서 발급
BIMS_SERVICE_KEY=                  # 공공데이터포털 부산버스정보시스템 API

# ─── JWT (Spring Security OAuth2 Resource Server)
# 발급 서버가 없으면 개발 환경에서는 아래 로컬 설정 사용
JWT_ISSUER_URI=                    # 예: https://your-auth-server.com

# ─── Spring 프로파일 ────────────────────────────
SPRING_PROFILES_ACTIVE=local       # local | prod

# ─── 카카오 지도 (프론트엔드) ───────────────────
# 발급: https://developers.kakao.com → 내 애플리케이션 → JavaScript 키
# 플랫폼 도메인 등록 필수: http://localhost:3000 (개발), https://your-domain.com (운영)
KAKAO_JS_KEY=                      # 프론트엔드 Vite 빌드 타임에 번들에 포함됨
```

### 기존 `.env`가 이미 있는 경우 이름 정리 규칙

기존 POC용 `.env`를 재사용할 때는 **셸에서 임시 매핑하지 말고 실제 키 이름을 아래처럼 통일한다.**

| 기존 키 | 신규 레포 표준 키 |
| --- | --- |
| `KAKAO_JAVASCRIPT_KEY` | `KAKAO_JS_KEY` |
| `BUSAN_BIMS_SERVICE_KEY_ENCODING` / `BUSAN_BIMS_SERVICE_KEY_DECODING` | `BIMS_SERVICE_KEY` |
| Redis 비밀번호 별도 없음 | `REDIS_PASSWORD` 추가 |

`docker-compose.yml`, 백엔드 설정, 프론트엔드 build args는 위 표준 키만 참조한다.  
기존 키와 신규 키를 혼용하면 `docker compose config`는 통과해도 일부 서비스가 빈 값으로 기동될 수 있다.

```bash
# .gitignore
.env
*.env
!.env.example
runtime/
etl/data/raw/*.pbf
etl/data/public/
```

---

## 3. Docker Compose (전체 서비스 기본 구성)

```yaml
# docker-compose.yml

services:

  postgresql:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB:       ${POSTGRES_DB}
      POSTGRES_USER:     ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./postgresql/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: >
      redis-server
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  graphhopper:
    build:
      context: ./graphhopper
    volumes:
      - ./runtime/graph:/data/graph-cache
      - ./etl/data/raw/busan.osm.pbf:/data/busan.osm.pbf:ro
      - ./graphhopper/config.yaml:/config/config.yaml:ro
      - ./graphhopper/custom_models:/config/custom_models:ro
    ports:
      - "${GRAPHHOPPER_PORT}:8989"
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8989/health"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s    # LM 준비 시간 확보
    depends_on:
      postgresql:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 5g
    restart: unless-stopped

  backend:
    build:
      context: ./backend
    environment:
      SPRING_PROFILES_ACTIVE:         ${SPRING_PROFILES_ACTIVE:-local}
      SPRING_DATASOURCE_URL:          jdbc:postgresql://postgresql:5432/${POSTGRES_DB}
      SPRING_DATASOURCE_USERNAME:     ${POSTGRES_USER}
      SPRING_DATASOURCE_PASSWORD:     ${POSTGRES_PASSWORD}
      SPRING_DATA_REDIS_HOST:         redis
      SPRING_DATA_REDIS_PORT:         6379
      SPRING_DATA_REDIS_PASSWORD:     ${REDIS_PASSWORD}
      GH_BASE_URL:                    http://graphhopper:8989
      TRANSIT_ODSAY_API_KEY:          ${ODSAY_API_KEY}
      TRANSIT_BIMS_SERVICE_KEY:       ${BIMS_SERVICE_KEY}
      SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_ISSUER_URI: ${JWT_ISSUER_URI:-}
    ports:
      - "8080:8080"
    depends_on:
      postgresql:
        condition: service_healthy
      redis:
        condition: service_healthy
      graphhopper:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/actuator/health"]
      interval: 30s
      retries: 5
      start_period: 60s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        # Vite 환경변수는 빌드 타임에 번들에 포함됨 → environment가 아닌 args로 전달
        VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8080}
        VITE_KAKAO_JS_KEY: ${KAKAO_JS_KEY}
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  pg_data:
  redis_data:
```

---

## 4. GraphHopper Dockerfile + 버전

```dockerfile
# graphhopper/Dockerfile
FROM eclipse-temurin:21-jre-alpine

WORKDIR /graphhopper

# GH 버전: 9.1 (Custom Model + LM 안정 버전)
# 다운로드: https://github.com/graphhopper/graphhopper/releases/tag/9.1
ARG GH_VERSION=9.1
RUN wget -q "https://github.com/graphhopper/graphhopper/releases/download/${GH_VERSION}/graphhopper-web-${GH_VERSION}.jar" \
    -O graphhopper.jar

EXPOSE 8989

ENTRYPOINT ["java", \
  "-Xmx4g", "-Xms1g", \
  "-Ddw.server.application_connectors[0].port=8989", \
  "-jar", "graphhopper.jar", \
  "server", "/config/config.yaml"]
```

**GH 버전 선택 이유:** v9.x부터 `encoded_values` 설정에서 커스텀 enum 값 목록(`values=YES,NO,UNKNOWN`)을 직접 지정 가능. `DecimalEncodedValue`의 `min_value/max_value` 파라미터 지원.

### GraphHopper 9.1 호환 규칙

`graphhopper/config.yaml`은 아래 형식을 기준으로 시작한다.

```yaml
graphhopper:
  datareader.file: /data/busan.osm.pbf
  graph.location: /data/graph-cache
  custom_models.directory: /config/custom_models
  graph.encoded_values: foot_access,foot_average_speed
  profiles:
    - name: visual_safe
      custom_model_files: [visual_safe.json]
    - name: visual_fast
      custom_model_files: [visual_fast.json]
    - name: wheelchair_safe
      custom_model_files: [wheelchair_safe.json]
    - name: wheelchair_fast
      custom_model_files: [wheelchair_fast.json]
  profiles_ch: []
  profiles_lm:
    - profile: visual_safe
    - profile: visual_fast
    - profile: wheelchair_safe
    - profile: wheelchair_fast
  prepare.lm.landmarks: 16
  import.osm.ignored_highways: motorway,trunk
  graph.dataaccess.default_type: RAM_STORE

server:
  application_connectors:
    - type: http
      port: 8989
  admin_connectors:
    - type: http
      port: 8988
  request_log:
    appenders: []
```

다음은 **처음부터 금지**한다.

- `profiles[].vehicle: foot`
- `profiles[].turn_costs: false`
- `profiles_lm[].preparations`
- `custom_model_files: [*.yaml]`

**이유:** GraphHopper 9.1에서는 위 문법이 모두 폐기되었고, 그대로 두면 서버가 import 시작 전 설정 파싱 단계에서 즉시 종료된다.

**주의:** GraphHopper 9.1의 `custom_model_files`는 YAML을 지원하지 않으므로 `custom_models/*.json`만 사용한다.

---

## 5. Spring Boot 프로젝트 초기 생성

```bash
# Spring Initializr CLI 또는 https://start.spring.io 에서 생성
# 설정:
#   Project: Gradle - Groovy
#   Language: Java
#   Spring Boot: 3.3.x
#   Java: 21
#   Dependencies:
#     Spring Web, Spring Security, OAuth2 Resource Server,
#     Spring Data JPA, Spring Data Redis, Spring Boot Actuator,
#     Validation, PostgreSQL Driver
```

### build.gradle (전체)

```groovy
// backend/build.gradle
plugins {
    id 'org.springframework.boot' version '3.3.4'
    id 'io.spring.dependency-management' version '1.1.6'
    id 'java'
}

group = 'com.ieumgil'
version = '0.0.1-SNAPSHOT'

java {
    sourceCompatibility = JavaVersion.VERSION_21
}

configurations {
    compileOnly { extendsFrom annotationProcessor }
}

repositories {
    mavenCentral()
}

dependencies {
    // Web
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-validation'

    // Security
    implementation 'org.springframework.boot:spring-boot-starter-security'
    implementation 'org.springframework.boot:spring-boot-starter-oauth2-resource-server'

    // Data
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-data-redis'
    runtimeOnly 'org.postgresql:postgresql'

    // Monitoring
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    implementation 'io.micrometer:micrometer-registry-prometheus'

    // Jackson
    implementation 'com.fasterxml.jackson.datatype:jackson-datatype-jsr310'

    // Lombok
    compileOnly 'org.projectlombok:lombok'
    annotationProcessor 'org.projectlombok:lombok'

    // Test
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.security:spring-security-test'
    testImplementation 'org.testcontainers:junit-jupiter'
    testImplementation 'org.testcontainers:postgresql'
    testImplementation 'com.redis.testcontainers:testcontainers-redis:1.6.4'
}

test {
    useJUnitPlatform()
}
```

### settings.gradle

```groovy
rootProject.name = 'ieumgil-backend'
```

---

## 6. Spring Boot application.yml (전체)

```yaml
# backend/src/main/resources/application.yml

spring:
  application:
    name: ieumgil-backend

  datasource:
    url:      ${SPRING_DATASOURCE_URL:jdbc:postgresql://localhost:5432/ieumgil}
    username: ${SPRING_DATASOURCE_USERNAME:ieumgil}
    password: ${SPRING_DATASOURCE_PASSWORD}
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: 10
      minimum-idle: 2
      connection-timeout: 30000

  jpa:
    database-platform: org.hibernate.dialect.PostgreSQLDialect
    hibernate:
      ddl-auto: validate          # DDL은 postgresql/init/01_schema.sql로 관리
    open-in-view: false
    properties:
      hibernate:
        jdbc:
          batch_size: 50

  data:
    redis:
      host:     ${SPRING_DATA_REDIS_HOST:localhost}
      port:     ${SPRING_DATA_REDIS_PORT:6379}
      password: ${SPRING_DATA_REDIS_PASSWORD}
      timeout:  2000ms
      lettuce:
        pool:
          max-active: 8
          min-idle: 2

  security:
    oauth2:
      resourceserver:
        jwt:
          # JWT_ISSUER_URI가 비어있으면 개발 환경에서는 보안 비활성화 고려
          issuer-uri: ${SPRING_SECURITY_OAUTH2_RESOURCESERVER_JWT_ISSUER_URI:}

  jackson:
    default-property-inclusion: non_null
    serialization:
      write-dates-as-timestamps: false
    time-zone: Asia/Seoul

# GraphHopper HTTP 클라이언트
graphhopper:
  base-url: ${GH_BASE_URL:http://localhost:8989}
  connect-timeout: 3000
  read-timeout: 10000

# 외부 API (기본값 없음 — 미설정 시 기동 실패)
transit:
  odsay:
    api-key:  ${TRANSIT_ODSAY_API_KEY}
    base-url: ${TRANSIT_ODSAY_BASE_URL:https://api.odsay.com/v1/api}
  bims:
    service-key: ${TRANSIT_BIMS_SERVICE_KEY}
    base-url:    ${TRANSIT_BIMS_BASE_URL:https://apis.data.go.kr/6260000/BusanBIMS}

# Actuator
management:
  endpoints:
    web:
      exposure:
        include: health, metrics, prometheus, info
  endpoint:
    health:
      show-details: when-authorized
      probes:
        enabled: true
  metrics:
    tags:
      application: ${spring.application.name}
      env: ${SPRING_PROFILES_ACTIVE:local}

# 로깅
logging:
  level:
    com.ieumgil: DEBUG
    org.springframework.security: INFO
  pattern:
    console: "%d{HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"

server:
  port: 8080
  shutdown: graceful
```

**로컬 개발용 오버라이드:**

```yaml
# backend/src/main/resources/application-local.yml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: ""   # 로컬에서는 JWT 검증 비활성화

# 로컬에서 JWT 없이 테스트하려면 SecurityConfig에서 local 프로파일 분기:
# @Profile("local") → permitAll()
```

---

## 7. Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM eclipse-temurin:21-jre-alpine AS runtime

WORKDIR /app

COPY build/libs/ieumgil-backend-*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", \
  "-Xmx1g", "-Xms256m", \
  "-Djava.security.egd=file:/dev/./urandom", \
  "-jar", "app.jar"]
```

```bash
# 빌드 명령 (Docker Compose build 전 실행)
cd backend
./gradlew bootJar
```

---

## 8. Python ETL 환경 설정

### requirements.txt

```txt
# etl/requirements.txt
osmium==3.7.0          # OSM PBF 파싱
shapely==2.0.5         # Geometry 처리
geopandas==0.14.4      # 공간 데이터 처리 (ETL 2단계)
rasterio==1.3.10       # DEM GeoTIFF 읽기 (경사도)
pyproj==3.6.1          # 좌표 변환 (WGS84 ↔ EPSG:5179)
psycopg2-binary==2.9.9 # PostgreSQL 연결
python-dotenv==1.0.1   # .env 파일 읽기
requests==2.32.3       # HTTP 클라이언트 (BIMS API 등)
tqdm==4.66.4           # 진행 표시
```

```bash
# Python 가상환경 설정
cd etl
python3.11 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### ETL 공통 DB 연결 유틸

```python
# etl/db.py
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'ieumgil'),
        user=os.getenv('POSTGRES_USER', 'ieumgil'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
    )
```

`.env`에 아래 추가:
```bash
# ETL용 (로컬에서 직접 실행 시)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

## 9. busan.osm.pbf 배치

```bash
# busan.osm.pbf를 etl/data/raw/ 에 복사
cp /path/to/busan.osm.pbf ieumgil-svc/etl/data/raw/busan.osm.pbf
```

파일 확인:
```bash
ls -lh etl/data/raw/busan.osm.pbf
# 예상: 약 200~400MB
```

---

## 10. 개발 시작 순서 (전체 flow)

```bash
# 1. 레포 클론 & 환경변수 설정
git clone https://github.com/yourorg/ieumgil-svc.git
cd ieumgil-svc
cp .env.example .env
# .env 파일 편집: POSTGRES_PASSWORD, REDIS_PASSWORD 등 입력

# 2. busan.osm.pbf 배치
cp /path/to/busan.osm.pbf etl/data/raw/

# 3. DB + Redis 기동
docker compose up postgresql redis -d

# 4. Python 환경 설정 (ETL용)
cd etl && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cd ..

# 5. svc_plan_01: 보행 네트워크 적재
python etl/build_network.py

# 6. svc_plan_02: 공공데이터 ETL (공공데이터 파일 준비 후)
python etl/etl_slope.py --dem etl/data/public/dem/busan_dem.tif
python etl/etl_accessibility.py --config etl/config/etl_config.yml

# 7. svc_plan_03: GH import + LM
docker compose up graphhopper -d
# GH import는 graphhopper 컨테이너가 처음 기동 시 자동 실행
# (import 완료까지 5~30분 소요)

# 8. svc_plan_04: 백엔드 빌드 & 기동
cd backend && ./gradlew bootJar && cd ..
docker compose up backend -d

# 9. svc_plan_05: 대중교통 참조 데이터
python etl/load_transit_ref.py

# 10. svc_plan_06~07: 오케스트레이션 코드 작성 후 재빌드
cd backend && ./gradlew bootJar && cd ..
docker compose up backend --build -d

# 11. 전체 기동 확인
docker compose ps
curl http://localhost:8080/actuator/health
curl http://localhost:8989/health
```

---

## 11. runtime/ 디렉토리 구조

```
runtime/
└── graph/         # GH graph artifact (git 제외)
    ├── graph-blue/
    ├── graph-green/
    └── graph-current -> graph-blue   (심볼릭 링크)
```

```bash
# 초기 생성
mkdir -p runtime/graph/graph-blue runtime/graph/graph-green
ln -sfn "$(pwd)/runtime/graph/graph-blue" runtime/graph/graph-current
```

---

## 12. 완료 기준

- [ ] 레포 디렉토리 구조 생성 완료
- [ ] `.env.example` 작성 및 `.env` 생성 완료
- [ ] `.gitignore` 설정 (`.env`, `runtime/`, `*.pbf` 제외)
- [ ] `docker compose up postgresql redis -d` 성공, health 통과
- [ ] `psql -h localhost -U ieumgil -d ieumgil` 접속 확인
- [ ] `01_schema.sql` 적용 완료 (모든 테이블 생성)
- [ ] Python venv 생성 및 `pip install -r requirements.txt` 완료
- [ ] `backend/gradlew bootJar` 빌드 성공 (빈 프로젝트 수준)
- [ ] GH 컨테이너 이미지 빌드 완료 (`docker compose build graphhopper`)
