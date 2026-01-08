# NOAA Data Lake - Historical Backfill System Deployment Guide

**Version:** 1.0  
**Date:** December 11, 2025  
**Account:** 899626030376  
**Status:** Ready for Deployment

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Prerequisites](#prerequisites)
4. [Fix Gold Layer Dashboard (Required)](#fix-gold-layer-dashboard-required)
5. [Deploy Historical Backfill System](#deploy-historical-backfill-system)
6. [Running Historical Backfill](#running-historical-backfill)
7. [Monitoring Progress](#monitoring-progress)
8. [Architecture Details](#architecture-details)
9. [Troubleshooting](#troubleshooting)
10. [Cost Estimates](#cost-estimates)

---

## Overview

The Historical Backfill System automatically ingests historical NOAA data dating back up to one year, processes it through the medallion architecture (Bronze → Silver → Gold), and makes it available for AI-interpreted queries.

### Key Features

- ✅ **Automated Historical Data Collection** - Fetches data in 7-day increments
- ✅ **Checkpoint/Resume Capability** - Resume from interruptions
- ✅ **Medallion Processing** - Bronze → Silver → Gold transformation
- ✅ **Rate Limiting** - Respects NOAA API limits
- ✅ **Progress Tracking** - Detailed logging and statistics
- ✅ **Error Handling** - Graceful failure recovery
- ✅ **Multi-Pond Support** - All 6 data ponds (atmospheric, oceanic, buoy, climate, terrestrial, spatial)

### Data Flow

```
NOAA APIs → Lambda (Bronze) → Glue ETL (Silver) → Glue ETL (Gold) → Athena → AI Queries
                   ↓                    ↓                    ↓
                 Raw JSON           Cleaned JSON        Parquet/Optimized
```

---

## Quick Start

```bash
# 1. Fix Gold Layer Dashboard
cd noaa_storefront
AWS_PROFILE=noaa-target bash scripts/fix_gold_dashboard.sh

# 2. Test backfill (7 days only)
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds atmospheric \
  --days-back 7 \
  --test

# 3. Full backfill (1 year, all ponds)
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 365
```

---

## Prerequisites

### 1. AWS Account Access

```bash
# Verify you're in the correct account
AWS_PROFILE=noaa-target aws sts get-caller-identity

# Should return: Account 899626030376
```

### 2. Python Dependencies

```bash
pip install boto3 botocore
```

### 3. Verify Existing Infrastructure

```bash
# Check ingestion Lambdas exist
AWS_PROFILE=noaa-target aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'ingest')].FunctionName"

# Check S3 bucket
AWS_PROFILE=noaa-target aws s3 ls s3://noaa-federated-lake-899626030376-dev/

# Check Glue ETL jobs (optional - will be created if missing)
AWS_PROFILE=noaa-target aws glue get-jobs \
  --query "Jobs[?contains(Name, 'noaa')].Name"
```

---

## Fix Gold Layer Dashboard (Required)

### Issue

The Gold layer dashboard modal currently returns a 502 Bad Gateway error due to:
1. Missing IAM permissions (Glue, Athena)
2. Lambda timeout on slow Athena queries

### Solution

Create and run the fix script:

```bash
#!/bin/bash
# scripts/fix_gold_dashboard.sh

export AWS_PROFILE=noaa-target
export AWS_REGION=us-east-1

echo "Fixing Gold Layer Dashboard..."

# 1. Add Glue and Athena permissions to dashboard Lambda role
cat > /tmp/dashboard-full-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:ListFunctions",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "events:ListRules",
        "events:DescribeRule",
        "events:ListTargetsByRule"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "glue:GetTables",
        "glue:GetTable",
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetJob",
        "glue:GetJobs",
        "glue:GetJobRuns"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:StartQueryExecution",
        "athena:StopQueryExecution"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev/*",
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name noaa-dev-lambda-exec \
  --policy-name DashboardMetricsFullAccess \
  --policy-document file:///tmp/dashboard-full-policy.json

echo "✅ IAM permissions updated"

# 2. Increase Lambda timeout
aws lambda update-function-configuration \
  --function-name noaa-dashboard-metrics \
  --timeout 120 \
  --memory-size 1024

echo "✅ Lambda timeout increased to 120s"

# 3. Force Lambda restart
aws lambda update-function-configuration \
  --function-name noaa-dashboard-metrics \
  --environment "Variables={DATA_LAKE_BUCKET=noaa-federated-lake-899626030376-dev,ATHENA_DATABASE=noaa_data_lake,ATHENA_OUTPUT_BUCKET=s3://noaa-federated-lake-899626030376-dev/athena-results/,UPDATED=$(date +%s)}"

echo "✅ Lambda restarted"

# 4. Test Gold layer endpoint
echo ""
echo "Testing Gold layer endpoint..."
sleep 10

RESPONSE=$(curl -s "https://ghew7mwudk326bla57wgqe5xxi0ymhjm.lambda-url.us-east-1.on.aws/?metric_type=gold_layer")

if echo "$RESPONSE" | grep -q "gold"; then
    echo "✅ Gold layer dashboard is working!"
else
    echo "⚠️  Gold layer may need additional fixes. Check logs:"
    echo "aws logs tail /aws/lambda/noaa-dashboard-metrics --follow --profile noaa-target"
fi

echo ""
echo "Dashboard URL: https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html"
```

Run it:

```bash
chmod +x scripts/fix_gold_dashboard.sh
AWS_PROFILE=noaa-target bash scripts/fix_gold_dashboard.sh
```

---

## Deploy Historical Backfill System

The backfill system is already created in `scripts/historical_backfill_system.py`. No deployment needed - just run it!

### Verify Lambda Functions Support Backfill

The ingestion Lambdas need to accept `mode: "backfill"` and date range parameters:

```python
# Expected Lambda payload format
{
  "env": "dev",
  "mode": "backfill",           # or "incremental"
  "start_date": "2024-12-01",
  "end_date": "2024-12-07"
}
```

If your Lambdas don't support this yet, they will use current date (still useful for building up historical data).

---

## Running Historical Backfill

### Test Run (7 days, single pond)

```bash
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds atmospheric \
  --days-back 7 \
  --test
```

**Expected output:**
```
================================================================================
NOAA HISTORICAL DATA BACKFILL
================================================================================
Account: 899626030376
Bucket: noaa-federated-lake-899626030376-dev
Ponds: atmospheric
Days back: 7
Test mode: True
================================================================================

[1/1] Processing atmospheric: 2024-12-04 to 2024-12-11
✓ Bronze ingestion successful: 1498 records, 66 API calls
✓ Silver transformation triggered
✓ Gold aggregation triggered
✓ Range completed: 1498 records ingested
```

### Production Run (90 days, all ponds)

```bash
# Start with 90 days to see how it performs
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 90 \
  > backfill_$(date +%Y%m%d).log 2>&1 &

# Get the process ID
echo $! > backfill.pid
```

### Full Year Backfill (365 days)

```bash
# Run in screen or tmux for long-running process
screen -S noaa-backfill

AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 365

# Detach: Ctrl+A, D
# Reattach: screen -r noaa-backfill
```

### Resume from Checkpoint

If the backfill is interrupted:

```bash
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --resume
```

The system automatically saves progress to `backfill_checkpoint.json` every 5 iterations.

---

## Monitoring Progress

### 1. Check Checkpoint File

```bash
cat backfill_checkpoint.json | python3 -m json.tool
```

Shows:
- Total records ingested
- Completed date ranges per pond
- Failed ranges
- API call count

### 2. Monitor Logs

```bash
# Real-time log
tail -f backfill.log

# Lambda logs
AWS_PROFILE=noaa-target aws logs tail \
  /aws/lambda/noaa-ingest-atmospheric-dev \
  --follow
```

### 3. Check S3 Data Growth

```bash
# Check Bronze layer
AWS_PROFILE=noaa-target aws s3 ls \
  s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/ \
  --recursive --human-readable | tail -20

# Count files per pond
for pond in atmospheric oceanic buoy climate terrestrial; do
  count=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/${pond}/ \
    --recursive --profile noaa-target | wc -l)
  echo "${pond}: ${count} files"
done
```

### 4. Monitor CloudWatch Metrics

```bash
# Check Lambda invocations
AWS_PROFILE=noaa-target aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=noaa-ingest-atmospheric-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### 5. Query Data in Athena

```sql
-- Check data coverage by date
SELECT 
    DATE(observation_time) as date,
    COUNT(*) as record_count,
    COUNT(DISTINCT station_id) as station_count
FROM gold_atmospheric
WHERE year = 2024 AND month = 12
GROUP BY DATE(observation_time)
ORDER BY date DESC
LIMIT 30;

-- Check oldest data available
SELECT 
    MIN(observation_time) as oldest_record,
    MAX(observation_time) as newest_record,
    COUNT(*) as total_records
FROM gold_atmospheric;
```

---

## Architecture Details

### Medallion Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Historical Backfill                       │
│                    (Python Script)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │  Lambda Ingestion          │
        │  (noaa-ingest-*-dev)       │
        │  - Calls NOAA APIs         │
        │  - Writes raw JSON         │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Bronze Layer (S3)         │
        │  - Raw JSON data           │
        │  - Partitioned by date     │
        │  - Preserves all fields    │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Glue ETL Job              │
        │  (bronze-to-silver)        │
        │  - Validates data          │
        │  - Cleans nulls            │
        │  - Standardizes schema     │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Silver Layer (S3)         │
        │  - Cleaned JSON            │
        │  - Schema enforced         │
        │  - Quality validated       │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Glue ETL Job              │
        │  (silver-to-gold)          │
        │  - Converts to Parquet     │
        │  - Aggregates data         │
        │  - Optimizes for queries   │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Gold Layer (S3)           │
        │  - Parquet format          │
        │  - Compressed              │
        │  - Analytics-optimized     │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  Athena Tables             │
        │  - Queryable via SQL       │
        │  - Partitioned             │
        │  - Indexed                 │
        └──────────┬─────────────────┘
                   │
                   ▼
        ┌────────────────────────────┐
        │  AI Query System           │
        │  - Natural language        │
        │  - Bedrock/Claude          │
        │  - Comprehensive results   │
        └────────────────────────────┘
```

### S3 Path Structure

```
s3://noaa-federated-lake-899626030376-dev/
├── bronze/
│   ├── atmospheric/
│   │   ├── observations/year=2024/month=12/day=11/hour=17/data_*.json
│   │   ├── alerts/year=2024/month=12/day=11/hour=17/data_*.json
│   │   └── stations/year=2024/month=12/day=11/hour=17/data_*.json
│   ├── oceanic/
│   │   ├── water_level/year=2024/month=12/day=11/...
│   │   └── wind/year=2024/month=12/day=11/...
│   └── [other ponds]/
├── silver/
│   ├── atmospheric/
│   │   └── [cleaned JSON with schema]
│   └── [other ponds]/
└── gold/
    ├── atmospheric/
    │   └── [parquet files, optimized]
    └── [other ponds]/
```

---

## Troubleshooting

### Problem: Lambda Timeout

**Symptoms:** Backfill script shows "Error invoking Lambda: timeout"

**Solution:**
```bash
# Increase Lambda timeout
AWS_PROFILE=noaa-target aws lambda update-function-configuration \
  --function-name noaa-ingest-atmospheric-dev \
  --timeout 300

# Or reduce chunk size in backfill script
# Edit POND_CONFIGS in historical_backfill_system.py:
"chunk_size_days": 3  # Reduced from 7
```

### Problem: API Rate Limits

**Symptoms:** NOAA API returns 429 errors

**Solution:**
```bash
# Increase sleep time in backfill script
# Edit POND_CONFIGS:
"api_rate_limit": 6  # Reduced from 12 (slower but safer)
```

### Problem: No Data in Bronze

**Symptoms:** verify_data_in_bronze() returns 0 files

**Possible causes:**
1. Date range has no historical data (NOAA limitation)
2. Lambda not writing to S3
3. Path structure mismatch

**Solution:**
```bash
# Check Lambda logs
AWS_PROFILE=noaa-target aws logs tail \
  /aws/lambda/noaa-ingest-atmospheric-dev \
  --since 10m

# Manually check S3
AWS_PROFILE=noaa-target aws s3 ls \
  s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/ \
  --recursive | grep 2024-12
```

### Problem: Glue Jobs Not Found

**Symptoms:** "Glue job not found - transformation skipped"

**Solution:**

Glue ETL jobs are optional for backfill. The system will still write to Bronze. You can:

1. Create Glue jobs later
2. Run manual transformations
3. Or continue - Bronze data is still queryable

To create Glue jobs:
```bash
# Deploy ETL pipeline
cd glue-etl
AWS_PROFILE=noaa-target bash deploy-etl-pipeline.sh
```

### Problem: Checkpoint Corruption

**Symptoms:** JSON parse error on resume

**Solution:**
```bash
# Backup and reset checkpoint
cp backfill_checkpoint.json backfill_checkpoint.json.bak
rm backfill_checkpoint.json

# Restart backfill (will start fresh)
```

---

## Cost Estimates

### Lambda Invocations

- **1 year backfill, all ponds:** ~2,600 invocations
- **Cost:** ~$0.00 (within free tier: 1M requests/month)

### Lambda Compute

- **Execution time:** 30-60s per invocation
- **Total compute:** ~45 hours
- **Cost:** ~$0.75 (128MB memory)

### S3 Storage

- **Data size:** ~40 GB Bronze, 35 GB Silver, 15 GB Gold = 90 GB total
- **Cost:** $90 * $0.023/GB = **~$2.07/month**

### Glue ETL

- **If using Glue:** $0.44/DPU-hour
- **Estimated:** 10 hours total = **~$4.40**

### Athena Queries

- **$5 per TB scanned**
- **Historical queries:** ~100 GB scanned = **$0.50**

### **Total Estimated Cost for 1-Year Backfill: $7-10**

---

## Performance Expectations

### Backfill Speed

| Pond | Days/Hour | Full Year Time |
|------|-----------|----------------|
| Atmospheric | 10-15 | ~24-36 hours |
| Oceanic | 15-20 | ~18-24 hours |
| Buoy | 15-20 | ~18-24 hours |
| Climate | 30-40 | ~9-12 hours |
| Terrestrial | 15-20 | ~18-24 hours |

**Parallel runs:** You can run multiple ponds simultaneously in separate terminals:

```bash
# Terminal 1
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds atmospheric --days-back 365 &

# Terminal 2
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds oceanic --days-back 365 &

# Terminal 3
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds buoy --days-back 365 &
```

This reduces total time to **~24-36 hours** for all ponds.

---

## Verification

After backfill completes:

### 1. Check Data Coverage

```bash
# Check Bronze layer
AWS_PROFILE=noaa-target aws s3 ls \
  s3://noaa-federated-lake-899626030376-dev/bronze/ \
  --recursive --human-readable --summarize
```

### 2. Query Historical Data

```sql
-- Athena query
SELECT 
    year,
    month,
    COUNT(*) as records,
    MIN(observation_time) as earliest,
    MAX(observation_time) as latest
FROM gold_atmospheric
GROUP BY year, month
ORDER BY year DESC, month DESC;
```

### 3. Test AI Queries

Visit dashboard and ask:
- "What were the temperatures in Miami last January?"
- "Show me hurricane activity in the Gulf of Mexico from last summer"
- "Compare water levels on the East Coast between March and April 2024"

### 4. Dashboard Verification

1. Open: https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html
2. Click Bronze Layer modal - should show current data
3. Click Silver Layer modal - should show transformation stats
4. Click Gold Layer modal - should show tables and analytics
5. All should display without errors

---

## Next Steps

1. ✅ Fix Gold layer dashboard
2. ✅ Test backfill with 7 days
3. ✅ Run 90-day backfill
4. ✅ Monitor and validate
5. ✅ Run full 365-day backfill
6. 🔄 Set up automated daily incremental updates
7. 🔄 Create alerting for data gaps
8. 🔄 Optimize query performance

---

## Support

- **Dashboard:** https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html
- **Logs:** CloudWatch `/aws/lambda/noaa-ingest-*-dev`
- **Checkpoint:** `backfill_checkpoint.json`
- **Documentation:** `INGESTION_STATUS_REPORT.md`

**For issues:**
```bash
# Check system status
AWS_PROFILE=noaa-target bash scripts/check_and_fix_ingestion.sh

# View recent logs
AWS_PROFILE=noaa-target aws logs tail \
  /aws/lambda/noaa-ingest-atmospheric-dev \
  --since 1h
```

---

**Last Updated:** December 11, 2025  
**Status:** Ready for Production Backfill