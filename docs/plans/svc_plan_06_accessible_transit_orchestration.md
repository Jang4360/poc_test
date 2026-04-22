# svc_plan_06: ACCESSIBLE_TRANSIT 오케스트레이션

> **작성일:** 2026-04-18 (POC 버그 분석 반영 전면 재작성)  
> **목적:** ODsay 실 API 연동 + 정확한 정류장/역 좌표 기반 walk leg 재계산 + 저상버스/엘리베이터 필터  
> **선행 조건:** svc_plan_03 (GH), svc_plan_04 (도보 API), svc_plan_05 (참조 데이터)  
> **후행 단계:** svc_plan_07 (통합 + 성능)

---

## 1. POC 핵심 버그 분석

### 버그 1 — Walk leg 좌표가 실제 정류장이 아닌 선형 보간값

```java
// POC TransitMixedRouteFacade.java
private TransitWaypoint interpolate(TransitWaypoint start, TransitWaypoint end, double ratio) {
    double lat = start.lat() + ((end.lat() - start.lat()) * ratio);
    double lng = start.lng() + ((end.lng() - start.lng()) * ratio);
    return new TransitWaypoint(lat, lng);  // 출발지-목적지 직선상의 임의 점
}

// 사용 예
TransitWaypoint legStart = interpolate(start, end, 0.00);  // 출발지
TransitWaypoint legEnd   = interpolate(start, end, 0.12);  // 직선의 12% 지점 → 실제 정류장이 아님
```

**ODsay 실 API는 각 subPath에 실제 좌표를 제공한다:**
```json
{
  "trafficType": 2,
  "startX": 129.0789, "startY": 35.1812, "startName": "부산시청",
  "endX":   129.0563, "endY":   35.1581, "endName":   "서면역",
  "startArsID": "05001"
}
```
이 좌표를 무시하고 보간값을 사용했기 때문에 walk 경로가 실제 도로에서 벗어난다.

### 버그 2 — 버스/지하철 노선 정보를 ODsay 응답에서 파싱하지 않음

```java
// POC StubOdsayTransitClient — 하드코딩
new TransitLegSeed(BUS, 0.12, 0.42, "Bus 86", 9,
    "5200000086", "86", null, "Busan City Hall", "Seomyeon", ...)
// 실제 API 연동 없음
```

ODsay 실 API 응답의 `lane[].busNo`, `lane[].busRouteId`, `passStopList.stations` 등을 파싱해야 한다.

### 버그 3 — 순차 처리로 인한 성능 문제

```java
// POC — 후보 3개를 순차 처리
odsayTransitClient.searchSeeds(request, departureAt).stream()
    .map(seed -> assembleCandidate(seed, ...))  // 순차
```

각 후보마다 GH walk 재계산 + BIMS 호출 → 총 수 초 소요.

---

## 2. ODsay API 응답 구조 (실 API 기준)

```
GET https://api.odsay.com/v1/api/searchPubTransPathT
  ?apiKey={key}&SX={출발lng}&SY={출발lat}&EX={목적lng}&EY={목적lat}&SearchType=0
```

