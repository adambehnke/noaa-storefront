#!/bin/bash

################################################################################
# Fix Table Definitions and Start 24-Hour Monitoring
# This script creates proper Athena tables and monitors ingestion
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ENV="${ENV:-dev}"
BUCKET_NAME="noaa-data-lake-${ENV}"
DATABASE_NAME="noaa_federated_${ENV}"
ATHENA_OUTPUT="s3://${BUCKET_NAME}/athena-results/"

echo ""
echo "=========================================="
echo "NOAA Table Fix & 24-Hour Monitor"
echo "=========================================="
echo ""
echo "Step 1: Creating proper Athena tables..."
echo ""

# Function to run Athena query
run_athena_query() {
    local query="$1"
    local description="$2"

    echo "  Running: ${description}..."

    local query_id=$(aws athena start-query-execution \
        --query-string "${query}" \
        --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
        --query-execution-context "Database=${DATABASE_NAME}" \
        --region "${AWS_REGION}" \
        --query 'QueryExecutionId' \
        --output text 2>&1)

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed: ${description}${NC}"
        return 1
    fi

    # Wait for completion
    for i in {1..30}; do
        local status=$(aws athena get-query-execution \
            --query-execution-id "${query_id}" \
            --region "${AWS_REGION}" \
            --query 'QueryExecution.Status.State' \
            --output text 2>&1)

        if [ "${status}" = "SUCCEEDED" ]; then
            echo -e "${GREEN}✓ ${description}${NC}"
            return 0
        elif [ "${status}" = "FAILED" ]; then
            local error=$(aws athena get-query-execution \
                --query-execution-id "${query_id}" \
                --region "${AWS_REGION}" \
                --query 'QueryExecution.Status.StateChangeReason' \
                --output text 2>&1)
            echo -e "${RED}✗ Failed: ${error}${NC}"
            return 1
        fi
        sleep 1
    done

    echo -e "${YELLOW}⚠ Timeout${NC}"
    return 1
}

# Create Atmospheric Tables
echo ""
echo "Creating Atmospheric tables..."

run_athena_query "DROP TABLE IF EXISTS atmospheric_observations_gold" "Drop old atmospheric_observations_gold"

run_athena_query "CREATE EXTERNAL TABLE atmospheric_observations_gold (
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
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/atmospheric/observations/'" "Create atmospheric_observations_gold"

run_athena_query "MSCK REPAIR TABLE atmospheric_observations_gold" "Repair atmospheric_observations_gold partitions"

run_athena_query "DROP TABLE IF EXISTS atmospheric_alerts_gold" "Drop old atmospheric_alerts_gold"

run_athena_query "CREATE EXTERNAL TABLE atmospheric_alerts_gold (
    alert_id STRING,
    event STRING,
    headline STRING,
    description STRING,
    severity STRING,
    certainty STRING,
    urgency STRING,
    effective STRING,
    expires STRING,
    alert_priority INT,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/atmospheric/alerts/'" "Create atmospheric_alerts_gold"

run_athena_query "MSCK REPAIR TABLE atmospheric_alerts_gold" "Repair atmospheric_alerts_gold partitions"

run_athena_query "DROP TABLE IF EXISTS atmospheric_stations_gold" "Drop old atmospheric_stations_gold"

run_athena_query "CREATE EXTERNAL TABLE atmospheric_stations_gold (
    station_id STRING,
    name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/atmospheric/stations/'" "Create atmospheric_stations_gold"

run_athena_query "MSCK REPAIR TABLE atmospheric_stations_gold" "Repair atmospheric_stations_gold partitions"

# Create Buoy Tables
echo ""
echo "Creating Buoy tables..."

run_athena_query "DROP TABLE IF EXISTS buoy_metadata_gold" "Drop old buoy_metadata_gold"

run_athena_query "CREATE EXTERNAL TABLE buoy_metadata_gold (
    buoy_id STRING,
    name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/buoy/metadata/'" "Create buoy_metadata_gold"

run_athena_query "MSCK REPAIR TABLE buoy_metadata_gold" "Repair buoy_metadata_gold partitions"

# Create Spatial Tables
echo ""
echo "Creating Spatial tables..."

run_athena_query "DROP TABLE IF EXISTS spatial_zones_gold" "Drop old spatial_zones_gold"

run_athena_query "CREATE EXTERNAL TABLE spatial_zones_gold (
    zone_id STRING,
    zone_type STRING,
    name STRING,
    state STRING,
    has_geometry BOOLEAN,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/spatial/zones/'" "Create spatial_zones_gold"

run_athena_query "MSCK REPAIR TABLE spatial_zones_gold" "Repair spatial_zones_gold partitions"

run_athena_query "DROP TABLE IF EXISTS spatial_locations_gold" "Drop old spatial_locations_gold"

run_athena_query "CREATE EXTERNAL TABLE spatial_locations_gold (
    location_name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/spatial/locations/'" "Create spatial_locations_gold"

run_athena_query "MSCK REPAIR TABLE spatial_locations_gold" "Repair spatial_locations_gold partitions"

# Create Terrestrial Tables
echo ""
echo "Creating Terrestrial tables..."

run_athena_query "DROP TABLE IF EXISTS terrestrial_observations_gold" "Drop old terrestrial_observations_gold"

run_athena_query "CREATE EXTERNAL TABLE terrestrial_observations_gold (
    station_id STRING,
    hour STRING,
    observation_count INT,
    avg_temperature DOUBLE,
    max_temperature DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/terrestrial/observations/'" "Create terrestrial_observations_gold"

