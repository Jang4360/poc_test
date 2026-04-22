# svc_plan_07: 통합 API + 성능 최적화 + 운영 준비

> **작성일:** 2026-04-18 (POC 분석 반영 업데이트)  
> **목적:** 세 옵션 병렬 API 완성, 캐싱, GH 무중단 교체, 운영 환경 구성  
> **선행 조건:** svc_plan_04 + svc_plan_06 완료  
> **후행 단계:** 운영 배포

---

## 1. POC 대비 개선 사항

| 항목 | POC 문제 | 신규 해결 |
|---|---|---|
| 인증 | 전 엔드포인트 오픈 | JWT + Spring Security |
| 내부 health 노출 | `/internal/health` 에 시스템 정보 노출 | actuator 보호, 외부용 health 분리 |
| API 키 관리 | 환경변수 + 빈 기본값 허용 | 기본값 없음, 미설정 시 기동 실패 |
| 순차 처리 | `stream().map()` 동기 순차 | `CompletableFuture` 병렬 |
| Synthetic fallback | walk leg 실패 시 임의 좌표 생성 | fallback 없음 → 후보 탈락 |
| 모니터링 | log.warn만 | Actuator metrics + 구조화 로그 |
| GH 교체 | 재기동 필요 | blue-green artifact 교체 |

---

## 2. 운영 환경 Docker Compose

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
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
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
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  graphhopper:
    build: ./graphhopper
    volumes:
      - /data/graph-current:/data/graph-cache:ro
      - /data/busan.osm.pbf:/data/busan.osm.pbf:ro
      - ./graphhopper/config.yaml:/config/config.yaml:ro
      - ./graphhopper/custom_models:/config/custom_models:ro
    ports:
      - "8989:8989"   # 내부망만 노출 (프록시 뒤에 위치)
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8989/health"]
      interval: 30s
      timeout: 10s
      retries: 5
    depends_on:
      postgresql:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 5g   # GH LM 4개 프로필 + 부산 네트워크

  backend:
    build: ./backend
    ports:
      - "8080:8080"
    environment:
      # DB
      SPRING_DATASOURCE_URL:      jdbc:postgresql://postgresql:5432/${POSTGRES_DB}
      SPRING_DATASOURCE_USERNAME: ${POSTGRES_USER}
      SPRING_DATASOURCE_PASSWORD: ${POSTGRES_PASSWORD}
      # Redis
      SPRING_DATA_REDIS_HOST:     redis
      SPRING_DATA_REDIS_PORT:     6379
      SPRING_DATA_REDIS_PASSWORD: ${REDIS_PASSWORD}
      # GH
      GH_BASE_URL:                http://graphhopper:8989
      # 외부 API (기본값 없음 — 미설정 시 기동 실패)
      ODSAY_API_KEY:              ${ODSAY_API_KEY}
      BIMS_SERVICE_KEY:           ${BIMS_SERVICE_KEY}
      # JWT
      JWT_ISSUER_URI:             ${JWT_ISSUER_URI}
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
    restart: unless-stopped

  frontend:
    build: ./frontend
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

## 3. 환경변수 관리 원칙

```bash
# .env (git에 절대 커밋하지 않음 — .gitignore 필수)
POSTGRES_DB=ieumgil
POSTGRES_USER=ieumgil
POSTGRES_PASSWORD=<strong-password>

REDIS_PASSWORD=<strong-password>

ODSAY_API_KEY=<odsay-key>
BIMS_SERVICE_KEY=<bims-key>

JWT_ISSUER_URI=https://your-auth-server/

# .gitignore
.env
*.env
```

```java
// application.yml — 기본값 없음, 미설정 시 기동 실패
transit:
  odsay:
    api-key: ${ODSAY_API_KEY}        # 기본값 없음 (의도적)
    base-url: ${ODSAY_BASE_URL:https://api.odsay.com/v1/api}
  bims:
    service-key: ${BIMS_SERVICE_KEY}
    base-url: ${BIMS_BASE_URL:https://apis.data.go.kr/6260000/BusanBIMS}
```

---

