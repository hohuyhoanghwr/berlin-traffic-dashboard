CREATE EXTENSION IF NOT EXISTS postgis;

-- Table for Road Segment Metadata (Static)
CREATE TABLE IF NOT EXISTS road_segments (
    segment_id SERIAL PRIMARY KEY, -- Unique identifier from OSM
    name_road_segment VARCHAR(255) NOT NULL, -- Name of the road segment (e.g., "Karl-Liebknecht-Straße")
    geometry GEOMETRY(LineString, 4326) NOT NULL, -- The actual LineString geometry of the road segment. SRID 4326 is for WGS84 (latitude/longitude)
    UNIQUE (geometry)
);

-- Spatial index for efficient geospatial queries
CREATE INDEX IF NOT EXISTS idx_road_segments_geometry ON road_segments USING GIST (geometry);

-- Table for Aggregated Traffic KPIs (Time-Series Data): hourly KPI values for each road segment
CREATE TABLE IF NOT EXISTS traffic_kpis (
    kpi_id SERIAL PRIMARY KEY,
    segment_id INTEGER NOT NULL REFERENCES road_segments(segment_id), -- Foreign key linking to the road_segments table
    measurement_timestamp TIMESTAMP WITH TIME ZONE NOT NULL, -- Timestamp of the measurement (hourly)
    vehicle_type VARCHAR(10) NOT NULL, -- Vehicle Type (e.g., 'all', 'cars', 'trucks')
    kpi_type VARCHAR(20) NOT NULL, -- KPI Type (e.g., 'vehicle_count', 'average_speed')
    kpi_value NUMERIC(10, 2) NOT NULL, -- The actual KPI value. Numeric to allow for decimal speeds
    UNIQUE (segment_id, measurement_timestamp, vehicle_type, kpi_type) -- prevent duplicate KPI entries for the same segment, time, type
);

-- Create indexes for efficient querying based on time, segment, and filters
CREATE INDEX IF NOT EXISTS idx_traffic_kpis_timestamp ON traffic_kpis (measurement_timestamp);
CREATE INDEX IF NOT EXISTS idx_traffic_kpis_segment_id ON traffic_kpis (segment_id);
CREATE INDEX IF NOT EXISTS idx_traffic_kpis_vehicle_type ON traffic_kpis (vehicle_type);
CREATE INDEX IF NOT EXISTS idx_traffic_kpis_kpi_type ON traffic_kpis (kpi_type);

-- Create a composite index for common queries
CREATE INDEX IF NOT EXISTS idx_traffic_kpis_composite ON traffic_kpis (segment_id, measurement_timestamp, vehicle_type, kpi_type);

-- Table for Detector Metadata
CREATE TABLE IF NOT EXISTS detector_metadata (
    det_id15 VARCHAR(15) PRIMARY KEY, -- Detector ID
    lane VARCHAR(50),                 -- Lane information
    street_name VARCHAR(255),         -- NEW: Street name from the Excel file
    lon NUMERIC(10, 6),               -- NEW: Longitude (WGS84)
    lat NUMERIC(10, 6)                -- NEW: Latitude (WGS84)
);