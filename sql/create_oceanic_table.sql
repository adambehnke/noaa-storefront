CREATE EXTERNAL TABLE noaa_gold_dev.oceanic_aggregated (
    station_id STRING,
    station_name STRING,
    state STRING,
    region STRING,
    timestamp STRING,
    avg_water_temp DOUBLE,
    min_water_temp DOUBLE,
    max_water_temp DOUBLE,
    temp_readings_count INT,
    avg_water_level DOUBLE,
    min_water_level DOUBLE,
    max_water_level DOUBLE,
    level_readings_count INT
)
PARTITIONED BY (date STRING)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://noaa-federated-lake-899626030376-dev/gold/oceanic/'
TBLPROPERTIES ('has_encrypted_data'='false')