```json
{
  "result": {
    "path": [
      {
        "pathType": 3,
        "info": {
          "totalTime": 45,
          "totalDistance": 5200,
          "busTransitCount": 1,
          "subwayTransitCount": 1,
          "totalWalk": 800,
          "payment": 1500
        },
        "subPath": [
          {
            "trafficType": 3,
            "distance": 200,
            "sectionTime": 3,
            "startX": 129.0756, "startY": 35.1795,
            "endX":   129.0789, "endY":   35.1812
          },
          {
            "trafficType": 2,
            "distance": 3200,
            "sectionTime": 25,
            "startX":    129.0789, "startY":    35.1812,
            "startName": "부산시청",
            "startArsID":"05001",
            "endX":      129.0563, "endY":      35.1581,
            "endName":   "서면역",
            "endArsID":  "05020",
            "lane": [{"busNo": "86", "busRouteId": "5200000086", "type": 11}],
            "passStopList": {
              "stations": [
                {"index":0,"stationName":"부산시청","x":"129.0789","y":"35.1812","arsId":"05001","stationID":"5010101"},
                {"index":5,"stationName":"서면역",  "x":"129.0563","y":"35.1581","arsId":"05020","stationID":"5010120"}
              ]
            }
          },
          {
            "trafficType": 3,
            "distance": 300,
            "sectionTime": 5,
            "startX": 129.0563, "startY": 35.1581,
            "endX":   129.0523, "endY":   35.1545
          },
          {
            "trafficType": 1,
            "distance": 1500,
            "sectionTime": 12,
            "startX":    129.0523, "startY":    35.1545,
            "startName": "서면",
            "startID":   "1013",
            "endX":      129.0402, "endY":      35.1039,
            "endName":   "남포",
            "endID":     "1017",
            "lane": [{"name":"부산 1호선","subwayCode":21,"stationCode":"1013"}],
            "passStopList": {
              "stations": [
                {"index":0,"stationName":"서면","x":"129.0523","y":"35.1545","stationID":"1013"},
                {"index":4,"stationName":"남포","x":"129.0402","y":"35.1039","stationID":"1017"}
              ]
            }
          }
        ]
      }
    ]
  }
}
```

---

## 3. ODsay 응답 파싱 DTO

```java
// ODsay subPath → 내부 도메인 객체로 파싱
public record OdsaySubPath(
    int trafficType,       // 1=지하철, 2=버스, 3=도보
    int distance,
    int sectionTime,

    // 도보/버스/지하철 공통 — 실제 시작/끝 좌표 (핵심)
    double startX, double startY,   // 정류장/역/출발지 실제 경도, 위도
    double endX,   double endY,     // 정류장/역/목적지 실제 경도, 위도

    // 버스/지하철 전용
    String startName,       // "부산시청" (정류장명 or 역명)
    String endName,         // "서면역"
    String startArsID,      // 버스 정류장 ID (BIMS 조회용)
    String endArsID,
    String startID,         // 지하철역 ID
    String endID,

    List<OdsayLane> lane,
    OdsayPassStopList passStopList
) {}

public record OdsayLane(
    String busNo,           // "86"
    String busRouteId,      // "5200000086"
    Integer type,           // 버스 타입
    String name,            // "부산 1호선" (지하철)
    Integer subwayCode,
    String stationCode
) {}

public record OdsayStation(
    int index,
    String stationName,
    String x,              // 경도 (문자열)
    String y,              // 위도 (문자열)
    String arsId,          // 버스 정류장 ID
    String stationID       // 지하철역 ID
) {}
```

---

## 4. 핵심 수정: Walk Leg에 실제 정류장 좌표 사용

