# svc_plan_03: GraphHopper Import + 4 프로필 + LM 준비

> **작성일:** 2026-04-18 (POC 분석 반영 업데이트)  
> **목적:** road_segments 9개 속성 → GH EV 채우기, 4개 프로필 custom model, LM 준비  
> **선행 조건:** svc_plan_02 완료 (road_segments 속성 적재)  
> **후행 단계:** svc_plan_04 (도보 라우팅 API)

---

## 1. POC의 근본적 설계 결함과 해결 방향

### POC 문제

```java
// POC IeumGraphHopperFactory.java — 문제의 원인
private CustomModel customModel(WalkProfileType walkProfileType) {
    return new CustomModel()
        .setDistanceInfluence(walkProfileType.distanceInfluence())
        .addToSpeed(Statement.If("true", LIMIT, VehicleSpeed.key(FOOT_VEHICLE)))
        .addToPriority(Statement.If(
            walkProfileType.passEncodedValue() + " == false",  // ← 이게 전부
            MULTIPLY, "0"));
}
// VISUAL_SAFE_PASS / WHEELCHAIR_SAFE_PASS 등 Boolean 4개를 import 시 미리 계산
// 대부분 UNKNOWN → PASS=true → 4개 프로필 경로 동일
```

### 신규 설계

- **Boolean PASS EV 제거.** `VISUAL_SAFE_PASS`, `WHEELCHAIR_SAFE_PASS` 등 사용하지 않음.
- **9개 Attribute EV 직접 등록** (braille_block_state, avg_slope_percent 등)
- **Custom model YAML에서 속성값 직접 비교** → 런타임 정책 변경 가능
- **`avg_slope_percent` → `DecimalEncodedValue`** → `avg_slope_percent > 3.0` 비교 가능

---

## 2. 프로젝트 구조

```
ieumgil-svc/
├── graphhopper/
│   ├── Dockerfile                   # GH 컨테이너 이미지
│   ├── config.yaml                  # GH 메인 설정
│   └── custom_models/
│       ├── visual_safe.json
│       ├── visual_fast.json
│       ├── wheelchair_safe.json
│       └── wheelchair_fast.json
└── gh-plugin/                       # GH 커스텀 EV 플러그인 (별도 Maven 모듈)
    ├── pom.xml
    └── src/main/java/
        ├── com/graphhopper/application/IeumGraphHopperApplication.java
        ├── com/graphhopper/http/IeumGraphHopperBundle.java
        ├── com/graphhopper/http/IeumGraphHopperManaged.java
        └── com/ieumgil/gh/
            ├── IeumGraphHopper.java
            ├── IeumImportRegistry.java
            ├── IeumEncodedValues.java
            ├── IeumTagParser.java
            └── SegmentEvLoader.java
```

**GH 플러그인 빌드 흐름:**
1. `gh-plugin/` Maven 모듈을 `mvn package` → `ieum-gh-plugin.jar` 생성
2. `graphhopper/Dockerfile`에서 GH web jar + 플러그인 jar를 함께 COPY
3. 실행 엔트리포인트는 공식 `GraphHopperApplication`이 아니라 `IeumGraphHopperApplication`

> **중요:** GraphHopper 9.1 web jar는 외부 classpath jar를 자동으로 스캔해 `ImportRegistry`를 주입하지 않는다.
> 따라서 단순 플러그인 jar 추가만으로는 커스텀 EV/TagParser가 활성화되지 않으며,
> `IeumGraphHopperManaged`에서 `new IeumGraphHopper().setImportRegistry(...)`를 적용하는
> 커스텀 앱 진입점이 필요하다.

> **선행 조건 (svc_plan_00 참조):** GH jar는 svc_plan_00의 Dockerfile에서
> GitHub Releases에서 자동 다운로드됨. 로컬 빌드 불필요.

---

## 3. GH 커스텀 EV 9개 (Java)

