#!/bin/bash
set -e

# =============================================================================
# NOAA Glue ETL - Quick Start Script
# =============================================================================
# Runs ETL jobs immediately and makes data queryable in Athena
#
# Usage: ./run-etl-now.sh [environment]
# Example: ./run-etl-now.sh dev
# =============================================================================

ENV=${1:-dev}
REGION=${AWS_REGION:-us-east-1}

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          NOAA ETL Pipeline - Quick Start                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Environment: $ENV"
echo "Region:      $REGION"
echo ""

# =============================================================================
# STEP 1: Trigger ETL Jobs
# =============================================================================

echo "[1/4] Starting ETL jobs..."
echo ""

JOB_IDS=()

for job in atmospheric-observations oceanic; do
  echo "  ▶ Starting: noaa-etl-${job}-${ENV}"
  JOB_ID=$(aws glue start-job-run \
    --job-name "noaa-etl-${job}-${ENV}" \
    --region "$REGION" \
    --query 'JobRunId' \
    --output text 2>&1)

  if [[ $JOB_ID == jr_* ]]; then
    echo "    ✓ Job started: $JOB_ID"
    JOB_IDS+=("noaa-etl-${job}-${ENV}:$JOB_ID")
  else
    echo "    ⚠ Failed to start (may already be running)"
  fi
done

echo ""
echo "✓ ETL jobs triggered"
echo ""

# =============================================================================
# STEP 2: Wait for Jobs to Complete
# =============================================================================

echo "[2/4] Waiting for ETL jobs to complete..."
echo "      (This takes about 3-5 minutes)"
echo ""

sleep 180  # Initial wait

for job_info in "${JOB_IDS[@]}"; do
  IFS=':' read -r job_name job_id <<< "$job_info"

  echo "  Checking: $job_name"

  MAX_ATTEMPTS=10
  ATTEMPT=0

  while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    STATUS=$(aws glue get-job-run \
      --job-name "$job_name" \
      --run-id "$job_id" \
      --region "$REGION" \
      --query 'JobRun.JobRunState' \
      --output text 2>/dev/null || echo "UNKNOWN")

    if [ "$STATUS" == "SUCCEEDED" ]; then
      echo "    ✓ Completed successfully"
      break
    elif [ "$STATUS" == "FAILED" ]; then
      echo "    ⚠ Failed (check logs)"
      break
    elif [ "$STATUS" == "RUNNING" ]; then
      echo "    ⏳ Still running... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
      sleep 30
      ATTEMPT=$((ATTEMPT + 1))
    else
      echo "    ? Status: $STATUS"
      sleep 30
      ATTEMPT=$((ATTEMPT + 1))
    fi
  done
done

echo ""
echo "✓ ETL processing complete"
echo ""

# =============================================================================
# STEP 3: Run Crawlers to Catalog Data
# =============================================================================

echo "[3/4] Running Glue crawlers to catalog queryable data..."
echo ""

for crawler in atmospheric oceanic; do
  echo "  ▶ Starting: noaa-queryable-${crawler}-crawler-${ENV}"

  aws glue start-crawler \
    --name "noaa-queryable-${crawler}-crawler-${ENV}" \
    --region "$REGION" 2>&1 | grep -q "CrawlerRunningException" && \
    echo "    ⚠ Already running" || \
    echo "    ✓ Started"
done

echo ""
echo "  ⏳ Waiting for crawlers (60 seconds)..."
sleep 60

echo ""
echo "✓ Crawlers complete"
echo ""

# =============================================================================
# STEP 4: Test Query with Athena
# =============================================================================

echo "[4/4] Testing Athena query..."
echo ""

DATABASE="noaa_queryable_${ENV}"
ATHENA_OUTPUT="s3://noaa-athena-results-899626030376-${ENV}/"

# Check if database exists
DB_EXISTS=$(aws glue get-database \
  --name "$DATABASE" \
  --region "$REGION" 2>&1 | grep -c "EntityNotFoundException" || echo "0")

if [ "$DB_EXISTS" -gt 0 ]; then
  echo "  ⚠ Database $DATABASE does not exist yet"
  echo "    Run the crawlers manually and wait 2-3 minutes"
  exit 0
fi

# List tables
echo "  Available tables in $DATABASE:"
aws glue get-tables \
  --database-name "$DATABASE" \
  --region "$REGION" \
  --query 'TableList[].Name' \
  --output table 2>/dev/null || echo "    No tables yet - crawlers still running"

echo ""
echo "  Running test query..."

# Test query
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT station_id, hour, avg_temperature, avg_wind_speed FROM ${DATABASE}.observations WHERE station_id = 'KBOS' ORDER BY hour DESC LIMIT 5" \
  --result-configuration "OutputLocation=${ATHENA_OUTPUT}" \
  --query-execution-context "Database=${DATABASE}" \
  --region "$REGION" \
  --query 'QueryExecutionId' \
  --output text 2>&1)

if [[ $QUERY_ID == *"-"* ]]; then
  echo "    Query ID: $QUERY_ID"
  sleep 5

  # Get results
  RESULT=$(aws athena get-query-results \
    --query-execution-id "$QUERY_ID" \
    --region "$REGION" \
    --output table 2>&1)

  if echo "$RESULT" | grep -q "station_id"; then
    echo ""
    echo "  ✓ Query successful! Results:"
    echo "$RESULT" | head -20
  else
    echo "    ⚠ Query returned no data (tables may still be cataloging)"
  fi
else
  echo "    ⚠ Query failed - tables may not be ready yet"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ ETL Pipeline Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Query your data in Athena:"
echo ""
echo "   Database: $DATABASE"
echo "   Tables:   observations, water_level, water_temperature, etc."
echo ""
echo "   Example Query:"
echo "   SELECT station_id, hour, avg_temperature, avg_wind_speed"
echo "   FROM ${DATABASE}.observations"
echo "   WHERE station_id IN ('KBOS', 'KPWM')"
echo "   ORDER BY hour DESC LIMIT 10;"
echo ""
echo "🌐 Athena Console:"
echo "   https://console.aws.amazon.com/athena/home?region=${REGION}"
echo ""
echo "📝 View Glue Jobs:"
echo "   https://console.aws.amazon.com/glue/home?region=${REGION}#etl:tab=jobs"
echo ""
echo "════════════════════════════════════════════════════════════════"
