#!/bin/bash
# Trigger Glue ETL jobs to process Bronze → Silver → Gold

export AWS_PROFILE=noaa-target

echo "Triggering NOAA Glue ETL Jobs..."
echo ""

# Trigger Bronze to Silver
echo "1. Bronze → Silver transformation..."
BRONZE_RUN=$(aws glue start-job-run --job-name noaa-bronze-to-silver-dev --query 'JobRunId' --output text 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✅ Started: $BRONZE_RUN"
else
    echo "   ⚠️ $BRONZE_RUN"
fi

sleep 2

# Trigger Silver to Gold
echo "2. Silver → Gold transformation..."
SILVER_RUN=$(aws glue start-job-run --job-name noaa-silver-to-gold-dev --query 'JobRunId' --output text 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✅ Started: $SILVER_RUN"
else
    echo "   ⚠️ $SILVER_RUN"
fi

sleep 2

# Trigger aggregations
echo "3. Hourly aggregation..."
HOURLY_RUN=$(aws glue start-job-run --job-name noaa-hourly-aggregation-dev --query 'JobRunId' --output text 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✅ Started: $HOURLY_RUN"
else
    echo "   ⚠️ $HOURLY_RUN"
fi

echo ""
echo "✅ Glue jobs triggered!"
echo ""
echo "Monitor with:"
echo "  aws glue get-job-runs --job-name noaa-bronze-to-silver-dev --max-results 1 --profile noaa-target"
