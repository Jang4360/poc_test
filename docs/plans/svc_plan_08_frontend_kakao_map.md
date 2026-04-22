# svc_plan_08: 프론트엔드 (React + Kakao Map API)

> **작성일:** 2026-04-18  
> **목적:** 카카오맵 기반 경로 탐색 UI 구현 — 장애 유형 선택, 경로 옵션 표시, 지도 렌더링  
> **선행 조건:** svc_plan_04 완료 (백엔드 `/routes/search` 동작)  
> **후행 단계:** svc_plan_07 완료 시 docker compose up으로 전체 통합

---

## 1. 기술 스택

| 항목 | 선택 | 이유 |
|---|---|---|
| 프레임워크 | React 18 + Vite | 경량, HMR 빠름, svc_plan_00 VITE_ 환경변수와 일치 |
| 언어 | TypeScript | 백엔드 API DTO와 타입 일치 확인 가능 |
| 지도 | Kakao Maps JavaScript SDK v3 | 국내 POI 최다, 부산 도보 경로 표시 적합 |
| HTTP 클라이언트 | axios | 인터셉터로 JWT 자동 주입 |
| 상태관리 | React useState / useReducer (최소) | 규모 작음 — Redux 불필요 |
| 스타일 | Tailwind CSS | 빠른 UI 구성 |

---

## 2. 프로젝트 구조

```
frontend/
├── Dockerfile
├── nginx.conf
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── .env.local                        # 로컬 개발용 (git 제외)
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   ├── client.ts                 # axios 인스턴스 + JWT 인터셉터
    │   └── routes.ts                 # /routes/search 호출
    ├── components/
    │   ├── SearchForm.tsx            # 출발지/목적지 입력 + 장애 유형 선택
    │   ├── RouteOptionTabs.tsx       # SAFE / SHORTEST / PUBLIC_TRANSPORT 탭
    │   ├── MapView.tsx               # 카카오맵 렌더링
    │   ├── RoutePolyline.tsx         # 경로 선 그리기
    │   ├── MarkerLayer.tsx           # 정류장/역 마커
    │   └── AccessibilityBadge.tsx    # 계단/경사/점자블록 상태 아이콘
    ├── hooks/
    │   ├── useKakaoMap.ts            # 카카오맵 SDK 로드 + 지도 인스턴스
    │   └── useRouteSearch.ts         # 경로탐색 API 호출 + 상태 관리
    └── types/
        └── api.ts                    # 백엔드 응답 타입 정의
```

---

## 3. Kakao Maps API 키 발급

```
1. https://developers.kakao.com → 로그인 → 내 애플리케이션 → 애플리케이션 추가
2. 플랫폼 → Web → 사이트 도메인 등록
   - 로컬 개발: http://localhost:3000
   - 운영:      https://your-domain.com
3. 앱 키 → "JavaScript 키" 복사
4. .env.local에 추가:
   VITE_KAKAO_JS_KEY=발급받은_키
5. docker-compose .env에도 추가:
   KAKAO_JS_KEY=발급받은_키
```

> **주의:** Kakao Maps SDK는 도메인 기반 인증. localhost:3000이 등록되지 않으면 지도가 로드되지 않음.

---

## 4. 환경변수

```bash
# frontend/.env.local (git 제외 — .gitignore에 추가)
VITE_API_BASE_URL=http://localhost:8080
VITE_KAKAO_JS_KEY=your_kakao_js_key_here

# .gitignore
frontend/.env.local
frontend/.env
```

```typescript
// src/types/env.d.ts
/// <reference types="vite/client" />
interface ImportMetaEnv {
    readonly VITE_API_BASE_URL: string;
    readonly VITE_KAKAO_JS_KEY: string;
}
```

---

## 5. 카카오맵 SDK 로드

```html
<!-- index.html — SDK는 script 태그로 로드 (npm 패키지 없음) -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>부산이음길</title>
</head>
<body>
  <div id="root"></div>
  <!-- Kakao Maps SDK: appkey는 빌드 시 환경변수로 주입 -->
  <script type="text/javascript"
    src="//dapi.kakao.com/v2/maps/sdk.js?appkey=%VITE_KAKAO_JS_KEY%&libraries=services">
  </script>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

```typescript
// vite.config.ts — index.html의 %VITE_KAKAO_JS_KEY% 치환
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    return {
        plugins: [react()],
        define: {
            // index.html에서 %VITE_KAKAO_JS_KEY% 치환용
        },
        server: {
            proxy: {
                '/routes': { target: env.VITE_API_BASE_URL, changeOrigin: true }
            }
        }
    };
});
```

```typescript
// src/hooks/useKakaoMap.ts
declare global {
    interface Window {
        kakao: any;
    }
}

