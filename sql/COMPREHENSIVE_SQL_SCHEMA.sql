-- ============================================================================
-- NOAA FEDERATED DATA LAKE - COMPREHENSIVE SQL SCHEMA
-- Medallion Architecture: Bronze → Silver → Gold
-- Author: NOAA Federated Data Lake Team
-- Version: 2.0
-- Date: December 2025
-- ============================================================================

-- ============================================================================
-- BRONZE LAYER - Raw Data Ingestion
-- ============================================================================

-- Atmospheric Pond - Raw Weather Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.atmospheric_raw (
    id string,
    properties struct<
        id:string,
        areaDesc:string,
        geocode:struct<SAME:array<string>,UGC:array<string>>,
        affectedZones:array<string>,
        references:array<struct<id:string,identifier:string,sender:string>>,
        sent:string,
        effective:string,
        onset:string,
        expires:string,
        ends:string,
        status:string,
        messageType:string,
        category:string,
        severity:string,
        certainty:string,
        urgency:string,
        event:string,
        sender:string,
        senderName:string,
        headline:string,
        description:string,
        instruction:string,
        response:string,
        parameters:map<string,array<string>>
    >,
    geometry struct<
        type:string,
        coordinates:array<array<array<double>>>
    >,
    ingestion_timestamp string,
    source_api string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw atmospheric data from NWS API'
);

-- Oceanic Pond - Raw Tide and Water Level Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.oceanic_raw (
    metadata struct<
        id:string,
        name:string,
        lat:double,
        lon:double
    >,
    data array<struct<
        t:string,
        v:double,
        s:double,
        f:string,
        q:string
    >>,
    station_id string,
    product string,
    datum string,
    ingestion_timestamp string,
    source_api string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/oceanic/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw oceanic data from NOAA Tides & Currents API'
);

-- Buoy Pond - Raw Marine Buoy Observations
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.buoy_raw (
    station_id string,
    timestamp string,
    wind_direction_deg double,
    wind_speed_mps double,
    gust_speed_mps double,
    wave_height_m double,
    dominant_wave_period_sec double,
    average_wave_period_sec double,
    wave_direction_deg double,
    sea_level_pressure_hpa double,
    air_temperature_c double,
    water_temperature_c double,
    dewpoint_temperature_c double,
    visibility_nmi double,
    tide_ft double,
    ingestion_timestamp string,
    source_api string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/buoy/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw buoy data from NDBC API'
);

-- Climate Pond - Raw Climate Data from CDO
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.climate_raw (
    station_id string,
    station_name string,
    latitude double,
    longitude double,
    elevation double,
    date string,
    datatype string,
    value double,
    measurement_flag string,
    quality_flag string,
    source_flag string,
    observation_time string,
    attributes array<struct<
        name:string,
        value:string
    >>,
    ingestion_timestamp string,
    source_api string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/climate/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw climate data from NOAA CDO API'
);

-- Terrestrial Pond - Raw Land/Soil Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.terrestrial_raw (
    location string,
    latitude double,
    longitude double,
    date string,
    soil_moisture_percent double,
    soil_temperature_c double,
    drought_index double,
    precipitation_mm double,
    evapotranspiration_mm double,
    snow_depth_cm double,
    snow_water_equivalent_mm double,
    ingestion_timestamp string,
    source_api string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/terrestrial/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw terrestrial data'
);

-- Spatial Pond - Raw Geographic/Boundary Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_bronze_dev.spatial_raw (
    feature_id string,
    feature_type string,
    name string,
    description string,
    geometry struct<
        type:string,
        coordinates:array<array<array<double>>>
    >,
    properties map<string,string>,
    source string,
    ingestion_timestamp string
)
STORED AS JSON
LOCATION 's3://noaa-federated-lake-899626030376-dev/bronze/spatial/'
TBLPROPERTIES (
    'classification'='json',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Raw spatial/geographic data'
);

-- ============================================================================
-- SILVER LAYER - Cleaned and Normalized Data
-- ============================================================================

-- Atmospheric Pond - Cleaned Weather Alerts
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_silver_dev.atmospheric_cleaned (
    alert_id string,
    area_description string,
    state_codes array<string>,
    ugc_codes array<string>,
    affected_zones array<string>,
    sent_timestamp timestamp,
    effective_timestamp timestamp,
    onset_timestamp timestamp,
    expires_timestamp timestamp,
    ends_timestamp timestamp,
    status string,
    message_type string,
    category string,
    severity string,
    certainty string,
    urgency string,
    event_type string,
    sender string,
    sender_name string,
    headline string,
    description string,
    instruction string,
    response_type string,
    latitude double,
    longitude double,
    ingestion_date date,
    processing_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/silver/atmospheric/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Cleaned and normalized atmospheric data'
);

