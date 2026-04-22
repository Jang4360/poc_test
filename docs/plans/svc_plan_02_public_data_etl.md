# svc_plan_02: 공공데이터 ETL (접근성 속성 매칭)

> **작성일:** 2026-04-18 (POC 분석 반영 업데이트)  
> **목적:** road_segments의 9개 접근성 속성 컬럼을 공공데이터로 채운다  
> **선행 조건:** svc_plan_01 완료 (road_segments 전체 적재, 속성 전부 UNKNOWN)  
> **후행 단계:** svc_plan_03 (GH import)

---

## 1. POC 대비 변경 이유

POC에는 ETL 스크립트가 없었다. `etl/data/raw/busan.osm.pbf`만 존재했고,
공공데이터 매칭은 전혀 구현되지 않아 모든 속성이 UNKNOWN → Boolean PASS = true → 4개 프로필 구분 불가.

신규 레포에서는 `avg_slope_percent`를 포함한 9개 속성을 실제 공공데이터로 채워야
GH custom model이 프로필별로 다른 경로를 생성한다.

---

## 2. 공공데이터 파일 준비

```
etl/data/public/
├── dem/
│   └── busan_dem.tif          # 국토지리정보원 수치표고모델 5m
│                               # 다운로드: https://map.ngii.go.kr → 수치표고모델
├── width/
│   └── busan_width.shp        # 보도 폭원 GIS
│                               # 출처: 국가공간정보포털 (nsdi.go.kr) → 보도 폭원
├── surface/
│   └── busan_surface.shp      # 도로 포장 상태 GIS
│                               # 출처: 부산광역시 열린데이터 / 국가공간정보포털
├── stairs.geojson              # 계단 위치 현황
├── curb_ramp.geojson           # 연석경사로
├── elevator.geojson            # 엘리베이터 (보행로 연결)
├── braille_block.geojson       # 점자블록 설치 현황
├── audio_signal.geojson        # 음향신호기 위치
└── crossing.geojson            # 횡단보도 GIS
```

> **공공데이터 출처 요약:**
> - 수치표고모델: 국토지리정보원 국가공간정보포털 (ngii.go.kr) → 무료
> - 나머지 6종: 공공데이터포털 (data.go.kr) → "부산 교통약자 편의시설" 검색
> - 부산광역시 열린데이터광장 (data.busan.go.kr) 병행 검색

GeoJSON이 아닌 SHP/CSV 형태인 경우 `geopandas`로 변환:
```bash
python -c "
import geopandas as gpd
gdf = gpd.read_file('etl/data/public/stairs.shp')
gdf.to_crs('EPSG:4326').to_file('etl/data/public/stairs.geojson', driver='GeoJSON')
"
```

## 3. 기술 스택

- **언어:** Python 3.11+ (svc_plan_00 venv 사용)
- **라이브러리:** `requirements.txt`에 모두 포함 (geopandas, shapely, rasterio, psycopg2, pyproj)
- **DB 연결:** `etl/db.py` 공통 유틸 사용 (svc_plan_00 작성)

---

## 3. 매칭 신뢰도 기준 (전 속성 공통)

| 거리 | 신뢰도 | 처리 |
|---|---|---|
| ≤ 15m | HIGH | 반영 |
| 15~30m | MEDIUM | 반영 + match_result LOW_CONFIDENCE 기록 |
| 30~50m | LOW | 무시, UNKNOWN 유지 |
| > 50m 또는 없음 | NONE | UNKNOWN 유지 |

**중요:** 공공데이터 커버리지가 100%가 아니므로, 매칭 안 된 구간은 절대 NO로 처리하지 않는다.
데이터셋이 해당 구역을 커버하는데 없는 경우만 NO 처리.
coverage 메타데이터가 없으면 해당 판단은 유보하고 `UNKNOWN`을 유지한다.

---

## 4. 속성별 ETL 명세

### 4-1. avg_slope_percent (가장 중요)

**데이터:** 국토지리정보원 수치표고모델(DEM) 5m 격자  
**출처:** 국가공간정보포털 → 수치표고모델  
**형식:** GeoTIFF (.tif)