export function useKakaoMap(containerId: string) {
    const [map, setMap] = useState<any>(null);

    useEffect(() => {
        // SDK가 비동기 로드될 수 있으므로 kakao.maps.load() 사용
        window.kakao.maps.load(() => {
            const container = document.getElementById(containerId);
            const options = {
                center: new window.kakao.maps.LatLng(35.1796, 129.0756), // 부산 시청
                level: 5,
            };
            setMap(new window.kakao.maps.Map(container, options));
        });
    }, [containerId]);

    return map;
}
```

---

## 6. 백엔드 API 타입 정의

```typescript
// src/types/api.ts
export type DisabilityType = 'VISUAL' | 'MOBILITY';
export type RouteOption    = 'SAFE' | 'SHORTEST' | 'PUBLIC_TRANSPORT';

export interface GeoPoint {
    lat: number;
    lng: number;
}

export interface RouteSearchRequest {
    disabilityType: DisabilityType;
    startPoint: GeoPoint;
    endPoint: GeoPoint;
    routeOption?: RouteOption;
}

export interface SegmentDto {
    sequence: number;
    geometry: string;          // WKT LINESTRING
    distanceMeter: number;
    stairsState: 'YES' | 'NO' | 'UNKNOWN';
    brailleBlockState: 'YES' | 'NO' | 'UNKNOWN';
    audioSignalState: 'YES' | 'NO' | 'UNKNOWN';
    curbRampState: 'YES' | 'NO' | 'UNKNOWN';
    crossingState: string;
    surfaceState: string;
    widthState: string;
    avgSlopePercent: number | null;
    guidanceMessage: string;
}

export interface RouteOptionResult {
    option: RouteOption;
    available: boolean;
    reason?: string;           // available=false 시
    totalDistanceMeter?: number;
    totalTimeMinute?: number;
    segments?: SegmentDto[];
    legs?: LegDto[];           // PUBLIC_TRANSPORT
    markers?: MarkerDto[];     // PUBLIC_TRANSPORT 정류장/역 마커
}

export interface LegDto {
    sequence: number;
    type: 'WALK' | 'BUS' | 'SUBWAY';
    durationMinute?: number;
    distanceMeter?: number;
    routeNo?: string;          // 버스 노선번호
    lineName?: string;         // 지하철 호선명
    boardName?: string;        // 탑승 정류장/역명
    alightName?: string;       // 하차 정류장/역명
    isLowFloor?: boolean;
    geometry?: string;         // Walk leg WKT
}

export interface MarkerDto {
    type: 'BUS_BOARD' | 'BUS_ALIGHT' | 'SUBWAY_BOARD' | 'SUBWAY_ALIGHT';
    name: string;
    lat: number;
    lng: number;
}

export interface RouteSearchResponse {
    disabilityType: DisabilityType;
    startPoint: GeoPoint;
    endPoint: GeoPoint;
    options: RouteOptionResult[];
}
```

---

## 7. API 클라이언트

```typescript
// src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL,
    timeout: 20_000,
});

// JWT 인터셉터 (운영용 — 로컬은 Authorization 헤더 없어도 통과)
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default apiClient;
```

```typescript
// src/api/routes.ts
import apiClient from './client';
import type { RouteSearchRequest, RouteSearchResponse } from '../types/api';

