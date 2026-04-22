# svc_plan_01: 보행 네트워크 파이프라인

> **작성일:** 2026-04-18 (POC 분석 반영 업데이트)  
> **목적:** OSM PBF → anchor 세그먼트 분해 → road_nodes / road_segments DB 적재  
> **대상 레포:** 신규 레포 (ieumgil-svc)  
> **선행 조건:** svc_plan_00 완료 (레포 세팅, DB 기동, Python venv 준비)  
> **후행 단계:** svc_plan_02 (공공데이터 ETL), svc_plan_03 (GH import)

---

## 1. POC 대비 변경 이유

POC(`IeumGraphEncodedValues`)에는 EV가 14개 정의되어 있었으나 실제 라우팅 결정은
`VISUAL_SAFE_PASS / WHEELCHAIR_SAFE_PASS` 등 Boolean EV 4개에만 의존했다.
이 Boolean은 import 시점에 고정 결정되므로, 런타임에 custom model로 세밀하게 조정 불가능.

신규 레포에서는 `avg_slope_percent`를 포함한 **9개 Attribute EV**를 GH custom model YAML에서
직접 비교하는 방식으로 전환한다. 이를 위해 road_segments의 속성 컬럼이 정확히 채워져야 한다.

---

## 2. 기술 스택

- **언어:** Python 3.11+
- **파싱:** `osmium` (PyOsmium 바인딩, OSM PBF 스트리밍 파서)
- **Geometry:** `shapely`, `pyproj`
- **DB:** `psycopg2` + PostGIS
- **실행:** `python etl/build_network.py`
- **배치 크기:** 한 번에 5,000건 bulk insert

---

## 3. 프로젝트 구조 (신규 레포)

```
ieumgil-svc/
├── etl/
│   ├── build_network.py          # svc_plan_01 메인 스크립트
│   ├── etl_slope.py              # svc_plan_02
│   ├── etl_accessibility.py      # svc_plan_02
│   ├── load_transit_ref.py       # svc_plan_05
│   └── data/
│       └── raw/
│           └── busan.osm.pbf
├── backend/                      # Spring Boot (svc_plan_04~)
├── graphhopper/                  # GH config (svc_plan_03)
├── postgresql/
│   └── init/
│       └── 01_schema.sql         # 전체 DDL
└── docker-compose.yml
```

---

## 4. DB 스키마 (PostgreSQL + PostGIS)

```sql
-- postgresql/init/01_schema.sql

-- PostGIS 확장
CREATE EXTENSION IF NOT EXISTS postgis;

-- ─── 보행 네트워크 ─────────────────────────────────────────

CREATE TABLE road_nodes (
    vertex_id       BIGSERIAL   PRIMARY KEY,
    osm_node_id     BIGINT      NOT NULL UNIQUE,
    point           GEOMETRY(POINT, 4326) NOT NULL
);
CREATE INDEX idx_road_nodes_point ON road_nodes USING GIST(point);

CREATE TYPE accessibility_state AS ENUM ('YES', 'NO', 'UNKNOWN');
CREATE TYPE width_state_t       AS ENUM ('ADEQUATE_150', 'ADEQUATE_120', 'NARROW', 'UNKNOWN');
CREATE TYPE surface_state_t     AS ENUM ('PAVED', 'GRAVEL', 'UNPAVED', 'OTHER', 'UNKNOWN');
CREATE TYPE crossing_state_t    AS ENUM ('TRAFFIC_SIGNALS', 'UNCONTROLLED', 'UNMARKED', 'NO', 'UNKNOWN');

CREATE TABLE road_segments (
    edge_id                    BIGSERIAL PRIMARY KEY,
    from_node_id               BIGINT NOT NULL REFERENCES road_nodes(vertex_id),
    to_node_id                 BIGINT NOT NULL REFERENCES road_nodes(vertex_id),
    geom                       GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_meter               NUMERIC(10,2) NOT NULL,
    source_way_id              BIGINT NOT NULL,
    source_osm_from_node_id    BIGINT NOT NULL,
    source_osm_to_node_id      BIGINT NOT NULL,
    segment_ordinal            INT NOT NULL DEFAULT 0,
    walk_access                VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',

    -- GH EV로 등록되는 9개 속성 (모두 공공데이터 ETL로만 채움)
    avg_slope_percent          NUMERIC(6,2),              -- NULL = 미계산
    width_meter                NUMERIC(6,2),
    braille_block_state        accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    audio_signal_state         accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    curb_ramp_state            accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    width_state                width_state_t NOT NULL DEFAULT 'UNKNOWN',
    surface_state              surface_state_t NOT NULL DEFAULT 'UNKNOWN',
    stairs_state               accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    elevator_state             accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    crossing_state             crossing_state_t NOT NULL DEFAULT 'UNKNOWN',

    UNIQUE (source_way_id, source_osm_from_node_id, source_osm_to_node_id)
);
CREATE INDEX idx_road_segments_geom   ON road_segments USING GIST(geom);
CREATE INDEX idx_road_segments_way    ON road_segments(source_way_id);
CREATE INDEX idx_road_segments_nodes  ON road_segments(from_node_id, to_node_id);

-- ETL 매칭 결과 추적
CREATE TABLE segment_attribute_match_result (
    id              BIGSERIAL PRIMARY KEY,
    edge_id         BIGINT NOT NULL REFERENCES road_segments(edge_id),
    attribute       VARCHAR(50) NOT NULL,
    matched         BOOLEAN NOT NULL,
    confidence      VARCHAR(10),            -- HIGH / MEDIUM / LOW / NONE
    distance_meter  NUMERIC(8,2),
    source_dataset  VARCHAR(100),
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_match_result_edge ON segment_attribute_match_result(edge_id);

-- ─── 대중교통 참조 ──────────────────────────────────────────

CREATE TABLE low_floor_bus_routes (
    route_id       VARCHAR(20) PRIMARY KEY,
    route_no       VARCHAR(20) NOT NULL,
    has_low_floor  BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE subway_station_elevators (
    elevator_id   BIGSERIAL PRIMARY KEY,
    station_id    VARCHAR(20) NOT NULL,
    station_name  VARCHAR(100) NOT NULL,
    line_name     VARCHAR(50) NOT NULL,
    entrance_no   VARCHAR(10),
    point         GEOMETRY(POINT, 4326) NOT NULL
);
CREATE INDEX idx_subway_elev_station ON subway_station_elevators(station_id);
CREATE INDEX idx_subway_elev_point   ON subway_station_elevators USING GIST(point);

-- ─── 사용자 도메인 ──────────────────────────────────────────

CREATE TYPE disability_type_t AS ENUM ('VISUAL', 'MOBILITY');
CREATE TYPE route_option_t    AS ENUM ('SAFE_WALK', 'FAST_WALK', 'ACCESSIBLE_TRANSIT');

-- (ERD 기준 나머지 테이블 — users, bookmarks, favorite_routes 등은 별도 마이그레이션)
```

