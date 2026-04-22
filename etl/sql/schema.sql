CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
BEGIN
    CREATE TYPE accessibility_state AS ENUM ('YES', 'NO', 'UNKNOWN');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE width_state AS ENUM ('ADEQUATE_150', 'ADEQUATE_120', 'NARROW', 'UNKNOWN');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE crossing_state AS ENUM ('TRAFFIC_SIGNALS', 'NO', 'UNKNOWN');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS users (
    "userId" UUID PRIMARY KEY,
    "nickname" VARCHAR(50),
    "socialProvider" VARCHAR(30) NOT NULL,
    "socialProviderUserId" VARCHAR(100) NOT NULL,
    "disabilityType" VARCHAR(30),
    "disabilityGrade" VARCHAR(20),
    "phoneNumber" VARCHAR(20) NOT NULL DEFAULT '119',
    "locationTermsAgreed" BOOLEAN NOT NULL DEFAULT FALSE,
    "locationTermsAgreedAt" VARCHAR(30),
    "ttsEnabled" BOOLEAN NOT NULL DEFAULT TRUE,
    "routeCollectionEnabled" BOOLEAN NOT NULL DEFAULT FALSE,
    "pushEnabled" BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE ("socialProvider", "socialProviderUserId")
);

CREATE TABLE IF NOT EXISTS places (
    "placeId" INT PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "category" VARCHAR(50) NOT NULL,
    "address" VARCHAR(255),
    "point" geometry(POINT, 4326) NOT NULL,
    "providerPlaceId" VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS place_accessibility_features (
    "id" INT PRIMARY KEY,
    "placeId" INT NOT NULL REFERENCES places ("placeId"),
    "featureType" VARCHAR(50) NOT NULL,
    "isAvailable" BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE ("placeId", "featureType")
);

CREATE TABLE IF NOT EXISTS bookmarks (
    "bookmarkId" INT PRIMARY KEY,
    "userId" UUID NOT NULL REFERENCES users ("userId"),
    "placeId" INT NOT NULL REFERENCES places ("placeId"),
    UNIQUE ("userId", "placeId")
);

CREATE TABLE IF NOT EXISTS favorite_routes (
    "favRouteId" INT PRIMARY KEY,
    "routeName" VARCHAR(100) NOT NULL,
    "startLabel" VARCHAR(255) NOT NULL,
    "endLabel" VARCHAR(255) NOT NULL,
    "startPoint" geometry(POINT, 4326) NOT NULL,
    "endPoint" geometry(POINT, 4326) NOT NULL,
    "routeOption" VARCHAR(30) NOT NULL DEFAULT 'SAFE',
    "userId" UUID NOT NULL REFERENCES users ("userId")
);

CREATE TABLE IF NOT EXISTS hazard_reports (
    "reportId" INT PRIMARY KEY,
    "reportType" VARCHAR(30) NOT NULL,
    "description" TEXT,
    "reportPoint" geometry(POINT, 4326) NOT NULL,
    "address" VARCHAR(255),
    "status" VARCHAR(30) NOT NULL DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS hazard_report_images (
    "reportImgId" INT PRIMARY KEY,
    "imageUrl" TEXT NOT NULL,
    "displayOrder" SMALLINT NOT NULL DEFAULT 0,
    "reportId" INT NOT NULL REFERENCES hazard_reports ("reportId"),
    UNIQUE ("reportId", "displayOrder")
);

CREATE TABLE IF NOT EXISTS road_nodes (
    "vertexId" BIGINT PRIMARY KEY,
    "osmNodeId" BIGINT NOT NULL UNIQUE,
    "point" geometry(POINT, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS road_segments (
    "edgeId" BIGINT PRIMARY KEY,
    "fromNodeId" BIGINT NOT NULL REFERENCES road_nodes ("vertexId"),
    "toNodeId" BIGINT NOT NULL REFERENCES road_nodes ("vertexId"),
    "geom" geometry(LINESTRING, 4326) NOT NULL,
    "lengthMeter" NUMERIC(10, 2) NOT NULL,
    "sourceWayId" BIGINT NOT NULL,
    "sourceOsmFromNodeId" BIGINT NOT NULL,
    "sourceOsmToNodeId" BIGINT NOT NULL,
    "segmentOrdinal" INT NOT NULL,
    "avgSlopePercent" NUMERIC(6, 2),
    "widthMeter" NUMERIC(6, 2),
    "walkAccess" VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    "brailleBlockState" accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    "audioSignalState" accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    "curbRampState" accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    "widthState" width_state NOT NULL DEFAULT 'UNKNOWN',
    "surfaceState" VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    "stairsState" accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    "elevatorState" accessibility_state NOT NULL DEFAULT 'UNKNOWN',
    "crossingState" crossing_state NOT NULL DEFAULT 'UNKNOWN',
    UNIQUE ("sourceWayId", "sourceOsmFromNodeId", "sourceOsmToNodeId", "segmentOrdinal")
);

CREATE TABLE IF NOT EXISTS segment_features (
    "featureId" BIGSERIAL PRIMARY KEY,
    "edgeId" BIGINT NOT NULL REFERENCES road_segments ("edgeId"),
    "featureType" VARCHAR(50) NOT NULL,
    "geom" geometry(Geometry, 4326) NOT NULL
);

CREATE TABLE IF NOT EXISTS route_logs (
    "routeLogId" BIGINT PRIMARY KEY,
    "disabilityType" VARCHAR(30) NOT NULL,
    "routeOption" VARCHAR(30) NOT NULL DEFAULT 'SAFE',
    "startedAt" VARCHAR(30) NOT NULL,
    "endedAt" VARCHAR(30) NOT NULL,
    "distanceMeter" NUMERIC(10, 2)
);

CREATE TABLE IF NOT EXISTS route_log_points (
    "routeLogPointId" BIGINT PRIMARY KEY,
    "routeLogId" BIGINT NOT NULL REFERENCES route_logs ("routeLogId"),
    "sequence" INT NOT NULL,
    "point" geometry(POINT, 4326) NOT NULL,
    "recordedAt" VARCHAR(30) NOT NULL,
    "accuracyMeter" NUMERIC(8, 2),
    UNIQUE ("routeLogId", "sequence")
);

CREATE TABLE IF NOT EXISTS low_floor_bus_routes (
    "routeId" VARCHAR(20) PRIMARY KEY,
    "routeNo" VARCHAR(20) NOT NULL,
    "hasLowFloor" BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS subway_station_elevators (
    "elevatorId" INT PRIMARY KEY,
    "stationId" VARCHAR(20) NOT NULL,
    "stationName" VARCHAR(100) NOT NULL,
    "lineName" VARCHAR(50) NOT NULL,
    "entranceNo" VARCHAR(10),
    "point" geometry(POINT, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_places_point ON places USING GIST ("point");
CREATE INDEX IF NOT EXISTS idx_hazard_reports_point ON hazard_reports USING GIST ("reportPoint");
CREATE INDEX IF NOT EXISTS idx_road_nodes_point ON road_nodes USING GIST ("point");
CREATE INDEX IF NOT EXISTS idx_road_segments_geom ON road_segments USING GIST ("geom");
CREATE INDEX IF NOT EXISTS idx_road_segments_way ON road_segments ("sourceWayId");
CREATE INDEX IF NOT EXISTS idx_road_segments_nodes ON road_segments ("fromNodeId", "toNodeId");
CREATE INDEX IF NOT EXISTS idx_segment_features_geom ON segment_features USING GIST ("geom");
CREATE INDEX IF NOT EXISTS idx_route_log_points_point ON route_log_points USING GIST ("point");
CREATE INDEX IF NOT EXISTS idx_subway_station_elevators_station_id ON subway_station_elevators ("stationId");
CREATE INDEX IF NOT EXISTS idx_subway_station_elevators_point ON subway_station_elevators USING GIST ("point");