export async function searchRoutes(req: RouteSearchRequest): Promise<RouteSearchResponse> {
    const { data } = await apiClient.post<{ data: RouteSearchResponse }>(
        '/routes/search', req
    );
    return data.data;
}
```

---

## 8. 핵심 컴포넌트

### SearchForm.tsx — 출발지/목적지 + 장애 유형 선택

```tsx
export function SearchForm({ onSearch }: { onSearch: (req: RouteSearchRequest) => void }) {
    const [disability, setDisability] = useState<DisabilityType>('MOBILITY');
    const [start, setStart] = useState<GeoPoint | null>(null);
    const [end, setEnd]     = useState<GeoPoint | null>(null);

    // 카카오 장소 검색으로 좌표 조회
    const searchPlace = (query: string, setter: (p: GeoPoint) => void) => {
        const ps = new window.kakao.maps.services.Places();
        ps.keywordSearch(query, (results: any[], status: string) => {
            if (status === window.kakao.maps.services.Status.OK) {
                setter({ lat: parseFloat(results[0].y), lng: parseFloat(results[0].x) });
            }
        });
    };

    return (
        <div className="p-4 bg-white rounded-lg shadow">
            <div className="flex gap-2 mb-3">
                <button
                    className={`flex-1 py-2 rounded ${disability === 'MOBILITY' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
                    onClick={() => setDisability('MOBILITY')}
                >
                    보행 약자
                </button>
                <button
                    className={`flex-1 py-2 rounded ${disability === 'VISUAL' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}
                    onClick={() => setDisability('VISUAL')}
                >
                    시각 장애
                </button>
            </div>

            <input
                className="w-full border rounded p-2 mb-2"
                placeholder="출발지 입력"
                onBlur={(e) => searchPlace(e.target.value, setStart)}
            />
            <input
                className="w-full border rounded p-2 mb-3"
                placeholder="목적지 입력"
                onBlur={(e) => searchPlace(e.target.value, setEnd)}
            />

            <button
                className="w-full bg-blue-600 text-white py-2 rounded disabled:opacity-40"
                disabled={!start || !end}
                onClick={() => start && end && onSearch({
                    disabilityType: disability,
                    startPoint: start,
                    endPoint: end
                })}
            >
                경로 탐색
            </button>
        </div>
    );
}
```

### MapView.tsx — 지도 + 경로/마커 렌더링

```tsx
export function MapView({
    result,
    activeOption
}: {
    result: RouteSearchResponse | null;
    activeOption: RouteOption;
}) {
    const map = useKakaoMap('kakao-map-container');
    const markersRef = useRef<any[]>([]);
    const polylinesRef = useRef<any[]>([]);

    useEffect(() => {
        if (!map || !result) return;

        // 이전 오버레이 정리
        [...markersRef.current, ...polylinesRef.current].forEach(o => o.setMap(null));
        markersRef.current = [];
        polylinesRef.current = [];

        const optResult = result.options.find(o => o.option === activeOption);
        if (!optResult?.available) return;

        // 도보 경로: segments geometry (WKT → LatLng)
        if (optResult.segments) {
            optResult.segments.forEach(seg => {
                const path = parseWktLinestring(seg.geometry);
                const color = getSegmentColor(seg);  // 계단/경사/점자 상태별 색상
                const polyline = new window.kakao.maps.Polyline({
                    path, strokeWeight: 4, strokeColor: color, strokeOpacity: 0.9
                });
                polyline.setMap(map);
                polylinesRef.current.push(polyline);
            });
        }

        // 대중교통: 마커 + walk leg 경로
        if (optResult.markers) {
            optResult.markers.forEach(m => {
                const marker = new window.kakao.maps.Marker({
                    position: new window.kakao.maps.LatLng(m.lat, m.lng),
                    title: m.name,
                    image: getMarkerImage(m.type)
                });
                marker.setMap(map);
                markersRef.current.push(marker);
            });
        }

        // 지도 범위 맞추기
        const bounds = new window.kakao.maps.LatLngBounds();
        [...markersRef.current].forEach(m => bounds.extend(m.getPosition()));
        if (!bounds.isEmpty()) map.setBounds(bounds);

    }, [map, result, activeOption]);

    return <div id="kakao-map-container" style={{ width: '100%', height: '500px' }} />;
}

// WKT LINESTRING(...) → kakao.maps.LatLng[]
function parseWktLinestring(wkt: string): any[] {
    const coords = wkt.replace('LINESTRING(', '').replace(')', '').split(',');
    return coords.map(pair => {
        const [lng, lat] = pair.trim().split(' ').map(Number);
        return new window.kakao.maps.LatLng(lat, lng);
    });
}

// 접근성 상태별 경로 색상
function getSegmentColor(seg: SegmentDto): string {
    if (seg.stairsState === 'YES') return '#ef4444';     // 빨강 — 계단
    if (seg.avgSlopePercent && seg.avgSlopePercent > 5) return '#f97316'; // 주황 — 급경사
    if (seg.brailleBlockState === 'YES') return '#3b82f6'; // 파랑 — 점자블록
    return '#22c55e';                                       // 녹색 — 기본
}
```

### RouteOptionTabs.tsx — 탭 + 요약 정보

```tsx
export function RouteOptionTabs({
    options,
    activeOption,
    onSelect
}: {
    options: RouteOptionResult[];
    activeOption: RouteOption;
    onSelect: (opt: RouteOption) => void;
}) {
    const LABELS: Record<RouteOption, string> = {
        SAFE:               '안전 도보',
        SHORTEST:           '최단 도보',
        PUBLIC_TRANSPORT:   '대중교통',
    };

    return (
        <div className="flex gap-1 mb-4">
            {options.map(opt => (
                <button
                    key={opt.option}
                    disabled={!opt.available}
                    className={`flex-1 py-2 px-3 rounded text-sm ${
                        activeOption === opt.option
                            ? 'bg-blue-600 text-white'
                            : opt.available
                                ? 'bg-gray-100 hover:bg-gray-200'
                                : 'bg-gray-50 text-gray-400 line-through'
                    }`}
                    onClick={() => onSelect(opt.option)}
                >
                    <div>{LABELS[opt.option]}</div>
                    {opt.available ? (
                        <div className="text-xs mt-0.5">
                            {opt.totalTimeMinute}분 · {Math.round((opt.totalDistanceMeter ?? 0) / 10) / 100}km
                        </div>
                    ) : (
                        <div className="text-xs mt-0.5">{opt.reason}</div>
                    )}
                </button>
            ))}
        </div>
    );
}
```

### AccessibilityBadge.tsx — 접근성 상태 아이콘

```tsx
export function AccessibilityBadge({ segment }: { segment: SegmentDto }) {
    return (
        <div className="flex gap-1 flex-wrap text-xs">
            {segment.stairsState === 'YES' &&
                <span className="bg-red-100 text-red-700 px-1 rounded">계단</span>}
            {segment.brailleBlockState === 'YES' &&
                <span className="bg-blue-100 text-blue-700 px-1 rounded">점자블록</span>}
            {segment.avgSlopePercent != null && segment.avgSlopePercent > 3 &&
                <span className="bg-orange-100 text-orange-700 px-1 rounded">
                    경사 {segment.avgSlopePercent.toFixed(1)}%
                </span>}
            {segment.curbRampState === 'YES' &&
                <span className="bg-green-100 text-green-700 px-1 rounded">경사로</span>}
            {segment.audioSignalState === 'YES' &&
                <span className="bg-purple-100 text-purple-700 px-1 rounded">음향신호</span>}
        </div>
    );
}
```

---

## 9. 메인 App 조립

```tsx
// src/App.tsx
export default function App() {
    const [response, setResponse] = useState<RouteSearchResponse | null>(null);
    const [activeOption, setActiveOption] = useState<RouteOption>('SAFE');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSearch = async (req: RouteSearchRequest) => {
        setLoading(true);
        setError(null);
        try {
            const result = await searchRoutes(req);
            setResponse(result);
            // 첫 번째 available 옵션 자동 선택
            const first = result.options.find(o => o.available);
            if (first) setActiveOption(first.option);
        } catch (e) {
            setError('경로 탐색에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        } finally {
            setLoading(false);
        }
    };

    const activeResult = response?.options.find(o => o.option === activeOption);

    return (
        <div className="flex h-screen">
            {/* 사이드 패널 */}
            <div className="w-80 p-4 overflow-y-auto bg-gray-50 border-r">
                <h1 className="text-lg font-bold mb-4">부산이음길</h1>
                <SearchForm onSearch={handleSearch} />

                {loading && <div className="mt-4 text-center text-gray-500">경로 탐색 중...</div>}
                {error   && <div className="mt-4 text-red-600 text-sm">{error}</div>}

                {response && (
                    <div className="mt-4">
                        <RouteOptionTabs
                            options={response.options}
                            activeOption={activeOption}
                            onSelect={setActiveOption}
                        />

                        {/* 도보 경로 세그먼트 목록 */}
                        {activeResult?.segments?.map(seg => (
                            <div key={seg.sequence} className="mb-2 p-2 bg-white rounded border">
                                <div className="text-sm">{seg.guidanceMessage}</div>
                                <div className="text-xs text-gray-500 mt-0.5">
                                    {Math.round(seg.distanceMeter)}m
                                </div>
                                <AccessibilityBadge segment={seg} />
                            </div>
                        ))}

                        {/* 대중교통 leg 목록 */}
                        {activeResult?.legs?.map(leg => (
                            <div key={leg.sequence} className="mb-2 p-2 bg-white rounded border">
                                {leg.type === 'WALK' && (
                                    <div className="text-sm">도보 {leg.distanceMeter}m · {leg.durationMinute}분</div>
                                )}
                                {leg.type === 'BUS' && (
                                    <div className="text-sm">
                                        버스 {leg.routeNo}  {leg.boardName} → {leg.alightName}
                                        {leg.isLowFloor && <span className="ml-1 text-green-600 text-xs">저상</span>}
                                    </div>
                                )}
                                {leg.type === 'SUBWAY' && (
                                    <div className="text-sm">
                                        {leg.lineName}  {leg.boardName} → {leg.alightName}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* 지도 */}
            <div className="flex-1">
                <MapView result={response} activeOption={activeOption} />
            </div>
        </div>
    );
}
```

---

## 10. package.json

```json
{
  "name": "ieumgil-frontend",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "dev":     "vite",
    "build":   "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react":     "^18.3.1",
    "react-dom": "^18.3.1",
    "axios":     "^1.7.2"
  },
  "devDependencies": {
    "@types/react":        "^18.3.3",
    "@types/react-dom":    "^18.3.0",
    "@vitejs/plugin-react":"^4.3.1",
    "autoprefixer":        "^10.4.19",
    "postcss":             "^8.4.38",
    "tailwindcss":         "^3.4.4",
    "typescript":          "^5.4.5",
    "vite":                "^5.3.1"
  }
}
```

---

## 11. Dockerfile (nginx 정적 서빙)

```dockerfile
# frontend/Dockerfile

# ── 빌드 스테이지 ──
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# 환경변수 주입 (docker compose build --build-arg 또는 compose environment)
ARG VITE_API_BASE_URL=http://localhost:8080
ARG VITE_KAKAO_JS_KEY=""

RUN VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_KAKAO_JS_KEY=$VITE_KAKAO_JS_KEY \
    npm run build

# ── 서빙 스테이지 ──
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA 라우팅 — 모든 경로를 index.html로
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 백엔드 API 프록시 (CORS 우회)
    location /routes {
        proxy_pass         http://backend:8080;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }

    location /actuator {
        proxy_pass         http://backend:8080;
        deny all;          # actuator는 외부 노출 금지
    }

    # 정적 파일 캐싱
    location ~* \.(js|css|png|jpg|svg|ico|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 12. docker-compose 반영 확인

svc_plan_00의 docker-compose에 이미 포함됨. `KAKAO_JS_KEY` 환경변수 추가 필요:

```yaml
# docker-compose.yml (svc_plan_00 기준 — 이미 작성됨)
frontend:
  build:
    context: ./frontend
    args:
      VITE_API_BASE_URL: http://localhost:8080  # 외부에서 접근 시 실제 도메인으로
      VITE_KAKAO_JS_KEY: ${KAKAO_JS_KEY}
  ports:
    - "3000:80"
  depends_on:
    - backend
  restart: unless-stopped
```

```bash
# .env (svc_plan_00 .env.example에 추가 필요)
KAKAO_JS_KEY=your_kakao_js_key_here
```

> **주의:** Vite 빌드 타임에 환경변수가 번들에 포함됨. 런타임 환경변수 주입 불가.  
> `docker compose build` 시 `--build-arg`로 전달되어야 하므로 `args:` 사용.

---

## 13. 로컬 개발 실행

```bash
cd frontend
npm install

# .env.local 생성
echo "VITE_API_BASE_URL=http://localhost:8080" > .env.local
echo "VITE_KAKAO_JS_KEY=your_key" >> .env.local

npm run dev
# → http://localhost:5173 (Vite dev server)
# → /routes 요청은 vite.config.ts proxy → localhost:8080으로 포워딩
```

---

## 14. 완료 기준

- [ ] `npm run dev` 실행 → 카카오맵 지도 표시 (SDK 로드 오류 없음)
- [ ] 출발지/목적지 입력 → 장소 검색 → 좌표 세팅 → 경로 탐색 버튼 활성화
- [ ] SAFE / SHORTEST 탭 전환 → 지도 경로 변경
- [ ] PUBLIC_TRANSPORT 탭 → 정류장/역 마커 지도 표시 (실제 정류장 위치)
- [ ] 도보 경로 선 색상: 계단(빨강) / 급경사(주황) / 점자블록(파랑) / 일반(녹색)
- [ ] `available: false` 옵션 탭 → 비활성 표시 + reason 메시지
- [ ] `docker compose up frontend` → 포트 3000 접속 → 동일 동작 확인
- [ ] `.env.local`, `KAKAO_JS_KEY` `.gitignore` 확인 (커밋 방지)