```java
// 신규 TransitLegAssembler.java — 보간 제거, ODsay 실제 좌표 사용
@Component
public class TransitLegAssembler {

    public List<TransitLeg> assemble(List<OdsaySubPath> subPaths, DisabilityType type) {
        List<TransitLeg> legs = new ArrayList<>();

        for (int i = 0; i < subPaths.size(); i++) {
            OdsaySubPath sub = subPaths.get(i);

            // ODsay subPath의 실제 좌표를 그대로 사용 (보간 없음)
            GeoPoint from = new GeoPoint(sub.startY(), sub.startX());
            GeoPoint to   = new GeoPoint(sub.endY(),   sub.endX());

            TransitLeg leg = switch (sub.trafficType()) {
                case 3 -> buildWalkLeg(sub, from, to, type, i, subPaths);
                case 2 -> buildBusLeg(sub, from, to);
                case 1 -> buildSubwayLeg(sub, from, to);
                default -> null;
            };

            if (leg != null) legs.add(leg);
        }
        return legs;
    }

    private TransitLeg buildWalkLeg(
        OdsaySubPath sub, GeoPoint from, GeoPoint to,
        DisabilityType type, int idx, List<OdsaySubPath> allSubs
    ) {
        // 이전 subPath가 지하철이면 → from은 지하철역 출구 좌표
        // 다음 subPath가 지하철이면 → to는 지하철역 입구 좌표 (MOBILITY: 엘리베이터 좌표로 대체)
        return new WalkLegSpec(from, to, type,
            isSubwayConnected(allSubs, idx));
    }

    private boolean isSubwayConnected(List<OdsaySubPath> subs, int walkIdx) {
        if (walkIdx + 1 < subs.size() && subs.get(walkIdx + 1).trafficType() == 1) return true;
        if (walkIdx - 1 >= 0 && subs.get(walkIdx - 1).trafficType() == 1) return true;
        return false;
    }

    private TransitLeg buildBusLeg(OdsaySubPath sub, GeoPoint from, GeoPoint to) {
        OdsayLane lane = sub.lane().get(0);
        return new BusLegSpec(
            from, to,
            lane.busRouteId(),
            lane.busNo(),
            sub.startName(),    // 실제 탑승 정류장명
            sub.endName(),      // 실제 하차 정류장명
            sub.startArsID(),   // BIMS 조회용 정류장 ID
            sub.sectionTime()
        );
    }

    private TransitLeg buildSubwayLeg(OdsaySubPath sub, GeoPoint from, GeoPoint to) {
        OdsayLane lane = sub.lane().get(0);
        return new SubwayLegSpec(
            from, to,
            lane.name(),        // "부산 1호선"
            sub.startName(),    // "서면"
            sub.endName(),      // "남포"
            sub.startID(),      // 역 ID (subway_station_elevators 조회용)
            sub.endID(),
            sub.sectionTime()
        );
    }
}
```

---

## 5. Walk Leg GH 재계산 + 엘리베이터 endpoint 대체

```java
@Component
public class WalkLegRecomputer {

    private final GraphHopperClient ghClient;
    private final SubwayStationElevatorRepository elevatorRepo;

    public Optional<ComputedWalkLeg> recompute(
        WalkLegSpec spec, DisabilityType type
    ) {
        GeoPoint from = spec.from();
        GeoPoint to   = spec.to();

        // MOBILITY + 지하철 연결 구간: 역 ID로 엘리베이터 조회 → endpoint 대체
        if (type == DisabilityType.MOBILITY && spec.isSubwayConnected()) {
            String stationId = resolveStationId(spec);  // ODsay startID/endID
            Optional<SubwayStationElevator> elev =
                elevatorRepo.findNearestByStationId(stationId, to.lat(), to.lng());

            if (elev.isEmpty()) {
                log.info("엘리베이터 없음 → 후보 탈락: stationId={}", stationId);
                return Optional.empty();
            }
            // 역 중심 좌표 → 실제 엘리베이터 입구 좌표로 교체
            to = elev.get().toGeoPoint();
        }

        String profile = type == MOBILITY ? "wheelchair_safe" : "visual_safe";

        try {
            GhRouteResponse resp = ghClient.route(from, to, profile,
                List.of("stairs_state", "avg_slope_percent", "surface_state"));

            if (resp == null || resp.paths().isEmpty()) return Optional.empty();

            return Optional.of(new ComputedWalkLeg(
                from, to, resp.paths().get(0).distance(),
                (int) Math.ceil(resp.paths().get(0).time() / 60_000.0),
                resp.paths().get(0), profile
            ));
        } catch (RouteNotFoundException e) {
            log.info("GH walk 경로 없음: from={},{} to={},{}", from.lat(), from.lng(), to.lat(), to.lng());
            return Optional.empty();
        }
    }
}
```

---

## 6. Bus Leg 검증 (저상버스 + BIMS 실시간)

