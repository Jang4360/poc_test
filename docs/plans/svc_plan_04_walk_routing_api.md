# svc_plan_04: 도보 라우팅 API (SAFE + SHORTEST)

> **작성일:** 2026-04-18 (POC 분석 반영 업데이트)  
> **목적:** GH 4개 프로필 기반 도보 라우팅 API 구현  
> **선행 조건:** svc_plan_03 완료 (GH 운영 중)  
> **후행 단계:** svc_plan_06 (ACCESSIBLE_TRANSIT)

---

## 1. POC 대비 변경 사항

| 항목 | POC | 신규 |
|---|---|---|
| DisabilityType | `VISUAL`, `WHEELCHAIR` | `VISUAL`, `MOBILITY` |
| RouteOption | `SAFE`, `SHORTEST` | `SAFE`, `SHORTEST`, `PUBLIC_TRANSPORT` |
| GH 연동 | GH embedded (같은 JVM) | GH HTTP API (별도 컨테이너) |
| fallback | synthetic 좌표 생성 (0.03 offset) | fallback 없음, `available: false` 반환 |
| 에러 처리 | `log.warn` 후 진행 | GlobalExceptionHandler + 명시적 에러 응답 |
| 인증 | 없음 | JWT Bearer (사용자 API) |

**POC의 synthetic fallback 제거 이유:**
```java
// POC TransitWalkLegRouter.java — 이 로직 사용 안 함
double offsetLat = (to.lng() - from.lng()) * 0.03d;  // 임의 ~3km offset
// 실제 도로 위에 없는 좌표를 지도에 표시 → 사용자 혼란
```

---

## 2. 프로젝트 구조 (Spring Boot)

```
backend/src/main/java/com/ieumgil/
├── common/
│   ├── ApiResponse.java
│   ├── GlobalExceptionHandler.java
│   └── SecurityConfig.java
├── routing/
│   ├── controller/
│   │   └── RouteSearchController.java
│   ├── service/
│   │   ├── RouteSearchService.java       # 세 옵션 병렬 처리
│   │   └── WalkRoutingService.java       # GH HTTP 호출
│   ├── client/
│   │   └── GraphHopperClient.java        # GH HTTP 클라이언트
│   ├── dto/
│   │   ├── RouteSearchRequest.java
│   │   ├── RouteSearchResponse.java
│   │   ├── RouteOptionResult.java
│   │   └── SegmentDto.java
│   └── domain/
│       ├── DisabilityType.java
│       └── RouteOption.java
└── IeumgilApplication.java
```

---

## 3. 도메인 열거형

```java
public enum DisabilityType { VISUAL, MOBILITY }
// WHEELCHAIR 사용하지 않음 — GH 프로필 내부만 wheelchair_*

public enum RouteOption { SAFE, SHORTEST, PUBLIC_TRANSPORT }
```

---

## 4. 프로필 매핑

```java
@Component
public class RoutingProfileResolver {

    private static final Map<DisabilityType, Map<RouteOption, String>> PROFILE_MAP = Map.of(
        DisabilityType.VISUAL, Map.of(
            RouteOption.SAFE, "visual_safe",
            RouteOption.SHORTEST, "visual_fast"
        ),
        DisabilityType.MOBILITY, Map.of(
            RouteOption.SAFE, "wheelchair_safe",
            RouteOption.SHORTEST, "wheelchair_fast"
        )
    );

    public String resolve(DisabilityType type, RouteOption option) {
        String profile = PROFILE_MAP.getOrDefault(type, Map.of()).get(option);
        if (profile == null) {
            throw new IllegalArgumentException(
                "프로필 매핑 없음: type=%s, option=%s".formatted(type, option));
        }
        return profile;
    }
}
```

---

## 5. GH HTTP 클라이언트

```java
@Component
public class GraphHopperClient {

    private final RestTemplate restTemplate;

    @Value("${graphhopper.base-url}")
    private String ghBaseUrl;

    /**
     * @param details GH에서 반환할 edge 속성 목록
     */
    public GhRouteResponse route(GeoPoint from, GeoPoint to, String profile, List<String> details) {
        String url = ghBaseUrl + "/route";
        MultiValueMap<String, String> params = new LinkedMultiValueMap<>();
        params.add("point", from.lat() + "," + from.lng());
        params.add("point", to.lat() + "," + to.lng());
        params.add("profile", profile);
        params.add("points_encoded", "false");
        params.add("instructions", "true");
        details.forEach(d -> params.add("details", d));

        try {
            return restTemplate.getForObject(url + "?" + toQueryString(params),
                GhRouteResponse.class);
        } catch (HttpClientErrorException.BadRequest e) {
            // GH가 경로를 찾지 못한 경우 (snap 실패, 연결 없음)
            throw new RouteNotFoundException(e.getMessage());
        }
    }

    private static final List<String> WALK_DETAILS = List.of(
        "braille_block_state", "audio_signal_state", "curb_ramp_state",
        "width_state", "surface_state", "stairs_state", "elevator_state",
        "crossing_state", "avg_slope_percent"
    );
}
```