```python
# etl/etl_slope.py
import rasterio
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString

def sample_dem_along_line(dem_path: str, geom_wgs84: LineString, n_samples: int = 10) -> float:
    """
    segment 선형을 따라 n_samples 개 지점에서 DEM 값 샘플링.
    시작점~끝점 고도 차이 / 수평 거리로 경사도(%) 계산.
    절댓값 반환 (양수).
    """
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

    with rasterio.open(dem_path) as dem:
        coords_wgs = list(geom_wgs84.coords)
        # 시작점 고도
        start_xy = transformer.transform(coords_wgs[0][0], coords_wgs[0][1])
        end_xy   = transformer.transform(coords_wgs[-1][0], coords_wgs[-1][1])

        start_elev = list(dem.sample([start_xy]))[0][0]
        end_elev   = list(dem.sample([end_xy]))[0][0]

        # 수평 거리 (투영 좌표계에서 미터)
        horizontal_m = ((end_xy[0]-start_xy[0])**2 + (end_xy[1]-start_xy[1])**2) ** 0.5
        if horizontal_m < 1.0:
            return 0.0

        slope_pct = abs(end_elev - start_elev) / horizontal_m * 100
        return round(min(slope_pct, 99.99), 2)  # 상한 99.99 (이상값 방어)


def run_slope_etl(conn, dem_path: str, batch_size: int = 500):
    cur = conn.cursor()
    # avg_slope_percent가 NULL인 segment만 처리
    cur.execute("SELECT edge_id, ST_AsText(geom) FROM road_segments WHERE avg_slope_percent IS NULL")
    rows = cur.fetchall()

    updates = []
    for edge_id, geom_wkt in rows:
        geom = wkt.loads(geom_wkt)
        slope = sample_dem_along_line(dem_path, geom)
        updates.append((slope, edge_id))

        if len(updates) >= batch_size:
            cur.executemany("UPDATE road_segments SET avg_slope_percent = %s WHERE edge_id = %s", updates)
            conn.commit()
            updates = []

    if updates:
        cur.executemany("UPDATE road_segments SET avg_slope_percent = %s WHERE edge_id = %s", updates)
        conn.commit()
    print(f"경사도 계산 완료: {len(rows)}개 segment")
```

**검증:**
```sql
-- 경사도 분포 확인 (부산 기준 3% 초과가 40~60% 예상)
SELECT
  COUNT(*) FILTER (WHERE avg_slope_percent <= 3)  AS flat,
  COUNT(*) FILTER (WHERE avg_slope_percent <= 5)  AS gentle,
  COUNT(*) FILTER (WHERE avg_slope_percent <= 8)  AS moderate,
  COUNT(*) FILTER (WHERE avg_slope_percent > 8)   AS steep,
  COUNT(*) FILTER (WHERE avg_slope_percent IS NULL) AS unmeasured
FROM road_segments;
```

---

### 4-2. width_meter / width_state

**데이터:** 부산광역시 보도 폭원 GIS (SHP)  
**매칭:** segment geometry overlap 기반

```python
import geopandas as gpd
from shapely.ops import unary_union

def classify_width_state(width_m: float) -> str:
    if width_m >= 1.5:   return "ADEQUATE_150"
    if width_m >= 1.2:   return "ADEQUATE_120"
    return "NARROW"

def run_width_etl(conn, shp_path: str):
    width_gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")

    cur = conn.cursor()
    cur.execute("SELECT edge_id, ST_AsText(geom) FROM road_segments")

    updates = []
    for edge_id, geom_wkt in cur.fetchall():
        seg_geom = wkt.loads(geom_wkt)
        seg_gs = gpd.GeoSeries([seg_geom], crs="EPSG:4326").to_crs("EPSG:5179")

        # 15m 이내 폭원 데이터 찾기
        seg_buf = seg_gs.buffer(15).iloc[0]
        candidates = width_gdf[width_gdf.to_crs("EPSG:5179").intersects(seg_buf)]

        if candidates.empty:
            continue  # UNKNOWN 유지

        nearest = candidates.iloc[0]
        width_m = float(nearest["width_m"])  # 컬럼명은 데이터셋에 맞게 조정
        updates.append((width_m, classify_width_state(width_m), edge_id))

    cur.executemany(
        "UPDATE road_segments SET width_meter = %s, width_state = %s WHERE edge_id = %s",
        updates
    )
    conn.commit()
```