```java
@Component
public class BusLegVerifier {

    private final LowFloorBusRouteRepository busRouteRepo;
    private final BimsClient bimsClient;

    /**
     * @return empty() → 후보 탈락
     */
    public Optional<VerifiedBusLeg> verify(BusLegSpec spec, DisabilityType type) {
        if (type == DisabilityType.VISUAL) {
            // VISUAL은 저상버스 검증 불필요
            return Optional.of(new VerifiedBusLeg(spec, false, false));
        }

        // 1. 정적 DB 검증 (has_low_floor)
        String routeId = spec.routeId();
        Optional<LowFloorBusRoute> route = busRouteRepo.findById(routeId);

        if (route.isEmpty()) {
            log.info("저상버스 DB에 없는 노선: routeId={}, routeNo={}", routeId, spec.routeNo());
            return Optional.empty();  // 탈락
        }
        if (!route.get().hasLowFloor()) {
            log.info("저상버스 아님: routeId={}, routeNo={}", routeId, spec.routeNo());
            return Optional.empty();  // 탈락
        }

        // 2. BIMS 실시간 override (실패해도 계속)
        boolean bimsConfirmed = false;
        try {
            // spec.boardArsId() = ODsay의 startArsID (정확한 정류장 ID)
            bimsConfirmed = bimsClient.isLowFloorExpected(spec.boardArsId(), routeId);
        } catch (Exception e) {
            log.debug("BIMS 실시간 조회 실패, static 기준 유지: {}", e.getMessage());
        }

        return Optional.of(new VerifiedBusLeg(spec, true, bimsConfirmed));
    }
}
```

---

## 7. Subway Leg 검증 + 역 ID 기반 엘리베이터 조회

```java
@Component
public class SubwayLegVerifier {

    private final SubwayStationElevatorRepository elevatorRepo;

    /**
     * ODsay startID, endID를 역 식별자로 사용
     */
    public Optional<VerifiedSubwayLeg> verify(SubwayLegSpec spec, DisabilityType type) {
        if (type == DisabilityType.VISUAL) {
            return Optional.of(new VerifiedSubwayLeg(spec, true, true));
        }

        // 승차역 엘리베이터 확인 (ODsay startID 사용)
        String boardStationId = spec.boardStationId();
        if (!elevatorRepo.existsByStationId(boardStationId)) {
            log.info("승차역 엘리베이터 없음: stationId={}, name={}", boardStationId, spec.boardStationName());
            return Optional.empty();
        }

        // 하차역 엘리베이터 확인 (ODsay endID 사용)
        String alightStationId = spec.alightStationId();
        if (!elevatorRepo.existsByStationId(alightStationId)) {
            log.info("하차역 엘리베이터 없음: stationId={}, name={}", alightStationId, spec.alightStationName());
            return Optional.empty();
        }

        return Optional.of(new VerifiedSubwayLeg(spec, true, true));
    }
}
```

---

## 8. 후보 병렬 평가 (순차 처리 제거)