---

## 6. WalkRoutingService

```java
@Service
public class WalkRoutingService {

    private final GraphHopperClient ghClient;
    private final RoutingProfileResolver profileResolver;

    public RouteOptionResult route(DisabilityType type, RouteOption option,
                                   GeoPoint start, GeoPoint end) {
        String profile = profileResolver.resolve(type, option);

        try {
            GhRouteResponse ghResp = ghClient.route(start, end, profile,
                GraphHopperClient.WALK_DETAILS);

            if (ghResp == null || ghResp.paths().isEmpty()) {
                return RouteOptionResult.unavailable(option, "NO_ACCESSIBLE_ROUTE");
            }

            GhPath best = ghResp.paths().get(0);
            List<SegmentDto> segments = buildSegments(best);
            SummaryDto summary = buildSummary(best, segments, type);

            return RouteOptionResult.available(option, profile, summary, segments);

        } catch (RouteNotFoundException e) {
            // 출발지/목적지 snap 실패 여부 판별
            String reason = e.getMessage().contains("Cannot find point")
                ? "ORIGIN_NOT_SNAPPABLE"
                : "NO_ACCESSIBLE_ROUTE";
            return RouteOptionResult.unavailable(option, reason);
        }
    }

    private List<SegmentDto> buildSegments(GhPath path) {
        // GH instructions와 details를 결합해 SegmentDto 생성
        Map<String, List<GhDetail>> detailMap = path.details();
        List<GhInstruction> instructions = path.instructions();

        return IntStream.range(0, instructions.size())
            .mapToObj(i -> {
                GhInstruction instr = instructions.get(i);
                int fromIdx = instr.interval().get(0);
                int toIdx   = instr.interval().get(1);

                return SegmentDto.builder()
                    .sequence(i + 1)
                    .geometry(extractGeometry(path.points(), fromIdx, toIdx))
                    .distanceMeter(instr.distance())
                    .stairsState(extractDetail(detailMap, "stairs_state", fromIdx))
                    .brailleBlockState(extractDetail(detailMap, "braille_block_state", fromIdx))
                    .audioSignalState(extractDetail(detailMap, "audio_signal_state", fromIdx))
                    .curbRampState(extractDetail(detailMap, "curb_ramp_state", fromIdx))
                    .crossingState(extractDetail(detailMap, "crossing_state", fromIdx))
                    .surfaceState(extractDetail(detailMap, "surface_state", fromIdx))
                    .widthState(extractDetail(detailMap, "width_state", fromIdx))
                    .avgSlopePercent(extractDecimalDetail(detailMap, "avg_slope_percent", fromIdx))
                    .guidanceMessage(buildGuidance(instr))
                    .build();
            })
            .toList();
    }

    private String extractDetail(Map<String, List<GhDetail>> detailMap,
                                  String key, int edgeIdx) {
        List<GhDetail> details = detailMap.get(key);
        if (details == null) return "UNKNOWN";
        return details.stream()
            .filter(d -> d.from() <= edgeIdx && edgeIdx < d.to())
            .map(GhDetail::value)
            .map(Object::toString)
            .findFirst()
            .orElse("UNKNOWN");
    }
}
```

---

## 7. RouteSearchService (병렬 처리)

```java
@Service
public class RouteSearchService {

    private final WalkRoutingService walkRoutingService;
    private final AccessibleTransitService transitService;

    // 라우팅 전용 스레드풀 (GH HTTP 호출 I/O 블로킹 고려)
    private final ExecutorService executor = Executors.newFixedThreadPool(8);

    public RouteSearchResponse search(RouteSearchRequest req) {
        List<RouteOption> options = req.routeOption() != null
            ? List.of(req.routeOption())
            : List.of(RouteOption.SAFE, RouteOption.SHORTEST, RouteOption.PUBLIC_TRANSPORT);

        List<CompletableFuture<RouteOptionResult>> futures = options.stream()
            .map(opt -> CompletableFuture
                .supplyAsync(() -> executeOption(req, opt), executor)
                .orTimeout(15, TimeUnit.SECONDS)   // 전체 타임아웃 15초
                .exceptionally(ex -> {
                    log.error("라우팅 실패: option={}, error={}", opt, ex.getMessage());
                    return RouteOptionResult.unavailable(opt, "TIMEOUT");
                }))
            .toList();

        List<RouteOptionResult> results = futures.stream()
            .map(CompletableFuture::join)
            .toList();

        return RouteSearchResponse.of(req.disabilityType(), req.startPoint(),
            req.endPoint(), results);
    }

    private RouteOptionResult executeOption(RouteSearchRequest req, RouteOption option) {
        return switch (option) {
            case SAFE  -> walkRoutingService.route(req.disabilityType(), SAFE,
                                   req.startPoint(), req.endPoint());
            case SHORTEST  -> walkRoutingService.route(req.disabilityType(), SHORTEST,
                                   req.startPoint(), req.endPoint());
            case PUBLIC_TRANSPORT -> transitService.orchestrate(req);  // svc_plan_06
        };
    }
}
```