**주의:** `disability_type`은 `VISUAL / MOBILITY`만. POC의 `WHEELCHAIR`는 사용하지 않는다.

---

## 5. OSM way 필터

```python
# etl/build_network.py

INCLUDE_HIGHWAY = frozenset({
    "footway", "path", "pedestrian", "living_street",
    "residential", "service", "unclassified", "crossing", "steps", "elevator"
})
EXCLUDE_HIGHWAY = frozenset({"motorway", "trunk"})

def is_walkable(tags: dict) -> bool:
    if tags.get("foot") == "no" or tags.get("access") == "private":
        return False
    if tags.get("highway") in EXCLUDE_HIGHWAY:
        return False
    return (
        tags.get("highway") in INCLUDE_HIGHWAY
        or tags.get("foot") in {"yes", "designated"}
        or tags.get("sidewalk") in {"left", "right", "both", "yes"}
    )
```

---

## 6. Anchor Node 식별 + Way 분해

```python
import osmium

class WayCollector(osmium.SimpleHandler):
    """Phase 1: 보행 가능 way 수집, node → way 역인덱스 구성"""
    def __init__(self):
        super().__init__()
        self.walkable_ways: dict[int, list[int]] = {}  # way_id → [node_id, ...]
        self.node_way_count: dict[int, int] = {}        # node_id → 등장 way 수
        self.osm_tags: dict[int, dict] = {}             # way_id → tags

    def way(self, w):
        tags = {t.k: t.v for t in w.tags}
        if not is_walkable(tags):
            return
        nodes = [n.ref for n in w.nodes]
        self.walkable_ways[w.id] = nodes
        self.osm_tags[w.id] = tags
        for node_id in nodes:
            self.node_way_count[node_id] = self.node_way_count.get(node_id, 0) + 1


def identify_anchors(collector: WayCollector, crossing_nodes: set[int]) -> set[int]:
    """anchor node = 교차점 | way 시작/끝 | crossing/barrier node"""
    anchors = set()
    for way_id, nodes in collector.walkable_ways.items():
        anchors.add(nodes[0])
        anchors.add(nodes[-1])
    for node_id, count in collector.node_way_count.items():
        if count >= 2:
            anchors.add(node_id)
    anchors |= crossing_nodes
    return anchors


def split_way_to_segments(way_id: int, nodes: list[int], anchors: set[int]):
    """anchor node 사이로 way 분해 → segment list"""
    segments = []
    current_start = nodes[0]
    ordinal = 0
    for i in range(1, len(nodes)):
        if nodes[i] in anchors:
            segments.append({
                "way_id": way_id,
                "from_node": current_start,
                "to_node": nodes[i],
                "ordinal": ordinal,
                "intermediate": nodes[max(0, i-1):i+1]
            })
            current_start = nodes[i]
            ordinal += 1
    return segments
```