-- Oceanic Pond - Cleaned Tide and Water Level Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_silver_dev.oceanic_cleaned (
    station_id string,
    station_name string,
    latitude double,
    longitude double,
    observation_timestamp timestamp,
    water_level_ft double,
    sigma double,
    flags string,
    quality string,
    product_type string,
    datum string,
    ingestion_date date,
    processing_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/silver/oceanic/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Cleaned and normalized oceanic data'
);

-- Buoy Pond - Cleaned Marine Observations
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_silver_dev.buoy_cleaned (
    station_id string,
    station_name string,
    latitude double,
    longitude double,
    observation_timestamp timestamp,
    wind_direction_deg double,
    wind_speed_mps double,
    gust_speed_mps double,
    wave_height_m double,
    dominant_wave_period_sec double,
    average_wave_period_sec double,
    wave_direction_deg double,
    sea_level_pressure_hpa double,
    air_temperature_c double,
    water_temperature_c double,
    dewpoint_temperature_c double,
    visibility_nmi double,
    tide_ft double,
    data_quality_score double,
    ingestion_date date,
    processing_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/silver/buoy/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Cleaned and normalized buoy data'
);

-- Climate Pond - Cleaned Historical Climate Data
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_silver_dev.climate_cleaned (
    station_id string,
    station_name string,
    latitude double,
    longitude double,
    elevation_m double,
    observation_date date,
    observation_timestamp timestamp,
    data_type string,
    value double,
    unit string,
    measurement_flag string,
    quality_flag string,
    source_flag string,
    data_quality_score double,
    ingestion_date date,
    processing_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/silver/climate/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Cleaned and normalized climate data'
);

-- ============================================================================
-- GOLD LAYER - Aggregated and Enriched Data (API-Ready)
-- ============================================================================

-- Atmospheric Pond - Aggregated Weather Statistics
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.atmospheric_aggregated (
    region string,
    state_code string,
    event_type string,
    severity string,
    alert_count bigint,
    avg_certainty double,
    urgent_count bigint,
    immediate_count bigint,
    future_count bigint,
    severity_distribution struct<
        extreme:bigint,
        severe:bigint,
        moderate:bigint,
        minor:bigint,
        unknown:bigint
    >,
    most_common_response string,
    active_alerts_list array<struct<
        id:string,
        event:string,
        headline:string
    >>,
    aggregation_date date,
    created_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/atmospheric/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Aggregated atmospheric data optimized for API queries',
    'partitioned_by'='aggregation_date'
);

-- Oceanic Pond - Aggregated Tide and Water Level Statistics
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.oceanic_aggregated (
    station_id string,
    station_name string,
    location string,
    latitude double,
    longitude double,
    avg_water_level_ft double,
    max_water_level_ft double,
    min_water_level_ft double,
    water_level_range_ft double,
    tide_cycle_count bigint,
    record_count bigint,
    data_quality_avg double,
    hourly_values array<struct<
        hour:int,
        avg_level:double
    >>,
    aggregation_date date,
    created_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/oceanic/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Aggregated oceanic data optimized for API queries',
    'partitioned_by'='aggregation_date'
);

-- Buoy Pond - Aggregated Marine Observation Statistics
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.buoy_aggregated (
    station_id string,
    station_name string,
    location string,
    latitude double,
    longitude double,
    avg_wave_height_m double,
    max_wave_height_m double,
    avg_wind_speed_mps double,
    max_wind_speed_mps double,
    avg_air_temp_c double,
    avg_water_temp_c double,
    avg_pressure_hpa double,
    dominant_wave_direction_deg double,
    dominant_wind_direction_deg double,
    record_count bigint,
    data_quality_avg double,
    hazard_indicators struct<
        high_waves:boolean,
        strong_winds:boolean,
        low_visibility:boolean
    >,
    aggregation_date date,
    created_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/buoy/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Aggregated buoy data optimized for API queries',
    'partitioned_by'='aggregation_date'
);

