-- ============================================================================
-- NOAA Federated Data Lake - Proper Athena Table Definitions
-- Creates tables that match the actual S3 data structure
-- ============================================================================

-- Database
CREATE DATABASE IF NOT EXISTS noaa_federated_dev;

-- ============================================================================
-- ATMOSPHERIC POND TABLES
-- ============================================================================

-- Atmospheric Observations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.atmospheric_observations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.atmospheric_observations_gold (
    station_id STRING,
    hour STRING,
    observation_count INT,
    avg_temperature DOUBLE,
    max_temperature DOUBLE,
    min_temperature DOUBLE,
    avg_wind_speed DOUBLE,
    max_wind_speed DOUBLE,
    data_quality_score DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/atmospheric/observations/';

-- Atmospheric Alerts (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.atmospheric_alerts_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.atmospheric_alerts_gold (
    alert_id STRING,
    event STRING,
    headline STRING,
    description STRING,
    severity STRING,
    certainty STRING,
    urgency STRING,
    status STRING,
    effective STRING,
    expires STRING,
    affected_zones STRING,
    alert_priority INT,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/atmospheric/alerts/';

-- Atmospheric Stations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.atmospheric_stations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.atmospheric_stations_gold (
    station_id STRING,
    name STRING,
    timezone STRING,
    forecast_office STRING,
    county STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    elevation_value DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/atmospheric/stations/';

-- ============================================================================
-- OCEANIC POND TABLES
-- ============================================================================

-- Oceanic Observations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.oceanic_observations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.oceanic_observations_gold (
    station_id STRING,
    product STRING,
    hour STRING,
    observation_count INT,
    avg_value DOUBLE,
    max_value DOUBLE,
    min_value DOUBLE,
    verified_count INT,
    data_quality_score DOUBLE,
    avg_wind_speed DOUBLE,
    max_wind_speed DOUBLE,
    max_wind_gust DOUBLE,
    avg_current_speed DOUBLE,
    max_current_speed DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/oceanic/water_level/';

-- Oceanic Stations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.oceanic_stations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.oceanic_stations_gold (
    station_id STRING,
    name STRING,
    state STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    timezone STRING,
    timezone_offset INT,
    station_type STRING,
    products STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/oceanic/stations/';

-- ============================================================================
-- BUOY POND TABLES
-- ============================================================================

-- Buoy Observations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.buoy_observations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.buoy_observations_gold (
    buoy_id STRING,
    hour STRING,
    observation_count INT,
    avg_wave_height DOUBLE,
    max_wave_height DOUBLE,
    min_wave_height DOUBLE,
    avg_wave_period DOUBLE,
    avg_wind_speed DOUBLE,
    max_wind_speed DOUBLE,
    max_wind_gust DOUBLE,
    avg_water_temperature DOUBLE,
    avg_air_temperature DOUBLE,
    data_completeness DOUBLE,
    wave_data_available BOOLEAN,
    wind_data_available BOOLEAN,
    sea_state STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/buoy/observations/';

-- Buoy Metadata (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.buoy_metadata_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.buoy_metadata_gold (
    buoy_id STRING,
    name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/buoy/metadata/';

-- ============================================================================
-- CLIMATE POND TABLES
-- ============================================================================

-- Climate Observations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.climate_observations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.climate_observations_gold (
    station_id STRING,
    date STRING,
    year INT,
    month INT,
    day INT,
    observation_count INT,
    temperature_max_c DOUBLE,
    temperature_min_c DOUBLE,
    temperature_avg_c DOUBLE,
    temperature_range_c DOUBLE,
    precipitation_mm DOUBLE,
    has_precipitation BOOLEAN,
    snowfall_mm DOUBLE,
    snow_depth_mm DOUBLE,
    has_snow BOOLEAN,
    weather_events STRING,
    extreme_event_count INT,
    data_completeness DOUBLE,
    heating_degree_days DOUBLE,
    cooling_degree_days DOUBLE,
    ingestion_timestamp STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/climate/observations/';

-- Climate Stations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.climate_metadata_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.climate_metadata_gold (
    station_id STRING,
    name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    elevation DOUBLE,
    min_date STRING,
    max_date STRING,
    datacoverage DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/climate/metadata/';

-- ============================================================================
-- SPATIAL POND TABLES
-- ============================================================================

-- Spatial Zones (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.spatial_zones_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.spatial_zones_gold (
    zone_id STRING,
    zone_type STRING,
    name STRING,
    name_lower STRING,
    name_tokens STRING,
    state STRING,
    cwa STRING,
    forecast_offices STRING,
    time_zone STRING,
    observation_stations STRING,
    geometry_type STRING,
    geometry STRING,
    has_geometry BOOLEAN,
    has_forecast_office BOOLEAN,
    is_marine BOOLEAN,
    is_coastal BOOLEAN,
    region STRING,
    coast STRING,
    grid_lat INT,
    grid_lon INT,
    spatial_key STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/spatial/zones/';

-- Spatial Locations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.spatial_locations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.spatial_locations_gold (
    location_name STRING,
    name_lower STRING,
    name_tokens STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    cwa STRING,
    forecast_office STRING,
    grid_id STRING,
    grid_x INT,
    grid_y INT,
    forecast_url STRING,
    county STRING,
    time_zone STRING,
    radar_station STRING,
    geometry STRING,
    coordinates_valid BOOLEAN,
    region STRING,
    coast STRING,
    has_geometry BOOLEAN,
    has_forecast_office BOOLEAN,
    grid_lat INT,
    grid_lon INT,
    spatial_key STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/spatial/locations/';

-- Spatial Marine Zones (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.spatial_marine_zones_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.spatial_marine_zones_gold (
    zone_id STRING,
    zone_type STRING,
    name STRING,
    name_lower STRING,
    name_tokens STRING,
    state STRING,
    cwa STRING,
    forecast_offices STRING,
    observation_stations STRING,
    geometry_type STRING,
    geometry STRING,
    has_geometry BOOLEAN,
    has_forecast_office BOOLEAN,
    is_marine BOOLEAN,
    is_coastal BOOLEAN,
    grid_lat INT,
    grid_lon INT,
    spatial_key STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/spatial/marine_zones/';

-- ============================================================================
-- TERRESTRIAL POND TABLES
-- ============================================================================

-- Terrestrial Observations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.terrestrial_observations_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.terrestrial_observations_gold (
    station_id STRING,
    hour STRING,
    observation_count INT,
    avg_temperature DOUBLE,
    max_temperature DOUBLE,
    min_temperature DOUBLE,
    temperature_range DOUBLE,
    avg_humidity DOUBLE,
    total_precipitation DOUBLE,
    max_precipitation_rate DOUBLE,
    avg_wind_speed DOUBLE,
    max_wind_speed DOUBLE,
    high_temp_events INT,
    freezing_events INT,
    heavy_precip_events INT,
    strong_wind_events INT,
    data_completeness DOUBLE,
    heat_index_avg DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/terrestrial/observations/';

-- Terrestrial Stations (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.terrestrial_metadata_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.terrestrial_metadata_gold (
    station_id STRING,
    name STRING,
    timezone STRING,
    forecast_office STRING,
    county STRING,
    fire_weather_zone STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    elevation DOUBLE,
    station_type STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/terrestrial/metadata/';

-- Terrestrial Fire Weather (Gold Layer)
DROP TABLE IF EXISTS noaa_federated_dev.terrestrial_fire_weather_gold;
CREATE EXTERNAL TABLE noaa_federated_dev.terrestrial_fire_weather_gold (
    alert_id STRING,
    alert_type STRING,
    event STRING,
    headline STRING,
    description STRING,
    severity STRING,
    urgency STRING,
    certainty STRING,
    area_desc STRING,
    sent STRING,
    effective STRING,
    onset STRING,
    expires STRING,
    affected_zones STRING,
    geometry STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (
    year INT,
    month INT,
    day INT
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-data-lake-dev/gold/terrestrial/fire_weather/';

-- ============================================================================
-- REPAIR ALL PARTITIONS
-- ============================================================================

-- Atmospheric
MSCK REPAIR TABLE noaa_federated_dev.atmospheric_observations_gold;
MSCK REPAIR TABLE noaa_federated_dev.atmospheric_alerts_gold;
MSCK REPAIR TABLE noaa_federated_dev.atmospheric_stations_gold;

-- Oceanic
MSCK REPAIR TABLE noaa_federated_dev.oceanic_observations_gold;
MSCK REPAIR TABLE noaa_federated_dev.oceanic_stations_gold;

-- Buoy
MSCK REPAIR TABLE noaa_federated_dev.buoy_observations_gold;
MSCK REPAIR TABLE noaa_federated_dev.buoy_metadata_gold;

-- Climate
MSCK REPAIR TABLE noaa_federated_dev.climate_observations_gold;
MSCK REPAIR TABLE noaa_federated_dev.climate_metadata_gold;

-- Spatial
MSCK REPAIR TABLE noaa_federated_dev.spatial_zones_gold;
MSCK REPAIR TABLE noaa_federated_dev.spatial_locations_gold;
MSCK REPAIR TABLE noaa_federated_dev.spatial_marine_zones_gold;

-- Terrestrial
MSCK REPAIR TABLE noaa_federated_dev.terrestrial_observations_gold;
MSCK REPAIR TABLE noaa_federated_dev.terrestrial_metadata_gold;
MSCK REPAIR TABLE noaa_federated_dev.terrestrial_fire_weather_gold;