```java
@Component
public class TransitCandidateEvaluator {

    private final TransitLegAssembler assembler;
    private final WalkLegRecomputer walkRecomputer;
    private final BusLegVerifier busVerifier;
    private final SubwayLegVerifier subwayVerifier;

    private final ExecutorService executor = Executors.newFixedThreadPool(10);

    public List<AccessibleTransitCandidate> evaluateAll(
        List<OdsayPath> paths, DisabilityType type
    ) {
        // 후보 병렬 평가
        List<CompletableFuture<Optional<AccessibleTransitCandidate>>> futures = paths.stream()
            .map(path -> CompletableFuture
                .supplyAsync(() -> evaluateSingle(path, type), executor)
                .orTimeout(8, TimeUnit.SECONDS)
                .exceptionally(ex -> {
                    log.warn("후보 평가 실패: {}", ex.getMessage());
                    return Optional.empty();
                }))
            .toList();

        return futures.stream()
            .map(CompletableFuture::join)
            .filter(Optional::isPresent)
            .map(Optional::get)
            .sorted(Comparator
                .comparingInt(AccessibleTransitCandidate::totalTimeMinute)
                .thenComparingInt(AccessibleTransitCandidate::walkDistanceMeter)
                .thenComparingInt(AccessibleTransitCandidate::transferCount))
            .limit(3)
            .toList();
    }

    private Optional<AccessibleTransitCandidate> evaluateSingle(OdsayPath path, DisabilityType type) {
        // ODsay subPath → 내부 leg spec 목록 (실제 좌표 사용)
        List<TransitLeg> legSpecs = assembler.assemble(path.subPath(), type);

        List<ResolvedLeg> resolved = new ArrayList<>();
        int totalWalkDistance = 0;

        for (TransitLeg leg : legSpecs) {
            Optional<ResolvedLeg> result = switch (leg) {
                case WalkLegSpec w -> walkRecomputer.recompute(w, type)
                    .map(ResolvedLeg::walk);
                case BusLegSpec b -> busVerifier.verify(b, type)
                    .map(ResolvedLeg::bus);
                case SubwayLegSpec s -> subwayVerifier.verify(s, type)
                    .map(ResolvedLeg::subway);
                default -> Optional.empty();
            };

            if (result.isEmpty()) return Optional.empty();  // 하나라도 실패 → 탈락
            if (leg instanceof WalkLegSpec) totalWalkDistance += result.get().distanceMeter();
            resolved.add(result.get());
        }

        return Optional.of(buildCandidate(path, resolved, totalWalkDistance, type));
    }
}
```

---

## 9. AccessibleTransitService — 진입점 (오케스트레이터)

```java
// svc_plan_04의 RouteSearchService.executeOption()에서 호출하는 최상위 서비스
@Service
@RequiredArgsConstructor
public class AccessibleTransitService {

    private final OdsayClient odsayClient;
    private final TransitCandidateEvaluator evaluator;
    private final RedisTemplate<String, AccessibleTransitResult> redisTemplate;

    private static final Duration CACHE_HIT_TTL  = Duration.ofSeconds(300);
    private static final Duration CACHE_MISS_TTL = Duration.ofSeconds(30);

    public RouteOptionResult orchestrate(RouteSearchRequest req) {
        String cacheKey = buildCacheKey(req);

        // 캐시 Hit
        AccessibleTransitResult cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            return cached.available()
                ? RouteOptionResult.available(ACCESSIBLE_TRANSIT, cached)
                : RouteOptionResult.unavailable(ACCESSIBLE_TRANSIT, cached.reason());
        }

        // ODsay 경로 탐색
        List<OdsayPath> paths;
        try {
            paths = odsayClient.searchPaths(req.startPoint(), req.endPoint());
        } catch (TransitApiException e) {
            return cacheAndReturn(cacheKey, RouteOptionResult.unavailable(
                ACCESSIBLE_TRANSIT, "TRANSIT_API_UNAVAILABLE"), CACHE_MISS_TTL);
        }

        if (paths.isEmpty()) {
            return cacheAndReturn(cacheKey, RouteOptionResult.unavailable(
                ACCESSIBLE_TRANSIT, "NO_TRANSIT_PATHS"), CACHE_MISS_TTL);
        }

        // 후보 병렬 평가
        List<AccessibleTransitCandidate> candidates =
            evaluator.evaluateAll(paths, req.disabilityType());

        if (candidates.isEmpty()) {
            return cacheAndReturn(cacheKey, RouteOptionResult.unavailable(
                ACCESSIBLE_TRANSIT, "NO_ACCESSIBLE_TRANSIT"), CACHE_MISS_TTL);
        }

        RouteOptionResult result = RouteOptionResult.available(ACCESSIBLE_TRANSIT, candidates);
        return cacheAndReturn(cacheKey, result, CACHE_HIT_TTL);
    }

    private String buildCacheKey(RouteSearchRequest req) {
        // 소수점 4자리 반올림 (약 11m 정밀도)
        return "transit:%s:%.4f:%.4f:%.4f:%.4f".formatted(
            req.disabilityType(),
            req.startPoint().lat(), req.startPoint().lng(),
            req.endPoint().lat(),   req.endPoint().lng()
        );
    }

    private RouteOptionResult cacheAndReturn(String key, RouteOptionResult result, Duration ttl) {
        redisTemplate.opsForValue().set(key,
            AccessibleTransitResult.from(result), ttl);
        return result;
    }
}
```