-- Climate Pond - Aggregated Historical Climate Statistics
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.climate_aggregated (
    station_id string,
    station_name string,
    location string,
    latitude double,
    longitude double,
    data_type string,
    unit string,
    avg_value double,
    max_value double,
    min_value double,
    stddev_value double,
    record_count bigint,
    data_quality_avg double,
    trend_indicator string,
    percentile_50 double,
    percentile_90 double,
    percentile_95 double,
    aggregation_date date,
    created_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/climate/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Aggregated climate data optimized for API queries',
    'partitioned_by'='aggregation_date'
);

-- ============================================================================
-- CROSS-POND ANALYTICS TABLES (Multi-Type Pond)
-- ============================================================================

-- Federated Query Log - Track Multi-Pond Queries
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.federated_query_log (
    query_id string,
    user_query string,
    intent string,
    ponds_queried array<string>,
    location struct<
        type:string,
        name:string,
        latitude:double,
        longitude:double
    >,
    time_range struct<
        start_date:string,
        end_date:string,
        days:int
    >,
    total_records bigint,
    response_time_ms bigint,
    success boolean,
    error_message string,
    query_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/federated_queries/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Federated query audit log for analytics'
);

-- Cross-Pond Correlation Table
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.cross_pond_correlations (
    correlation_id string,
    pond_a string,
    pond_b string,
    location string,
    correlation_type string,
    correlation_coefficient double,
    significance_level double,
    observation_count bigint,
    pattern_description string,
    example_events array<struct<
        timestamp:timestamp,
        pond_a_value:double,
        pond_b_value:double
    >>,
    analysis_date date,
    created_timestamp timestamp
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/correlations/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'creator'='NOAA Data Pipeline',
    'description'='Cross-pond correlation analysis for ML insights'
);

-- ============================================================================
-- MATERIALIZED VIEWS (For Performance Optimization)
-- ============================================================================

-- Daily Summary View - All Ponds
CREATE OR REPLACE VIEW noaa_gold_dev.daily_summary AS
SELECT
    'atmospheric' as pond_name,
    aggregation_date,
    COUNT(*) as record_count,
    COLLECT_SET(region) as regions
FROM noaa_gold_dev.atmospheric_aggregated
GROUP BY aggregation_date
UNION ALL
SELECT
    'oceanic' as pond_name,
    aggregation_date,
    COUNT(*) as record_count,
    COLLECT_SET(location) as regions
FROM noaa_gold_dev.oceanic_aggregated
GROUP BY aggregation_date
UNION ALL
SELECT
    'buoy' as pond_name,
    aggregation_date,
    COUNT(*) as record_count,
    COLLECT_SET(location) as regions
FROM noaa_gold_dev.buoy_aggregated
GROUP BY aggregation_date
UNION ALL
SELECT
    'climate' as pond_name,
    aggregation_date,
    COUNT(*) as record_count,
    COLLECT_SET(location) as regions
FROM noaa_gold_dev.climate_aggregated
GROUP BY aggregation_date;

-- ============================================================================
-- DATA QUALITY TABLES
-- ============================================================================

-- Data Quality Metrics
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.data_quality_metrics (
    pond_name string,
    table_name string,
    metric_name string,
    metric_value double,
    pass_fail string,
    threshold_value double,
    record_count bigint,
    check_timestamp timestamp,
    check_date date
)
STORED AS PARQUET
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/quality_metrics/'
TBLPROPERTIES (
    'parquet.compression'='SNAPPY',
    'has_encrypted_data'='false',
    'description'='Data quality monitoring metrics'
);

-- ============================================================================
-- UTILITY FUNCTIONS AND PROCEDURES
-- ============================================================================

-- Function to calculate data freshness
-- (Note: Athena doesn't support UDFs directly, but this is pseudocode for Glue ETL)

COMMENT ON DATABASE noaa_bronze_dev IS 'Raw data layer - JSON format, direct API responses';
COMMENT ON DATABASE noaa_silver_dev IS 'Cleaned data layer - Parquet format, normalized schema';
COMMENT ON DATABASE noaa_gold_dev IS 'Aggregated data layer - Parquet format, API-optimized';

-- ============================================================================
-- MAINTENANCE QUERIES
-- ============================================================================

-- Vacuum old partitions (run monthly)
-- VACUUM noaa_gold_dev.atmospheric_aggregated RETAIN 168 HOURS;

-- Analyze tables for query optimization (run weekly)
-- ANALYZE TABLE noaa_gold_dev.atmospheric_aggregated COMPUTE STATISTICS;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