```java
// IeumEncodedValues.java
public final class IeumEncodedValues {

    // Enum 3-value EVs
    public static final String BRAILLE_BLOCK = "braille_block_state";  // YES/NO/UNKNOWN
    public static final String AUDIO_SIGNAL  = "audio_signal_state";
    public static final String CURB_RAMP     = "curb_ramp_state";
    public static final String STAIRS        = "stairs_state";
    public static final String ELEVATOR      = "elevator_state";

    // Enum 4-value EV
    public static final String WIDTH         = "width_state";          // ADEQUATE_150/ADEQUATE_120/NARROW/UNKNOWN

    // Enum 5-value EVs
    public static final String SURFACE       = "surface_state";        // PAVED/GRAVEL/UNPAVED/OTHER/UNKNOWN
    public static final String CROSSING      = "crossing_state";       // TRAFFIC_SIGNALS/UNCONTROLLED/UNMARKED/NO/UNKNOWN

    // Decimal EV (핵심)
    public static final String AVG_SLOPE     = "avg_slope_percent";    // 0.0 ~ 30.0

    private IeumEncodedValues() {}
}
```

```java
public enum AccessibilityState { YES, NO, UNKNOWN }
public enum WidthState { ADEQUATE_150, ADEQUATE_120, NARROW, UNKNOWN }
public enum SurfaceState { PAVED, GRAVEL, UNPAVED, OTHER, UNKNOWN }
public enum CrossingState { TRAFFIC_SIGNALS, UNCONTROLLED, UNMARKED, NO, UNKNOWN }

public final class IeumEncodedValues {
    public static EnumEncodedValue<AccessibilityState> brailleBlock() {
        return new EnumEncodedValue<>(BRAILLE_BLOCK, AccessibilityState.class);
    }

    public static EnumEncodedValue<AccessibilityState> audioSignal() {
        return new EnumEncodedValue<>(AUDIO_SIGNAL, AccessibilityState.class);
    }

    public static EnumEncodedValue<AccessibilityState> curbRamp() {
        return new EnumEncodedValue<>(CURB_RAMP, AccessibilityState.class);
    }

    public static EnumEncodedValue<AccessibilityState> stairs() {
        return new EnumEncodedValue<>(STAIRS, AccessibilityState.class);
    }

    public static EnumEncodedValue<AccessibilityState> elevator() {
        return new EnumEncodedValue<>(ELEVATOR, AccessibilityState.class);
    }

    public static EnumEncodedValue<WidthState> width() {
        return new EnumEncodedValue<>(WIDTH, WidthState.class);
    }

    public static EnumEncodedValue<SurfaceState> surface() {
        return new EnumEncodedValue<>(SURFACE, SurfaceState.class);
    }

    public static EnumEncodedValue<CrossingState> crossing() {
        return new EnumEncodedValue<>(CROSSING, CrossingState.class);
    }

    public static DecimalEncodedValue avgSlope() {
        return new DecimalEncodedValueImpl(AVG_SLOPE, 7, 0.0, 0.25, false, false, false);
    }
}
```

`StringEncodedValue`가 아니라 Java enum 기반 `EnumEncodedValue`를 사용한다.

---

## 4. DB → EV 매핑 (Bulk Load)

```java
// IeumTagParser.java
public class IeumTagParser implements TagParser {

    private final Map<Long, List<SegmentEV>> segmentsByWayId;
    private final ConcurrentMap<Long, AtomicInteger> ordinalByWay = new ConcurrentHashMap<>();

    @Override
    public void handleWayTags(int edgeId, EdgeIntAccess edgeIntAccess, ReaderWay way, IntsRef relationFlags) {
        long wayId = way.getId();
        int ordinal = ordinalByWay.computeIfAbsent(wayId, ignored -> new AtomicInteger()).getAndIncrement();

        SegmentEV ev = findSegment(wayId, ordinal).orElse(SegmentEV.unknown());

        brailleBlockEV.setEnum(false, edgeId, edgeIntAccess, ev.brailleBlockState());
        audioSignalEV.setEnum(false, edgeId, edgeIntAccess, ev.audioSignalState());
        curbRampEV.setEnum(false, edgeId, edgeIntAccess, ev.curbRampState());
        widthEV.setEnum(false, edgeId, edgeIntAccess, ev.widthState());
        surfaceEV.setEnum(false, edgeId, edgeIntAccess, ev.surfaceState());
        stairsEV.setEnum(false, edgeId, edgeIntAccess, ev.stairsState());
        elevatorEV.setEnum(false, edgeId, edgeIntAccess, ev.elevatorState());
        crossingEV.setEnum(false, edgeId, edgeIntAccess, ev.crossingState());
        avgSlopeEV.setDecimal(false, edgeId, edgeIntAccess, ev.avgSlopePercentOrZero());
    }
}
```