---

## 8. GlobalExceptionHandler (보안 + 에러처리)

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
            .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
            .collect(Collectors.joining(", "));
        return ResponseEntity.badRequest()
            .body(ApiResponse.error("VALIDATION_ERROR", message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleGeneral(Exception e) {
        // 내부 상세 오류를 클라이언트에 노출하지 않음 (보안)
        log.error("Unhandled exception", e);
        return ResponseEntity.internalServerError()
            .body(ApiResponse.error("INTERNAL_ERROR", "서버 오류가 발생했습니다."));
    }
}
```

---

## 9. 보안 설정

> **전체 application.yml, build.gradle, Dockerfile:** svc_plan_00 참조. 이 섹션은 보안 관련 부분만 기술.

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .csrf(csrf -> csrf.disable())  // REST API — CSRF 불필요
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health").permitAll()  // 헬스체크만 오픈
                .requestMatchers("/actuator/**").hasRole("ADMIN") // actuator 보호
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

```yaml
# application.yml (svc_plan_00에 전체 포함됨)
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: ${JWT_ISSUER_URI}  # 환경변수 필수 — 기본값 없음

graphhopper:
  base-url: ${GH_BASE_URL:http://graphhopper:8989}  # 기본값은 docker 내부
```

### 로컬 개발용 JWT bypass

로컬 개발 시 JWT 발급 서버 없이 API를 테스트하려면 `application-local.yml`을 사용:

```yaml
# backend/src/main/resources/application-local.yml
# spring.profiles.active=local 로 기동 시 적용
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: ""  # JWT 검증 비활성화

# local profile에서는 모든 요청 허용 (SecurityConfig에서 profile 체크)
```

```java
// SecurityConfig.java — local profile 대응
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Value("${spring.profiles.active:}")
    private String activeProfile;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        if ("local".equals(activeProfile)) {
            return http
                .csrf(csrf -> csrf.disable())
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .build();
        }
        // 운영 설정
        return http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(s -> s.sessionCreationPolicy(STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/actuator/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .build();
    }
}
```

```bash
# 로컬 실행 시
./gradlew bootRun --args='--spring.profiles.active=local'
```

**API 키 관리 원칙:**
- 환경변수 주입 — 코드에 하드코딩 절대 금지
- 기본값은 빈 문자열 또는 명시적 실패 (POC처럼 fallback 허용 안 함)

---

## 10. Request / Response DTO

```java
public record RouteSearchRequest(
    @NotNull DisabilityType disabilityType,
    @NotNull @Valid GeoPointDto startPoint,
    @NotNull @Valid GeoPointDto endPoint,
    RouteOption routeOption  // null 허용 (전체 반환)
) {}

public record GeoPointDto(
    @NotNull @DecimalMin("-90") @DecimalMax("90")  Double lat,
    @NotNull @DecimalMin("-180") @DecimalMax("180") Double lng
) {}

public record SegmentDto(
    int sequence,
    String geometry,              // WKT LINESTRING
    double distanceMeter,
    String stairsState,           // YES / NO / UNKNOWN
    String brailleBlockState,
    String audioSignalState,
    String curbRampState,
    String crossingState,
    String surfaceState,
    String widthState,
    Double avgSlopePercent,       // null 가능 (미측정)
    String guidanceMessage
) {}
```

---

## 11. 완료 기준

- [ ] `POST /routes/search`: SAFE + SHORTEST 병렬 응답
- [ ] MOBILITY → `wheelchair_*` 프로필, VISUAL → `visual_*` 프로필 정확히 매핑
- [ ] segments에 9개 EV 상태값 포함 (UNKNOWN 포함 허용)
- [ ] GH snap/route 실패 → `available: false` + reason (synthetic 좌표 생성 없음)
- [ ] GlobalExceptionHandler 동작 확인 (400, 500 응답 형식 일관)
- [ ] `/actuator/health` 외 actuator 보호 확인
- [ ] `PUBLIC_TRANSPORT` → stub(`available: false, reason: NOT_IMPLEMENTED`)
- [ ] 단위/통합 테스트 통과