## 4. 보안 설정 (Spring Security)

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(auth -> auth
                // 헬스체크 오픈
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/actuator/health/liveness").permitAll()
                .requestMatchers("/actuator/health/readiness").permitAll()
                // actuator 나머지는 내부망 전용 (IP 제한 또는 ADMIN 역할)
                .requestMatchers("/actuator/**").hasIpAddress("10.0.0.0/8")
                // GH 내부 health (외부 노출 X — 백엔드에서만 사용)
                .requestMatchers("/internal/**").denyAll()
                // 서비스 API
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

---

## 5. 응답 성능 목표 및 Timeout 설정

| 옵션 | P95 목표 | 타임아웃 |
|---|---|---|
| SAFE / SHORTEST | ≤ 3초 | 5초 |
| PUBLIC_TRANSPORT (캐시 Miss) | ≤ 10초 | 15초 |
| PUBLIC_TRANSPORT (캐시 Hit) | ≤ 200ms | — |

```java
// RouteSearchService — 각 옵션 타임아웃 분리
private RouteOptionResult executeWithTimeout(
    RouteSearchRequest req, RouteOption option
) {
    Duration timeout = option == PUBLIC_TRANSPORT
        ? Duration.ofSeconds(15)
        : Duration.ofSeconds(5);

    CompletableFuture<RouteOptionResult> future = CompletableFuture
        .supplyAsync(() -> executeOption(req, option), executor);

    try {
        return future.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
    } catch (TimeoutException e) {
        future.cancel(true);
        log.warn("라우팅 타임아웃: option={}", option);
        return RouteOptionResult.unavailable(option, "TIMEOUT");
    } catch (Exception e) {
        return RouteOptionResult.unavailable(option, "INTERNAL_ERROR");
    }
}
```

---

## 6. 구조화 로그 (성능 측정)

```java
@PostMapping("/routes/search")
public ResponseEntity<ApiResponse<RouteSearchResponse>> search(
    @RequestBody @Valid RouteSearchRequest req
) {
    long start = System.currentTimeMillis();
    RouteSearchResponse result = routeSearchService.search(req);
    long elapsed = System.currentTimeMillis() - start;

    // JSON 구조화 로그 (ELK, Datadog 등 수집 용이)
    log.info("""
        {"event":"route_search","disability":"{}","options":"{}","elapsed_ms":{},"results":{}}
        """,
        req.disabilityType(),
        req.routeOption(),
        elapsed,
        result.options().stream()
            .map(o -> o.option() + ":" + (o.available() ? "OK" : o.reason()))
            .toList()
    );

    if (elapsed > 10_000) {
        log.warn("route_search_slow: elapsed={}ms, disability={}", elapsed, req.disabilityType());
    }

    return ResponseEntity.ok(ApiResponse.success(result));
}
```

---

## 7. Spring Actuator 설정

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health, metrics, prometheus, info
  endpoint:
    health:
      show-details: when-authorized   # 인증된 요청만 상세 정보 노출
      probes:
        enabled: true                  # liveness / readiness 분리
  metrics:
    tags:
      application: ieumgil-backend
      env: ${SPRING_PROFILES_ACTIVE:local}
```

---

## 8. GH Blue-Green Artifact 교체

### 디렉토리 구조

```
/data/
├── graph-blue/          # 현재 운영 artifact
├── graph-green/         # import 대상 artifact
└── graph-current -> /data/graph-blue   (심볼릭 링크)
```

### 교체 스크립트

```bash
#!/bin/bash
# scripts/swap_graph.sh
set -e

BLUE=/data/graph-blue
GREEN=/data/graph-green
CURRENT=/data/graph-current
PBF=/data/busan.osm.pbf
GH_JAR=/graphhopper/graphhopper.jar
CONFIG=/config/config.yaml

ACTIVE=$(readlink -f "$CURRENT")
if [ "$ACTIVE" = "$BLUE" ]; then
    TARGET=$GREEN; TARGET_NAME="green"
else
    TARGET=$BLUE;  TARGET_NAME="blue"
fi

echo "[1/3] GH import → $TARGET_NAME"
java -Xmx4g -jar "$GH_JAR" import \
    --graph.location="$TARGET" \
    --datareader.file="$PBF" \
    --config="$CONFIG"

echo "[2/3] 심볼릭 링크 교체 → $TARGET_NAME"
ln -sfn "$TARGET" "$CURRENT"

echo "[3/3] GH 컨테이너 재기동"
docker compose restart graphhopper

echo "완료: 현재 artifact = $TARGET_NAME"
```

**주의:** GH 재기동 중(헬스체크 복구까지 ~30초) 도보 라우팅은 `available: false` 반환.
백엔드에서 GH health 확인 후 fallback 처리:

```java
public RouteOptionResult route(...) {
    if (!ghHealthChecker.isReady()) {
        return RouteOptionResult.unavailable(option, "ROUTING_ENGINE_UNAVAILABLE");
    }
    // ... 기존 로직
}
```

---

## 9. build.gradle / Dockerfile

> **전체 build.gradle, backend/Dockerfile, graphhopper/Dockerfile:** svc_plan_00 참조.
> 이 계획서에서 중복 기술하지 않음.

**GH embedded 사용하지 않음.** POC는 GH를 같은 JVM에 로드했으나,
신규 레포에서는 GH를 별도 컨테이너로 분리 → 백엔드는 HTTP 클라이언트만 포함.
이유: 메모리 격리, GH 재기동 시 백엔드 무중단, 독립 스케일링.

---

## 10. 전체 시스템 기동 순서 (배포 체크리스트)

```
[1단계] DB + 인프라 기동
  docker compose up postgresql redis -d
  → postgresql healthcheck 통과 대기

[2단계] 데이터 파이프라인 (병렬 가능)
  python etl/build_network.py --pbf ...          # svc_plan_01
  python etl/etl_slope.py --dem ...               # svc_plan_02
  python etl/etl_accessibility.py --type ...      # svc_plan_02
  python etl/load_low_floor_routes.py --csv ...   # svc_plan_05
  python etl/load_subway_elevators.py --geojson . # svc_plan_05

[3단계] GH import (svc_plan_02 완료 후)
  docker compose build graphhopper    # gh-plugin.jar 빌드 포함
  docker compose up graphhopper -d    # import + LM preparation (~10분)
  → GH healthcheck 통과 대기 (GET http://localhost:8989/health)

[4단계] 백엔드 기동 (GH healthcheck 통과 후)
  docker compose up backend -d
  → /actuator/health 200 확인

[5단계] 프론트엔드
  docker compose up frontend -d

[최종 확인]
  # 전체 healthcheck
  docker compose ps
  curl http://localhost:8080/actuator/health

  # 도보 라우팅 스모크 테스트
  curl -X POST http://localhost:8080/routes/search \
    -H "Content-Type: application/json" \
    -d '{"disabilityType":"MOBILITY","startPoint":{"lat":35.1795,"lng":129.0756},"endPoint":{"lat":35.1581,"lng":129.0563}}'
```

**주의:** 단계 순서 위반 시 발생하는 오류:
- GH 기동 전 백엔드 기동 → `GH_BASE_URL` 연결 실패로 healthcheck 실패
- ETL 전 GH import → 모든 속성 UNKNOWN → 4개 프로필 경로 동일
- svc_plan_01 전 svc_plan_02 실행 → road_segments 테이블 없음 오류

---

## 11. 완료 기준

- [ ] 세 옵션 병렬 반환 (SAFE + SHORTEST + PUBLIC_TRANSPORT stub 제거)
- [ ] JWT 인증 적용 (모든 라우팅 API)
- [ ] `/actuator/health` 외 actuator 보호
- [ ] `.env` 파일 `.gitignore` 확인 (커밋 방지)
- [ ] 미설정 API 키로 기동 시 실패 확인 (기본값 없음)
- [ ] SAFE/SHORTEST P95 ≤ 3초 (부산 실제 좌표)
- [ ] PUBLIC_TRANSPORT (캐시 Miss) P95 ≤ 10초
- [ ] GH blue-green 교체 스크립트 동작 확인
- [ ] Docker Compose 전체 기동 확인 (postgresql + redis + graphhopper + backend + frontend)
- [ ] `/actuator/prometheus` 메트릭 노출 확인
- [ ] 배포 체크리스트 순서대로 기동 시 오류 없음 확인