**Redis 설정 (application.yml, svc_plan_00 전체 포함):**
```yaml
spring:
  data:
    redis:
      host: ${SPRING_DATA_REDIS_HOST:redis}
      port: ${SPRING_DATA_REDIS_PORT:6379}
      password: ${REDIS_PASSWORD}
```

---

## 10. ODsay 클라이언트 실 연동 + API 키 발급

### ODsay API 키 발급

```
1. https://lab.odsay.com 회원가입
2. 마이페이지 → API 키 발급 → "대중교통 경로탐색" 권한 신청
3. 발급된 키를 .env의 ODSAY_API_KEY에 설정
4. 무료 플랜: 하루 1,000건 → 개발/POC에 충분
```

```java
@Component
public class OdsayClient {

    @Value("${transit.odsay.api-key}")
    private String apiKey;

    private final RestTemplate restTemplate;

    public List<OdsayPath> searchPaths(GeoPoint start, GeoPoint end) {
        URI uri = UriComponentsBuilder
            .fromHttpUrl("https://api.odsay.com/v1/api/searchPubTransPathT")
            .queryParam("apiKey",     apiKey)
            .queryParam("SX",         start.lng())
            .queryParam("SY",         start.lat())
            .queryParam("EX",         end.lng())
            .queryParam("EY",         end.lat())
            .queryParam("SearchType", 0)
            .build().toUri();

        try {
            OdsaySearchResponse resp = restTemplate.getForObject(uri, OdsaySearchResponse.class);

            if (resp == null || resp.result() == null || resp.result().path() == null) {
                return List.of();
            }
            return resp.result().path();

        } catch (RestClientException e) {
            log.error("ODsay API 호출 실패: {}", e.getMessage());
            throw new TransitApiException("ODsay API 장애: " + e.getMessage());
        }
    }
}
```

**Jackson 역직렬화 주의사항:**
- ODsay는 `passStopList.stations[].x`, `y`가 **문자열**로 옴 → `Double.parseDouble()` 필요
- `trafficType` 숫자 매핑: 1=지하철, 2=버스, 3=도보
- 경로가 없으면 `result.path`가 null (빈 배열 아님)
- `startArsID`, `endArsID`는 버스 subPath에만 존재. 지하철 subPath에는 `startID`, `endID` 사용

```java
// OdsaySearchResponse Jackson 역직렬화 핵심
// passStopList.stations[].x/y가 문자열임에 주의
public record OdsayStation(
    int index,
    String stationName,
    @JsonProperty("x") String xStr,     // 문자열 경도
    @JsonProperty("y") String yStr,     // 문자열 위도
    String arsId,
    String stationID
) {
    public double lng() { return Double.parseDouble(xStr); }
    public double lat() { return Double.parseDouble(yStr); }
}
```

---

## 10. BIMS 실시간 API 연동