```java
// 시작 시 road_segments 전체 bulk load
// per-edge DB query 절대 금지
@Component
public class SegmentEvLoader {

    public Map<Long, SegmentEV> loadAll(JdbcTemplate jdbc) {
        Map<Long, SegmentEV> map = new HashMap<>(200_000);
        jdbc.query("""
            SELECT source_way_id, segment_ordinal,
                   braille_block_state, audio_signal_state, curb_ramp_state,
                   width_state, surface_state, stairs_state, elevator_state,
                   crossing_state, avg_slope_percent
            FROM road_segments
            """,
            rs -> {
                long key = rs.getLong("source_way_id") * 1000L + rs.getInt("segment_ordinal");
                map.put(key, SegmentEV.fromResultSet(rs));
            }
        );
        return map;
    }
}
```

---

## 5. GH config.yaml

```yaml
graphhopper:
  graph.location: /data/graph-cache
  datareader.file: /data/busan.osm.pbf

  custom_models.directory: /config/custom_models

  # 9개 EV 이름 등록 (실제 EV 타입/bit는 IeumImportRegistry에서 생성)
  graph.encoded_values: >-
    foot_access,foot_average_speed,
    braille_block_state,audio_signal_state,curb_ramp_state,
    stairs_state,elevator_state,width_state,
    surface_state,crossing_state,avg_slope_percent

  profiles:
    - name: visual_safe
      custom_model_files: [visual_safe.json]
    - name: visual_fast
      custom_model_files: [visual_fast.json]
    - name: wheelchair_safe
      custom_model_files: [wheelchair_safe.json]
    - name: wheelchair_fast
      custom_model_files: [wheelchair_fast.json]

  profiles_ch: []  # CH 사용 안 함 (custom model 런타임 적용 불가)

  profiles_lm:
    - profile: visual_safe
    - profile: visual_fast
    - profile: wheelchair_safe
    - profile: wheelchair_fast
  prepare.lm.landmarks: 16

  import.osm.ignored_highways: motorway,trunk
  graph.dataaccess.default_type: RAM_STORE
```

---

## 6. Custom Model JSON 4개 (핵심)

### visual_safe.json

```json
{
  "speed": [
    { "if": "true", "limit_to": "foot_average_speed" },
    { "if": "avg_slope_percent > 8.0", "limit_to": 0 },
    { "if": "braille_block_state == NO", "limit_to": 0 },
    { "if": "crossing_state != NO && audio_signal_state == NO", "limit_to": 0 },
    { "if": "stairs_state == YES", "multiply_by": 0.2 },
    { "if": "avg_slope_percent > 5.0", "multiply_by": 0.7 }
  ],
  "priority": [
    { "if": "true", "multiply_by": 1.0 },
    { "if": "braille_block_state == UNKNOWN", "multiply_by": 0.5 },
    { "if": "crossing_state != NO && audio_signal_state == UNKNOWN", "multiply_by": 0.6 }
  ],
  "distance_influence": 80
}
```

### visual_fast.json

```json
{
  "speed": [
    { "if": "true", "limit_to": "foot_average_speed" },
    { "if": "avg_slope_percent > 8.0", "limit_to": 0 },
    { "if": "crossing_state != NO && audio_signal_state == NO", "limit_to": 0 },
    { "if": "stairs_state == YES", "multiply_by": 0.3 },
    { "if": "avg_slope_percent > 5.0", "multiply_by": 0.5 }
  ],
  "priority": [
    { "if": "true", "multiply_by": 1.0 },
    { "if": "braille_block_state == NO", "multiply_by": 0.4 },
    { "if": "braille_block_state == UNKNOWN", "multiply_by": 0.7 }
  ],
  "distance_influence": 30
}
```

### wheelchair_safe.json