---

### 4-3. surface_state

**데이터:** 부산광역시 도로 포장 상태 GIS (SHP/GeoJSON)  
**매칭:** segment geometry overlap 기반

```python
def classify_surface_state(raw: str) -> str:
    raw = (raw or "").strip().lower()
    if raw in {"paved", "asphalt", "concrete", "포장", "아스팔트", "콘크리트"}:
        return "PAVED"
    if raw in {"gravel", "자갈"}:
        return "GRAVEL"
    if raw in {"unpaved", "dirt", "soil", "비포장", "흙"}:
        return "UNPAVED"
    if raw:
        return "OTHER"
    return "UNKNOWN"
```

`surface_state`는 `wheelchair_safe`, `wheelchair_fast` 프로필의 HARD EXCLUDE 조건에 직접 연결되므로
`UNKNOWN`과 `UNPAVED/GRAVEL`을 혼동하지 않는다.

---

### 4-4. stairs_state / curb_ramp_state / elevator_state

**데이터:** 한국장애인개발원 보행환경 DB / 부산광역시 교통약자 편의시설 (POINT)  
**매칭:** segment endpoint 15m 반경 내 POINT 존재 여부

```python
def match_point_features(conn, feature_table: str, column: str, radius_m: float = 15):
    """
    from_node 또는 to_node 좌표 반경 radius_m 내 feature POINT 존재 시 → YES
    데이터셋 커버리지 내 없으면 → NO
    커버리지 밖 → UNKNOWN 유지
    """
    # PostGIS 공간 쿼리로 처리 (Python 루프 최소화)
    query = f"""
        UPDATE road_segments rs
        SET {column} = 'YES'
        WHERE EXISTS (
            SELECT 1 FROM {feature_table} f
            JOIN road_nodes rn_from ON rn_from.vertex_id = rs.from_node_id
            WHERE ST_DWithin(rn_from.point::geography, f.geom::geography, {radius_m})
        )
        OR EXISTS (
            SELECT 1 FROM {feature_table} f
            JOIN road_nodes rn_to ON rn_to.vertex_id = rs.to_node_id
            WHERE ST_DWithin(rn_to.point::geography, f.geom::geography, {radius_m})
        )
    """
    # PostGIS 처리 — Python 루프 없이 DB에서 한 번에 처리
    with conn.cursor() as cur:
        cur.execute(query)
    conn.commit()
```

**주의:** 데이터셋 적재 완료 구역 내에서만 NO 처리. 미적재 구역은 UNKNOWN 유지.
coverage 폴리곤이 있으면 `--coverage path/to/coverage.geojson`로 함께 넘기고,
coverage 정보가 없으면 보수적으로 `UNKNOWN` 유지가 기본 동작이다.

---

### 4-5. braille_block_state

**데이터:** 부산광역시 점자블록 설치 현황 (POINT / LINESTRING)  
**매칭:** segment geometry buffer 10m 내 존재 여부

```sql
-- PostGIS 직접 UPDATE (Python 루프 불필요)
UPDATE road_segments rs
SET braille_block_state = 'YES'
FROM braille_block_staging bb
WHERE ST_DWithin(rs.geom::geography, bb.geom::geography, 10);
```

---

### 4-6. audio_signal_state

**데이터:** 부산광역시 / 도로교통공단 음향신호기 위치 (POINT)  
**매칭:** segment endpoint 15m 내  
**적용 대상:** crossing 구간 우선 (`crossing_state != 'NO'`)
coverage 정보가 없으면 `NO`보다 `UNKNOWN` 유지가 우선이다.

---

### 4-7. crossing_state

**데이터:** 경찰청 / 부산광역시 횡단보도 GIS (POINT)  
**변환:**

| 원천 | crossing_state |
|---|---|
| 신호등 있음 | `TRAFFIC_SIGNALS` |
| 신호등 없음, 횡단보도 있음 | `UNCONTROLLED` |
| 노면 표시만 | `UNMARKED` |
| 없음 확인 | `NO` |
| 미적재 | `UNKNOWN` |