```java
@Component
public class BimsClient {

    @Value("${transit.bims.service-key}")
    private String serviceKey;

    /**
     * @param arsId ODsay의 startArsID 값 (정확한 정류장 ID)
     * @param routeId ODsay의 lane[].busRouteId 값
     */
    public boolean isLowFloorExpected(String arsId, String routeId) {
        if (arsId == null || arsId.isBlank()) return false;

        try {
            URI uri = UriComponentsBuilder
                .fromHttpUrl("https://apis.data.go.kr/6260000/BusanBIMS/getBusArrivalList")
                .queryParam("serviceKey", serviceKey)
                .queryParam("arsId",      arsId)
                .queryParam("routeId",    routeId)
                .build().toUri();

            BusArrivalResponse resp = restTemplate.getForObject(uri, BusArrivalResponse.class);

            return resp != null && resp.items() != null && resp.items().stream()
                .anyMatch(item ->
                    "1".equals(item.lowplate1()) || "1".equals(item.lowplate2()));

        } catch (Exception e) {
            log.warn("BIMS 실시간 조회 실패: arsId={}, routeId={}, error={}", arsId, routeId, e.getMessage());
            return false;  // 실패 시 보수적으로 false (static DB 기준 유지)
        }
    }
}
```

---

## 11. 응답 구성 (실제 정류장 좌표 포함)

```java
private AccessibleTransitCandidate buildCandidate(
    OdsayPath path, List<ResolvedLeg> resolved,
    int totalWalkDistance, DisabilityType type
) {
    List<LegDto> legDtos = new ArrayList<>();
    List<MarkerDto> markers = new ArrayList<>();

    for (int i = 0; i < resolved.size(); i++) {
        ResolvedLeg leg = resolved.get(i);

        // 마커 좌표 = ODsay가 준 실제 정류장/역 좌표 (보간값 아님)
        switch (leg.type()) {
            case WALK -> {
                // walk leg은 GH가 재계산한 실제 경로
                legDtos.add(LegDto.walk(i+1, leg.distanceMeter(), leg.durationMinute(),
                    leg.geometry()));
            }
            case BUS -> {
                VerifiedBusLeg bus = (VerifiedBusLeg) leg;
                markers.add(MarkerDto.busBoard(bus.spec().boardName(),
                    bus.spec().from().lat(), bus.spec().from().lng()));  // 실제 정류장 좌표
                markers.add(MarkerDto.busAlight(bus.spec().alightName(),
                    bus.spec().to().lat(), bus.spec().to().lng()));
                legDtos.add(LegDto.bus(i+1, bus.spec().routeNo(),
                    bus.spec().boardName(), bus.spec().alightName(),
                    bus.isLowFloor(), bus.bimsConfirmed()));
            }
            case SUBWAY -> {
                VerifiedSubwayLeg sub = (VerifiedSubwayLeg) leg;
                markers.add(MarkerDto.subwayBoard(sub.spec().boardStationName(),
                    sub.spec().from().lat(), sub.spec().from().lng()));  // 실제 역 좌표
                markers.add(MarkerDto.subwayAlight(sub.spec().alightStationName(),
                    sub.spec().to().lat(), sub.spec().to().lng()));
                legDtos.add(LegDto.subway(i+1, sub.spec().lineName(),
                    sub.spec().boardStationName(), sub.spec().alightStationName()));
            }
        }
    }

    return AccessibleTransitCandidate.builder()
        .totalTimeMinute(path.info().totalTime())
        .walkDistanceMeter(totalWalkDistance)
        .transferCount(path.info().busTransitCount() + path.info().subwayTransitCount() - 1)
        .legs(legDtos)
        .markers(markers)
        .lowFloorConfirmed(type == MOBILITY)
        .elevatorAccessConfirmed(type == MOBILITY)
        .build();
}
```

---

## 12. 탈락 기준 정리

| 조건 | 처리 |
|---|---|
| ODsay API 실패 | `TRANSIT_API_UNAVAILABLE` (전체) |
| Walk leg: GH 경로 없음 | 해당 후보 탈락 |
| MOBILITY + Walk: 지하철역 엘리베이터 없음 | 해당 후보 탈락 |
| MOBILITY + Bus: `low_floor_bus_routes` 미등록 | 해당 후보 탈락 |
| MOBILITY + Bus: `has_low_floor = false` | 해당 후보 탈락 |
| MOBILITY + Subway: 승차/하차역 엘리베이터 없음 | 해당 후보 탈락 |
| 후보 평가 타임아웃 (8초) | 해당 후보 탈락 |
| 모든 후보 탈락 | `NO_ACCESSIBLE_TRANSIT` |