```json
{
  "speed": [
    { "if": "true", "limit_to": "foot_average_speed" },
    { "if": "stairs_state == YES", "limit_to": 0 },
    { "if": "surface_state == GRAVEL || surface_state == UNPAVED", "limit_to": 0 },
    { "if": "width_state == NARROW", "limit_to": 0 },
    { "if": "avg_slope_percent > 3.0", "limit_to": 0 },
    { "if": "crossing_state != NO && curb_ramp_state == NO", "limit_to": 0 }
  ],
  "priority": [
    { "if": "true", "multiply_by": 1.0 },
    { "if": "width_state == UNKNOWN", "multiply_by": 0.5 },
    { "if": "crossing_state != NO && curb_ramp_state == UNKNOWN", "multiply_by": 0.4 },
    { "if": "stairs_state == UNKNOWN", "multiply_by": 0.4 }
  ],
  "distance_influence": 80
}
```

### wheelchair_fast.json

```json
{
  "speed": [
    { "if": "true", "limit_to": "foot_average_speed" },
    { "if": "stairs_state == YES", "limit_to": 0 },
    { "if": "surface_state == GRAVEL || surface_state == UNPAVED", "limit_to": 0 },
    { "if": "width_state == NARROW", "limit_to": 0 },
    { "if": "avg_slope_percent > 5.0", "limit_to": 0 }
  ],
  "priority": [
    { "if": "true", "multiply_by": 1.0 },
    { "if": "avg_slope_percent > 3.0", "multiply_by": 0.5 },
    { "if": "width_state == UNKNOWN", "multiply_by": 0.6 },
    { "if": "stairs_state == UNKNOWN", "multiply_by": 0.5 }
  ],
  "distance_influence": 30
}
```

---

## 7. Dockerfile

```dockerfile
FROM openjdk:21-slim

WORKDIR /graphhopper

# svc_plan_00 Dockerfile에서 GH 9.1 jar는 GitHub Releases에서 자동 다운로드됨
# 이 Dockerfile은 docker-compose build 시 자동 실행 — 수동 jar 다운로드 불필요
COPY graphhopper-web-9.1.jar graphhopper.jar
COPY ieum-gh-plugin.jar /graphhopper/plugins/ieum-gh-plugin.jar
COPY config.yaml /config/config.yaml
COPY custom_models/ /config/custom_models/

EXPOSE 8989

# GH 플러그인 jar의 커스텀 Application을 실행
ENTRYPOINT ["java", "-Xmx4g",
            "-cp", "/graphhopper/plugins/*:/graphhopper/graphhopper.jar",
            "com.graphhopper.application.IeumGraphHopperApplication",
            "server", "/config/config.yaml"]
```

**메모리:** 부산 규모 도보 네트워크 + LM 4개 프로필 → 최소 4GB 할당.

### GH 플러그인 빌드 (gh-plugin/pom.xml 핵심)

```xml
<project>
  <groupId>com.ieumgil</groupId>
  <artifactId>ieum-gh-plugin</artifactId>
  <version>1.0.0</version>

  <dependencies>
    <dependency>
      <groupId>com.graphhopper</groupId>
      <artifactId>graphhopper-core</artifactId>
      <version>9.1</version>
      <scope>provided</scope>   <!-- GH jar에 이미 포함 -->
    </dependency>
    <dependency>
      <groupId>org.postgresql</groupId>
      <artifactId>postgresql</artifactId>
      <version>42.7.3</version>
    </dependency>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-jdbc</artifactId>
      <version>6.1.6</version>
    </dependency>
  </dependencies>
</project>
```

### SegmentEvLoader — DB 연결 설정

`SegmentEvLoader`는 GH import 실행 시점(컨테이너 기동 시)에 한 번만 실행된다. Spring Boot 백엔드 startup이 아님.