---

## 5. match_result 기록

```python
def reset_attribute_state(cur, attribute: str):
    cur.execute(
        "DELETE FROM segment_attribute_match_result WHERE attribute = %s",
        (attribute,),
    )


def record_match(cur, edge_id: int, attribute: str, matched: bool,
                 confidence: str, distance_m: float, source: str):
    cur.execute("""
        INSERT INTO segment_attribute_match_result
          (edge_id, attribute, matched, confidence, distance_meter, source_dataset)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (edge_id, attribute, matched, confidence, distance_m, source))
```

**재실행 원칙:** 각 속성 ETL 시작 시 해당 속성 컬럼을 기본값으로 되돌리고,
동일 `attribute`의 `segment_attribute_match_result`를 먼저 삭제한 뒤 다시 적재한다.
`ON CONFLICT DO NOTHING` 방식으로는 멱등성이 보장되지 않는다.

---

## 6. 실행 순서

```bash
# ieumgil-svc/ 루트에서 실행
source etl/.venv/bin/activate

# 1. DEM 경사도 (가장 중요 — GH custom model에 직접 영향)
python etl/etl_slope.py --dem etl/data/public/dem/busan_dem.tif

# 2. 보도 폭원 (width_state → wheelchair_safe HARD EXCLUDE 기준)
python etl/etl_accessibility.py --type width --shp etl/data/public/width/busan_width.shp

# 3. 포장 상태 (wheelchair 계열 HARD EXCLUDE 기준)
python etl/etl_accessibility.py --type surface --shp etl/data/public/surface/busan_surface.shp

# 4. 계단/경사로/엘리베이터 (접근성 핵심 속성)
python etl/etl_accessibility.py --type stairs    --geojson etl/data/public/stairs.geojson
python etl/etl_accessibility.py --type curb_ramp --geojson etl/data/public/curb_ramp.geojson
python etl/etl_accessibility.py --type elevator  --geojson etl/data/public/elevator.geojson

# 5. 점자블록 (시각장애 핵심 속성)
python etl/etl_accessibility.py --type braille_block --geojson etl/data/public/braille_block.geojson

# 6. 음향신호기
python etl/etl_accessibility.py --type audio_signal --geojson etl/data/public/audio_signal.geojson

# 7. 횡단보도
python etl/etl_accessibility.py --type crossing --geojson etl/data/public/crossing.geojson

# 8. 커버리지 리포트 (완료 기준 검증)
python etl/coverage_report.py
```

**실행 전 체크:**
```bash
# DB 연결 확인
python -c "from etl.db import get_conn; conn = get_conn(); print('DB 연결 OK'); conn.close()"

# road_segments가 있는지 확인 (svc_plan_01 완료 필수)
psql -h localhost -U ieumgil -d ieumgil -c "SELECT COUNT(*) FROM road_segments;"
```

---

## 7. 커버리지 리포트 (완료 기준 검증)

```sql
SELECT
    attribute,
    COUNT(*) FILTER (WHERE matched) AS matched_cnt,
    COUNT(*) FILTER (WHERE NOT matched) AS unmatched_cnt,
    ROUND(100.0 * COUNT(*) FILTER (WHERE matched) / COUNT(*), 1) AS match_rate_pct
FROM segment_attribute_match_result
GROUP BY attribute
ORDER BY attribute;
```

---

## 8. 완료 기준

- [ ] `avg_slope_percent`: 전체 segment의 85% 이상 값 존재 (NULL 아님)
- [ ] `width_state`: 데이터셋 커버리지 내 매칭 완료
- [ ] `surface_state`: 데이터셋 커버리지 내 매칭 완료
- [ ] `stairs_state`, `curb_ramp_state`: 데이터셋 커버리지 내 매칭 완료
- [ ] `braille_block_state`: 데이터셋 커버리지 내 매칭 완료
- [ ] `segment_attribute_match_result` 기록 완료
- [ ] 커버리지 리포트 출력 (속성별 매칭률)
- [ ] ETL 재실행 시 결과 동일 (멱등성)