---

## 13. 테스트 요구사항

### 단위 테스트

Fixture 파일 위치: `backend/src/test/resources/fixtures/odsay_response_sample.json`

실제 ODsay API를 한 번 호출해 응답을 저장해 두고 테스트에서 재사용:
```bash
# 실제 API 호출 후 fixture 저장 (최초 1회)
curl "https://api.odsay.com/v1/api/searchPubTransPathT?apiKey=$ODSAY_API_KEY&SX=129.0756&SY=35.1795&EX=129.0402&EY=35.1039&SearchType=0" \
  > backend/src/test/resources/fixtures/odsay_response_sample.json
```

```java
// TransitLegAssemblerTest
// 실 ODsay 응답 JSON fixture 사용 (실제 응답 샘플로 테스트)
@Test
void assembleUsesActualCoordinates() {
    OdsayPath path = parseFixture("odsay_response_sample.json");
    List<TransitLeg> legs = assembler.assemble(path.subPath(), MOBILITY);

    // Walk leg 시작 좌표 = ODsay subPath startX/Y (보간값 아님)
    WalkLegSpec walkLeg = (WalkLegSpec) legs.get(0);
    assertThat(walkLeg.from().lat()).isEqualTo(35.1795);
    assertThat(walkLeg.from().lng()).isEqualTo(129.0756);

    // Bus leg routeId = ODsay lane[].busRouteId
    BusLegSpec busLeg = (BusLegSpec) legs.get(1);
    assertThat(busLeg.routeId()).isEqualTo("5200000086");
    assertThat(busLeg.routeNo()).isEqualTo("86");
    assertThat(busLeg.boardName()).isEqualTo("부산시청");
}

// BusLegVerifierTest
@Test
void mobilityRejectsNonLowFloorBus() {
    given(busRouteRepo.findById("5200000086"))
        .willReturn(Optional.of(new LowFloorBusRoute("5200000086", "86", false)));

    Optional<VerifiedBusLeg> result = verifier.verify(busSpec, MOBILITY);
    assertThat(result).isEmpty();
}

@Test
void visualSkipsBusVerification() {
    Optional<VerifiedBusLeg> result = verifier.verify(busSpec, VISUAL);
    assertThat(result).isPresent();
    verify(busRouteRepo, never()).findById(any());
}
```

### 통합 테스트

- 부산 실제 좌표로 요청 → 응답의 마커 좌표가 실제 정류장/역 근처인지 확인
- MOBILITY 요청 → 저상버스만 포함된 후보 반환 확인
- VISUAL 요청 → 저상버스/엘리베이터 검증 없이 후보 반환 확인
- ODsay Mock 응답에서 버스 후보 + 지하철 후보 분리 반환 확인

---

## 14. 완료 기준

- [ ] ODsay 실 API 연동 (stub 완전 제거)
- [ ] Walk leg from/to = ODsay subPath 실제 좌표 (선형 보간 없음)
- [ ] Bus leg routeId, routeNo, 정류장명 = ODsay 실 응답 파싱
- [ ] Subway leg 역명, 역ID = ODsay 실 응답 파싱
- [ ] MOBILITY + 지하철: walk endpoint → 엘리베이터 좌표 대체
- [ ] MOBILITY + 버스: `low_floor_bus_routes` DB 검증
- [ ] BIMS 실 API 연동 (trip 단위 override)
- [ ] 후보 평가 병렬 처리 (순차 처리 제거)
- [ ] 지도 마커 좌표 = 실제 정류장/역 좌표
- [ ] 단위 테스트 (ODsay fixture 기반), 통합 테스트 통과
