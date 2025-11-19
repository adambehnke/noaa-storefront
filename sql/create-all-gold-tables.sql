-- Atmospheric (already exists but recreate if needed)
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.atmospheric_aggregated (
    region string,
    event_type string,
    severity string,
    alert_count bigint,
    avg_certainty double,
    date string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/atmospheric/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- Oceanic (tides and currents)
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.oceanic_aggregated (
    station_id string,
    station_name string,
    location string,
    avg_water_level double,
    max_water_level double,
    min_water_level double,
    record_count bigint,
    date string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/oceanic/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- Buoy (marine observations)
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.buoy_aggregated (
    buoy_id string,
    location string,
    avg_wave_height double,
    avg_wind_speed double,
    avg_air_temp double,
    avg_water_temp double,
    record_count bigint,
    date string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/buoy/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- Climate (CDO data)
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.climate_aggregated (
    station_id string,
    location string,
    data_type string,
    avg_value double,
    max_value double,
    min_value double,
    record_count bigint,
    date string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/climate/'
TBLPROPERTIES ('has_encrypted_data'='false');

-- Archive (NCEI historical data)
CREATE EXTERNAL TABLE IF NOT EXISTS noaa_gold_dev.archive_aggregated (
    dataset string,
    location string,
    data_type string,
    value double,
    record_count bigint,
    date string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/archive/'
TBLPROPERTIES ('has_encrypted_data'='false');