---

## 7. Bulk Insert

```python
from psycopg2.extras import execute_values

BATCH_SIZE = 5_000

def insert_road_nodes(cur, nodes: list[dict]):
    execute_values(cur,
        """INSERT INTO road_nodes (osm_node_id, point)
           VALUES %s
           ON CONFLICT (osm_node_id) DO NOTHING""",
        [(n["osm_node_id"], f"SRID=4326;POINT({n['lng']} {n['lat']})")
         for n in nodes],
        page_size=BATCH_SIZE
    )

def insert_road_segments(cur, segments: list[dict]):
    execute_values(cur,
        """INSERT INTO road_segments
           (from_node_id, to_node_id, geom, length_meter,
            source_way_id, source_osm_from_node_id, source_osm_to_node_id, segment_ordinal)
           VALUES %s
           ON CONFLICT (source_way_id, source_osm_from_node_id, source_osm_to_node_id) DO NOTHING""",
        [(s["from_node_id"], s["to_node_id"], s["geom_wkt"], s["length_m"],
          s["way_id"], s["from_osm"], s["to_osm"], s["ordinal"])
         for s in segments],
        page_size=BATCH_SIZE
    )
```

**per-row INSERT 금지.** 전체 bulk → 트랜잭션 단위 commit.

---

## 8. OSM 구조 정보 반영 (주의)

`confirm_blueprint.md` 기준으로 `highway=steps`, `highway=elevator` 같은 구조 태그는
참고 가능하다. 하지만 **svc_plan_01 기본 적재 파이프라인은 속성 컬럼을 모두 기본값으로 유지한다.**
즉, base load 단계에서는 `stairs_state`, `elevator_state`도 `UNKNOWN` 그대로 적재한다.

아래 helper는 후속 실험 또는 별도 분석용으로만 남기고, 기본 실행 경로에서는 적용하지 않는다.

```python
def apply_osm_structural_hints(tags: dict) -> dict:
    """공공데이터 ETL 이전 임시 초기값 — ETL이 우선"""
    hints = {}
    if tags.get("highway") == "steps":
        hints["stairs_state"] = "YES"
    if tags.get("highway") == "elevator":
        hints["elevator_state"] = "YES"
    return hints
```

---

## 9. 멱등성 보장

```python
# 재실행 시 중복 없음 보장
# road_nodes: UNIQUE(osm_node_id) → ON CONFLICT DO NOTHING
# road_segments: UNIQUE(source_way_id, from, to) → ON CONFLICT DO NOTHING
# 초기 구축: TRUNCATE road_segments, road_nodes CASCADE 후 재적재
```

---

## 10. 실행 방법

```bash
# etl/ 디렉토리에서 실행
cd ieumgil-svc
source etl/.venv/bin/activate

# PostgreSQL이 localhost:5432에서 실행 중이어야 함
# docker compose up postgresql -d 후 실행

python etl/build_network.py \
  --pbf etl/data/raw/busan.osm.pbf \
  --truncate   # 재실행 시 기존 데이터 삭제 후 재적재
```

---

## 11. 완료 기준

검증 쿼리:
```sql
-- 1. 적재 건수 확인
SELECT
  (SELECT COUNT(*) FROM road_nodes)    AS node_count,
  (SELECT COUNT(*) FROM road_segments) AS segment_count;
-- 기대: road_nodes 수십만 건, road_segments 수십만~수백만 건

-- 2. 속성 컬럼 기본값 확인 (전부 UNKNOWN이어야 함)
SELECT
  COUNT(*) FILTER (WHERE braille_block_state != 'UNKNOWN') AS non_unknown_braille,
  COUNT(*) FILTER (WHERE stairs_state != 'UNKNOWN')        AS non_unknown_stairs,
  COUNT(*) FILTER (WHERE avg_slope_percent IS NOT NULL)    AS has_slope
FROM road_segments;
-- 기대: 모두 0 (ETL 이전 상태)

-- 3. Geometry 유효성
SELECT COUNT(*) FROM road_segments WHERE NOT ST_IsValid(geom);
-- 기대: 0

-- 4. UNIQUE 제약 확인
SELECT source_way_id, source_osm_from_node_id, source_osm_to_node_id, COUNT(*)
FROM road_segments
GROUP BY 1,2,3
HAVING COUNT(*) > 1;
-- 기대: 0건
```

- [ ] `road_nodes`, `road_segments` 적재 완료 (부산 전체)
- [ ] 모든 속성 컬럼 기본값 `UNKNOWN` (avg_slope_percent = NULL)
- [ ] `UNIQUE` 제약 위반 없음 (위 쿼리 0건)
- [ ] `ST_IsValid(geom)` 전수 통과 (위 쿼리 0건)
- [ ] 재실행 시 중복 증가 없음 (멱등성 — `--truncate` 없이 재실행 후 건수 동일)