run_athena_query "MSCK REPAIR TABLE terrestrial_observations_gold" "Repair terrestrial_observations_gold partitions"

run_athena_query "DROP TABLE IF EXISTS terrestrial_metadata_gold" "Drop old terrestrial_metadata_gold"

run_athena_query "CREATE EXTERNAL TABLE terrestrial_metadata_gold (
    station_id STRING,
    name STRING,
    latitude DOUBLE,
    longitude DOUBLE,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/terrestrial/metadata/'" "Create terrestrial_metadata_gold"

run_athena_query "MSCK REPAIR TABLE terrestrial_metadata_gold" "Repair terrestrial_metadata_gold partitions"

# Create Climate Tables
echo ""
echo "Creating Climate tables..."

run_athena_query "DROP TABLE IF EXISTS climate_metadata_gold" "Drop old climate_metadata_gold"

run_athena_query "CREATE EXTERNAL TABLE climate_metadata_gold (
    station_id STRING,
    name STRING,
    ingestion_timestamp STRING
)
PARTITIONED BY (year INT, month INT, day INT)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://${BUCKET_NAME}/gold/climate/metadata/'" "Create climate_metadata_gold"

run_athena_query "MSCK REPAIR TABLE climate_metadata_gold" "Repair climate_metadata_gold partitions"

# Verify tables work
echo ""
echo "=========================================="
echo "Step 2: Verifying tables have data..."
echo "=========================================="
echo ""

verify_table() {
    local table=$1
    echo "Checking ${table}..."

    local count=$(aws athena start-query-execution \
        --query-string "SELECT COUNT(*) FROM ${table}" \
        --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
        --query-execution-context "Database=${DATABASE_NAME}" \
        --region "${AWS_REGION}" \
        --query 'QueryExecutionId' \
        --output text 2>&1)

    sleep 3

    local result=$(aws athena get-query-results \
        --query-execution-id "${count}" \
        --region "${AWS_REGION}" \
        --query 'ResultSet.Rows[1].Data[0].VarCharValue' \
        --output text 2>&1)

    if [ -n "${result}" ] && [ "${result}" != "0" ] && [ "${result}" != "None" ]; then
        echo -e "${GREEN}✓ ${table}: ${result} records${NC}"
    else
        echo -e "${YELLOW}⚠ ${table}: No data yet (will populate soon)${NC}"
    fi
}

verify_table "atmospheric_observations_gold"
verify_table "atmospheric_alerts_gold"
verify_table "atmospheric_stations_gold"
verify_table "buoy_metadata_gold"
verify_table "spatial_zones_gold"
verify_table "spatial_locations_gold"
verify_table "terrestrial_observations_gold"
verify_table "terrestrial_metadata_gold"
verify_table "climate_metadata_gold"

echo ""
echo "=========================================="
echo "Step 3: Starting 24-Hour Monitoring..."
echo "=========================================="
echo ""

# Create log directory
LOG_DIR="deployment/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/monitor_24h_$(date +%Y%m%d_%H%M%S).log"

echo "Monitoring log: ${LOG_FILE}"
echo ""
echo "Will check every 15 minutes for 24 hours (96 checks total)"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Monitoring loop
check_count=0
max_checks=96  # 24 hours * 4 checks per hour

while [ ${check_count} -lt ${max_checks} ]; do
    check_count=$((check_count + 1))

    echo "=========================================="
    echo "CHECK #${check_count} of ${max_checks}"
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="

    # Check each table
    for table in atmospheric_observations_gold atmospheric_alerts_gold buoy_metadata_gold spatial_zones_gold terrestrial_observations_gold; do
        verify_table "${table}"
    done

    # Check Lambda executions
    echo ""
    echo "Recent Lambda executions:"
    for pond in atmospheric oceanic buoy climate spatial terrestrial; do
        lambda_name="noaa-ingest-${pond}-${ENV}"
        recent=$(aws logs filter-log-events \
            --log-group-name "/aws/lambda/${lambda_name}" \
            --start-time $(($(date +%s) * 1000 - 900000)) \
            --filter-pattern "Ingestion complete" \
            --region "${AWS_REGION}" \
            --query 'events[0].message' \
            --output text 2>/dev/null | head -1)

        if [ -n "${recent}" ] && [ "${recent}" != "None" ]; then
            echo -e "${GREEN}✓ ${pond}: Recent execution${NC}"
        else
            echo -e "${YELLOW}⚠ ${pond}: No recent execution${NC}"
        fi
    done

    # Check S3 data growth
    echo ""
    echo "S3 Data Volume:"
    total_size=$(aws s3 ls s3://${BUCKET_NAME}/gold/ --recursive --summarize 2>/dev/null | grep "Total Size" | awk '{print $3" "$4}')
    total_files=$(aws s3 ls s3://${BUCKET_NAME}/gold/ --recursive --summarize 2>/dev/null | grep "Total Objects" | awk '{print $3}')
    echo "  Files: ${total_files}"
    echo "  Size: ${total_size}"

    echo ""
    echo "Next check in 15 minutes..."
    echo "=========================================="
    echo ""

    # Log to file
    {
        echo "CHECK #${check_count} - $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Total files: ${total_files}, Size: ${total_size}"
        echo ""
    } >> "${LOG_FILE}"

    # Wait 15 minutes unless it's the last check
    if [ ${check_count} -lt ${max_checks} ]; then
        sleep 900  # 15 minutes
    fi
done

echo ""
echo "=========================================="
echo "24-Hour Monitoring Complete!"
echo "=========================================="
echo "Total checks: ${check_count}"
echo "Log file: ${LOG_FILE}"
echo ""