```java
// GH import job 시작 시 DB에서 전체 road_segments 읽어 Map 구성
// DB 접속 정보는 환경변수로 주입 (svc_plan_00 .env 참조)
@Component
public class SegmentEvLoader {

    private final String jdbcUrl;
    private final String dbUser;
    private final String dbPassword;

    public SegmentEvLoader() {
        // GH는 Spring Context 없이 실행 → 환경변수 직접 읽기
        this.jdbcUrl    = System.getenv("DB_JDBC_URL");        // jdbc:postgresql://postgresql:5432/ieumgil
        this.dbUser     = System.getenv("POSTGRES_USER");
        this.dbPassword = System.getenv("POSTGRES_PASSWORD");
    }

    public Map<Long, SegmentEV> loadAll() {
        Map<Long, SegmentEV> map = new HashMap<>(200_000);
        try (Connection conn = DriverManager.getConnection(jdbcUrl, dbUser, dbPassword);
             PreparedStatement ps = conn.prepareStatement("""
                SELECT source_way_id, segment_ordinal,
                       braille_block_state, audio_signal_state, curb_ramp_state,
                       width_state, surface_state, stairs_state, elevator_state,
                       crossing_state, avg_slope_percent
                FROM road_segments
             """);
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                long key = rs.getLong("source_way_id") * 1000L + rs.getInt("segment_ordinal");
                map.put(key, SegmentEV.fromResultSet(rs));
            }
        } catch (SQLException e) {
            throw new RuntimeException("road_segments 로드 실패. svc_plan_02 완료 여부 확인", e);
        }
        return map;
    }
}
```

**실행 순서 명시:**
```
svc_plan_01 완료 (road_segments 전체 적재)
  → svc_plan_02 완료 (9개 속성 ETL)
  → docker compose build graphhopper  (gh-plugin jar 빌드 포함)
  → docker compose up graphhopper      (GH import + LM preparation)
```

---

## 8. 검증 시나리오

### 8-1. 프로필 차이 검증 (가장 중요)

```python
# tests/verify_gh_profiles.py
import json
import urllib.parse
import urllib.request

base = "http://localhost:8989/route"
start = "35.15,129.02"  # 부산 시내 계단 근처
end = "35.16,129.03"

for profile in ["wheelchair_safe", "wheelchair_fast", "visual_safe", "visual_fast"]:
    query = urllib.parse.urlencode([
        ("point", start),
        ("point", end),
        ("profile", profile),
        ("details", "stairs_state"),
        ("details", "avg_slope_percent"),
    ])
    with urllib.request.urlopen(f"{base}?{query}") as resp:
        payload = json.load(resp)
    path = payload["paths"][0]
    print(f"{profile}: {path['distance']:.0f}m, {path['time']//1000//60}min")

# 기대 결과: wheelchair_safe 거리 > wheelchair_fast 거리 (우회로 선택)
# wheelchair_safe != visual_safe (완전히 다른 경로)
```

> 주의: 위 검증은 `svc_plan_02` 실데이터 ETL이 끝나서 `road_segments`에 `stairs_state`, `avg_slope_percent` 등이 실제 값으로 채워진 상태를 전제로 한다.
> 공공데이터가 아직 적재되지 않아 관련 컬럼이 전부 `UNKNOWN/NULL`이면 4개 프로필이 동일 경로를 반환하는 것이 정상이며,
> 이 경우 `svc_plan_03`의 import 성공과 `4개 프로필 분기 검증`은 분리해서 기록한다.

### 8-2. 계단 회피 검증

- 알려진 계단 포함 구간 좌표 → `wheelchair_safe` 경로가 계단 없는 우회로 반환 확인
- `visual_safe`는 같은 구간 통과 가능 (PENALTY만)

### 8-3. 경사도 필터 검증

- `avg_slope_percent > 3.0` 구간 → `wheelchair_safe` 경로에 포함되지 않음
- 동일 구간 → `wheelchair_fast` (> 5.0 기준)는 통과 가능

### 8-4. GH health

```
GET http://localhost:8989/health → 200 OK
```

---

## 9. 완료 기준

- [ ] 9개 EV 정상 등록 (GH 로그 확인)
- [ ] 4개 프로필 LM preparation 완료
- [ ] `wheelchair_safe` vs `visual_safe` 경로가 서로 다름
- [ ] `wheelchair_safe` 경로에 계단 포함 구간 없음
- [ ] `wheelchair_safe` 경로에 avg_slope_percent > 3.0 구간 없음
- [ ] GH `/health` 200 응답
