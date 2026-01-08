# NOAA Federated Data Lake - Enhanced Features Deployment Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Enhancement 1: Real-Time Streaming](#enhancement-1-real-time-streaming)
5. [Enhancement 2: Advanced Analytics Layer](#enhancement-2-advanced-analytics-layer)
6. [Enhancement 3: QuickSight Dashboards](#enhancement-3-quicksight-dashboards)
7. [Deployment Instructions](#deployment-instructions)
8. [Configuration](#configuration)
9. [Usage Examples](#usage-examples)
10. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
11. [Cost Analysis](#cost-analysis)
12. [Best Practices](#best-practices)

---

## Overview

This guide covers three major enhancements to the NOAA Federated Data Lake:

### 🌊 Real-Time Streaming Infrastructure
High-frequency data ingestion using **Amazon Kinesis Data Streams** for atmospheric, oceanic, and buoy data with sub-second latency and automatic persistence to S3.

### 📊 Advanced Analytics Layer
**Multi-tiered analytics platform** with Glue ETL jobs for hourly/daily aggregations, ML feature engineering, and cross-pond correlation analysis.

### 📈 QuickSight Dashboards
**Interactive visualizations** for operational monitoring, analytics insights, and data quality metrics with role-based access control.

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    NOAA Federated Data Lake                          │
│                     Enhanced Architecture                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│  Data Sources       │
│  (NOAA APIs)        │
└──────┬──────────────┘
       │
       ├─ Batch Ingestion (existing)
       │         │
       │         ▼
       │  ┌─────────────┐
       │  │   Lambda    │
       │  │  Functions  │
       │  └──────┬──────┘
       │         │
       ├─ Real-Time Streaming (NEW)
       │         │
       │         ▼
       │  ┌─────────────────────────────────────┐
       │  │    Kinesis Data Streams             │
       │  ├─────────────────────────────────────┤
       │  │  • Atmospheric Stream (2 shards)    │
       │  │  • Oceanic Stream (2 shards)        │
       │  │  • Buoy Stream (2 shards)           │
       │  └──────┬──────────────────────────────┘
       │         │
       │         ▼
       │  ┌─────────────────────┐
       │  │ Stream Processors   │
       │  │    (Lambda)         │
       │  └──────┬──────────────┘
       │         │
       └─────────┴──────────────┐
                                │
                                ▼
                    ┌───────────────────────┐
                    │   S3 Data Lake        │
                    ├───────────────────────┤
                    │  • Bronze Layer       │
                    │  • Silver Layer       │
                    │  • Gold Layer         │
                    │  • Streaming Layer    │──┐
                    │  • Analytics Layer    │  │ (NEW)
                    │  • ML Datasets        │  │ (NEW)
                    └───────┬───────────────┘  │
                            │                  │
                            │                  │
        ┌───────────────────┴──────────────────┴──────────┐
        │                                                  │
        ▼                                                  ▼
┌───────────────────┐                          ┌──────────────────────┐
│  Glue Crawlers    │                          │  Glue ETL Jobs       │
│  & Data Catalog   │                          │  (Analytics)         │
└────────┬──────────┘                          └──────────┬───────────┘
         │                                                 │
         │                                                 │
         ▼                                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    Athena Query Engine                              │
├────────────────────────────────────────────────────────────────────┤
│  • noaa_gold_dev         (Production Data)                         │
│  • noaa_analytics_dev    (Aggregations - NEW)                      │
│  • noaa_ml_dev           (ML Features - NEW)                       │
└────────┬───────────────────────────────────────────────────────────┘
         │
         │
         ▼
┌────────────────────────────────────────────┐
│       Amazon QuickSight (NEW)              │
├────────────────────────────────────────────┤
│  • Operational Dashboard                   │
│  • Analytics Dashboard                     │
│  • Data Quality Dashboard                  │
│  • Real-time Streaming Metrics             │
└────────────────────────────────────────────┘
```

---

## Prerequisites

### Required AWS Services
- ✅ AWS Account: `899626030376`
- ✅ AWS Profile: `noaa-target`
- ✅ Region: `us-east-1`
- ✅ Existing Data Lake infrastructure deployed

### IAM Permissions Required
```json
{
  "Services": [
    "kinesis:*",
    "firehose:*",
    "glue:*",
    "athena:*",
    "quicksight:*",
    "cloudformation:*",
    "iam:CreateRole",
    "iam:AttachRolePolicy",
    "lambda:*",
    "s3:*"
  ]
}
```

### Software Requirements
- AWS CLI v2.x or higher
- Bash 4.0+
- Python 3.11+ (for local testing)
- jq (for JSON parsing)

### Verify Prerequisites
```bash
# Source environment
source config/environment.sh

# Validate environment
validate_environment

# Check existing infrastructure
./verify_complete_system.sh
```

---

## Enhancement 1: Real-Time Streaming

### Features

#### 🚀 High-Throughput Data Ingestion
- **Kinesis Data Streams** with configurable shards (default: 2 per stream)
- **Sub-second latency** from data source to S3
- **24-hour retention** with configurable extension up to 7 days
- **Encryption at rest** using AWS KMS

#### 📦 Components

| Component | Description | Configuration |
|-----------|-------------|---------------|
| `AtmosphericStream` | High-frequency atmospheric data | 2 shards, 24h retention |
| `OceanicStream` | Oceanic measurements | 2 shards, 24h retention |
| `BuoyStream` | Buoy telemetry | 2 shards, 24h retention |
| `StreamProcessor` | Lambda consumer | 100 records/batch, 5s window |
| `MetadataTable` | DynamoDB tracking | On-demand billing |

#### 🔄 Data Flow

```
NOAA API → Kinesis Stream → Lambda Processor → S3 Streaming Layer
                                              → DynamoDB Metadata
                                              → CloudWatch Metrics
```

#### 📁 S3 Storage Structure
```
s3://noaa-federated-lake-899626030376-dev/
  streaming/
    atmospheric/
      year=2024/
        month=12/
          day=10/
            2024-12-10T15:30:45.123456.json
            2024-12-10T15:30:46.789012.json
    oceanic/
      year=2024/...
    buoy/
      year=2024/...
```

### Deployment

#### Deploy Streaming Infrastructure
```bash
# Deploy only streaming
./deploy_enhancements.sh streaming

# Or deploy with custom parameters
aws cloudformation create-stack \
  --stack-name noaa-streaming-dev \
  --template-body file://real-time-streaming/streaming-infrastructure.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ShardCount,ParameterValue=2 \
    ParameterKey=RetentionHours,ParameterValue=24 \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile noaa-target
```

#### Verify Deployment
```bash
# Check stream status
aws kinesis describe-stream \
  --stream-name noaa-stream-atmospheric-dev \
  --profile noaa-target

# Test stream ingestion
aws kinesis put-record \
  --stream-name noaa-stream-atmospheric-dev \
  --partition-key test-001 \
  --data '{"station_id":"KBOS","temperature":72.5,"timestamp":"2024-12-10T15:30:00Z"}' \
  --profile noaa-target
```

### Configuration Options

#### Adjust Shard Count
```bash
# Scale up for higher throughput
aws kinesis update-shard-count \
  --stream-name noaa-stream-atmospheric-dev \
  --target-shard-count 4 \
  --scaling-type UNIFORM_SCALING \
  --profile noaa-target
```

#### Extend Retention Period
```bash
# Extend to 7 days (168 hours)
aws kinesis increase-stream-retention-period \
  --stream-name noaa-stream-atmospheric-dev \
  --retention-period-hours 168 \
  --profile noaa-target
```

### Monitoring

#### CloudWatch Metrics
- `GetRecords.IteratorAgeMilliseconds` - Processing lag
- `IncomingRecords` - Records per second
- `IncomingBytes` - Data throughput
- `WriteProvisionedThroughputExceeded` - Throttling events

#### Custom Metrics
- `NOAA/Streaming/RecordsProcessed` - Successfully processed records
- `NOAA/Streaming/ProcessingErrors` - Failed records

---

## Enhancement 2: Advanced Analytics Layer

### Features

#### 📊 Multi-Level Aggregations
- **Hourly aggregations** - Statistical summaries every hour
- **Daily aggregations** - Day-over-day analysis with percentiles
- **Monthly aggregations** - Long-term trends
- **Cross-pond analytics** - Correlation analysis across data sources

#### 🤖 ML-Ready Datasets
- **Feature engineering** - Time-series features, rolling averages
- **Training/validation splits** - Pre-partitioned datasets
- **Normalized data** - Standardized formats for ML models

#### 🔧 Components

| Component | Schedule | Workers | Purpose |
|-----------|----------|---------|---------|
| `HourlyAggregationJob` | Every hour | 5 x G.1X | Statistical summaries |
| `DailyAggregationJob` | Daily at 2:15 AM | 10 x G.1X | Daily reports & KPIs |
| `MLFeatureEngineeringJob` | After daily job | 15 x G.2X | ML feature creation |
| `CrossPondAnalyticsJob` | Weekly (Sunday 4 AM) | 20 x G.2X | Correlation analysis |

### Deployment

#### Deploy Analytics Infrastructure
```bash
# Deploy analytics layer
./deploy_enhancements.sh analytics

# Verify Glue databases
aws glue get-databases \
  --profile noaa-target \
  --query "DatabaseList[?Name=='noaa_analytics_dev' || Name=='noaa_ml_dev']"
```

#### Start Analytics Jobs Manually
```bash
# Run hourly aggregation
aws glue start-job-run \
  --job-name noaa-hourly-aggregation-dev \
  --profile noaa-target

# Run with custom date
aws glue start-job-run \
  --job-name noaa-daily-aggregation-dev \
  --arguments '{"--execution_date":"2024-12-09"}' \
  --profile noaa-target
```

### Analytics Workgroups

#### Athena Workgroups
```sql
-- Switch to analytics workgroup
USE noaa_analytics_dev;

-- Query hourly aggregates
SELECT 
  pond_name,
  aggregation_hour,
  record_count,
  avg_value,
  min_value,
  max_value
FROM hourly_aggregates
WHERE pond_name = 'atmospheric'
  AND aggregation_hour >= current_timestamp - interval '24' hour
ORDER BY aggregation_hour DESC;

-- Daily statistics with percentiles
SELECT 
  pond_name,
  aggregation_date,
  record_count,
  avg_value,
  percentile_25,
  percentile_50,
  percentile_75
FROM daily_aggregates
WHERE aggregation_date >= current_date - interval '30' day
ORDER BY aggregation_date DESC;
```

### ML Datasets

#### Feature Schema
```python
# ML Features Available
{
  "station_id": "string",
  "observation_time": "timestamp",
  "value": "double",
  "rolling_avg_7d": "double",      # 7-day rolling average
  "rolling_avg_1d": "double",      # 1-day rolling average
  "rolling_std_7d": "double",      # 7-day rolling std dev
  "hour_of_day": "int",            # 0-23
  "day_of_week": "int",            # 1-7
  "month": "int",                  # 1-12
  "year": "int",
  "month": "int"                   # Partition keys
}
```

#### Query ML Features
```sql
-- Use ML database
USE noaa_ml_dev;

-- Retrieve features for training
SELECT *
FROM features
WHERE year = 2024
  AND month >= 11
ORDER BY observation_time;
```

---

## Enhancement 3: QuickSight Dashboards

### Features

#### 📊 Dashboard Types

1. **Operational Dashboard**
   - Real-time ingestion metrics
   - Data quality indicators
   - System health status
   - Pond-by-pond breakdowns

2. **Analytics Dashboard**
   - Hourly/daily trends
   - Statistical distributions
   - Comparative analysis
   - Historical patterns

3. **Data Quality Dashboard**
   - Completeness scores
   - Timeliness metrics
   - Validation results
   - Error tracking

### Deployment

#### Prerequisites
```bash
# Enable QuickSight (one-time setup)
# Visit: https://quicksight.aws.amazon.com/

# Create QuickSight user
aws quicksight register-user \
  --aws-account-id 899626030376 \
  --namespace default \
  --identity-type IAM \
  --iam-arn "arn:aws:iam::899626030376:role/noaa-quicksight-user" \
  --user-role ADMIN \
  --email your-email@domain.com \
  --profile noaa-target \
  --region us-east-1
```

#### Deploy Dashboards
```bash
# Deploy QuickSight infrastructure
./deploy_enhancements.sh quicksight

# Get dashboard URL
aws cloudformation describe-stacks \
  --stack-name noaa-quicksight-dev \
  --profile noaa-target \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardURL'].OutputValue" \
  --output text
```

### Dashboard Configuration

#### Data Refresh Schedule
```bash
# Set up automated refresh (via AWS Console or CLI)
aws quicksight create-data-set-refresh-properties \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --data-set-refresh-properties '{
    "RefreshConfiguration": {
      "IncrementalRefresh": {
        "LookbackWindow": {
          "ColumnName": "observation_time",
          "Size": 1,
          "SizeUnit": "HOUR"
        }
      }
    }
  }' \
  --profile noaa-target \
  --region us-east-1
```

#### Custom Visualizations

**KPI Cards:**
- Total records processed (24h)
- Average processing latency
- Data quality score
- Active streams

**Line Charts:**
- Records per hour by pond
- Processing time trends
- Error rate over time

**Bar Charts:**
- Records by data source
- Data quality by pond
- Storage growth

**Geo Maps:**
- Station locations
- Data coverage heatmap

### Sharing Dashboards

#### Grant Access
```bash
# Share dashboard with users
aws quicksight update-dashboard-permissions \
  --aws-account-id 899626030376 \
  --dashboard-id noaa-operational-dashboard-dev \
  --grant-permissions Principal=arn:aws:quicksight:us-east-1:899626030376:user/default/analyst,Actions=quicksight:DescribeDashboard,quicksight:QueryDashboard \
  --profile noaa-target \
  --region us-east-1
```

#### Embed in Applications
```python
# Python example for embedding
import boto3

quicksight = boto3.client('quicksight')

response = quicksight.generate_embed_url_for_registered_user(
    AwsAccountId='899626030376',
    ExperienceConfiguration={
        'Dashboard': {
            'InitialDashboardId': 'noaa-operational-dashboard-dev'
        }
    },
    UserArn='arn:aws:quicksight:us-east-1:899626030376:user/default/admin'
)

print(response['EmbedUrl'])
```

---

## Deployment Instructions

### Quick Start - Deploy All Enhancements

```bash
# 1. Clone repository and navigate to project
cd noaa_storefront

# 2. Source environment configuration
source config/environment.sh

# 3. Make deployment script executable
chmod +x deploy_enhancements.sh

# 4. Deploy all enhancements
./deploy_enhancements.sh all
```

### Individual Component Deployment

```bash
# Deploy only streaming
./deploy_enhancements.sh streaming

# Deploy only analytics
./deploy_enhancements.sh analytics

# Deploy only QuickSight
./deploy_enhancements.sh quicksight
```

### Verification Steps

```bash
# 1. Check CloudFormation stacks
aws cloudformation describe-stacks \
  --profile noaa-target \
  --query "Stacks[?contains(StackName, 'noaa-streaming') || contains(StackName, 'noaa-analytics') || contains(StackName, 'noaa-quicksight')].{Name:StackName,Status:StackStatus}" \
  --output table

# 2. Verify Kinesis streams
aws kinesis list-streams \
  --profile noaa-target \
  --output table

# 3. Verify Glue jobs
aws glue list-jobs \
  --profile noaa-target \
  --query "JobNames[?contains(@, 'noaa-')]" \
  --output table

# 4. Verify Athena databases
aws athena list-databases \
  --catalog-name AwsDataCatalog \
  --profile noaa-target \
  --region us-east-1

# 5. Test QuickSight access
aws quicksight list-dashboards \
  --aws-account-id 899626030376 \
  --profile noaa-target \
  --region us-east-1
```

---

## Configuration

### Environment Variables

All configurations are managed in `config/environment.sh`:

```bash
# Streaming Configuration
export KINESIS_SHARD_COUNT=2
export KINESIS_RETENTION_HOURS=24
export STREAM_BATCH_SIZE=100
export STREAM_BATCH_WINDOW=5

# Analytics Configuration
export HOURLY_AGG_WORKERS=5
export DAILY_AGG_WORKERS=10
export ML_FEATURE_WORKERS=15
export CROSS_POND_WORKERS=20

# QuickSight Configuration
export QUICKSIGHT_EDITION="ENTERPRISE"
export QUICKSIGHT_REFRESH_INTERVAL="1h"
```

### Scaling Configurations

#### Kinesis Scaling
```bash
# Auto-scaling based on throughput
# Create application autoscaling target
aws application-autoscaling register-scalable-target \
  --service-namespace kinesis \
  --scalable-dimension kinesis:stream:ShardCount \
  --resource-id stream/noaa-stream-atmospheric-dev \
  --min-capacity 2 \
  --max-capacity 10 \
  --profile noaa-target
```

#### Glue Job Tuning
```bash
# Adjust worker count for heavy processing
aws glue update-job \
  --job-name noaa-daily-aggregation-dev \
  --job-update '{
    "NumberOfWorkers": 20,
    "WorkerType": "G.2X",
    "MaxRetries": 3
  }' \
  --profile noaa-target
```

---

## Usage Examples

### Example 1: Stream Real-Time Data

```python
import boto3
import json
from datetime import datetime

kinesis = boto3.client('kinesis', region_name='us-east-1')

# Prepare atmospheric data
data = {
    'station_id': 'KBOS',
    'temperature': 72.5,
    'pressure': 1013.25,
    'humidity': 65,
    'wind_speed': 15.2,
    'timestamp': datetime.utcnow().isoformat()
}

# Send to Kinesis
response = kinesis.put_record(
    StreamName='noaa-stream-atmospheric-dev',
    Data=json.dumps(data),
    PartitionKey=data['station_id']
)

print(f"Sequence Number: {response['SequenceNumber']}")
```

### Example 2: Query Analytics Data

```python
import boto3
import time

athena = boto3.client('athena', region_name='us-east-1')

query = """
SELECT 
    pond_name,
    DATE_TRUNC('hour', aggregation_hour) as hour,
    AVG(avg_value) as avg_temp,
    MAX(max_value) as max_temp,
    MIN(min_value) as min_temp
FROM noaa_analytics_dev.hourly_aggregates
WHERE pond_name = 'atmospheric'
  AND aggregation_hour >= current_timestamp - interval '24' hour
GROUP BY pond_name, DATE_TRUNC('hour', aggregation_hour)
ORDER BY hour DESC
"""

response = athena.start_query_execution(
    QueryString=query,
    QueryExecutionContext={'Database': 'noaa_analytics_dev'},
    ResultConfiguration={
        'OutputLocation': 's3://noaa-athena-results-899626030376-dev/analytics/'
    },
    WorkGroup='noaa-analytics-dev'
)

query_execution_id = response['QueryExecutionId']

# Wait for query to complete
while True:
    result = athena.get_query_execution(QueryExecutionId=query_execution_id)
    state = result['QueryExecution']['Status']['State']
    
    if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
        break
    
    time.sleep(1)

# Get results
if state == 'SUCCEEDED':
    results = athena.get_query_results(QueryExecutionId=query_execution_id)
    for row in results['ResultSet']['Rows'][1:]:  # Skip header
        print(row['Data'])
```

### Example 3: Trigger ML Feature Engineering

```python
import boto3

glue = boto3.client('glue', region_name='us-east-1')

# Start ML feature engineering job
response = glue.start_job_run(
    JobName='noaa-ml-feature-engineering-dev',
    Arguments={
        '--execution_time': datetime.utcnow().isoformat(),
        '--lookback_days': '30',
        '--feature_sets': 'temporal,statistical,geospatial'
    }
)

print(f"Job Run ID: {response['JobRunId']}")

# Monitor job progress
while True:
    status = glue.get_job_run(
        JobName='noaa-ml-feature-engineering-dev',
        RunId=response['JobRunId']
    )
    
    state = status['JobRun']['JobRunState']
    print(f"Job State: {state}")
    
    if state in ['SUCCEEDED', 'FAILED', 'STOPPED']:
        break
    
    time.sleep(10)
```

---

## Monitoring & Troubleshooting

### CloudWatch Dashboards

Access pre-configured dashboards:
- **Streaming Metrics**: https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Streaming-dev
- **Analytics Metrics**: https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Analytics-dev
- **QuickSight Metrics**: https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-QuickSight-Metrics-dev

### Key Metrics to Monitor

#### Streaming Health
```bash
# Check iterator age (should be < 60 seconds)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Kinesis \
  --metric-name GetRecords.IteratorAgeMilliseconds \
  --dimensions Name=StreamName,Value=noaa-stream-atmospheric-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --profile noaa-target
```

#### Analytics Job Status
```bash
# Check Glue job runs
aws glue get-job-runs \
  --job-name noaa-hourly-aggregation-dev \
  --profile noaa-target \
  --query "JobRuns[0:5].{StartedOn:StartedOn,Status:JobRunState,Duration:ExecutionTime}"
```

### Common Issues & Solutions

#### Issue 1: Stream Iterator Age Growing

**Symptom**: `GetRecords.IteratorAgeMilliseconds` > 60000

**Solution**:
```bash
# Scale up shards
aws kinesis update-shard-count \
  --stream-name noaa-stream-atmospheric-dev \
  --target-shard-count 4 \
  --scaling-type UNIFORM_SCALING \
  --profile noaa-target

# Or increase Lambda concurrency
aws lambda put-function-concurrency \
  --function-name noaa-stream-processor-atmospheric-dev \
  --reserved-concurrent-executions 10 \
  --profile noaa-target
```

#### Issue 2: Glue Job Failures

**Symptom**: Job state = FAILED

**Solution**:
```bash
# View job logs
aws logs tail /aws-glue/jobs/output \
  --follow \
  --format short \
  --filter-pattern "noaa-hourly-aggregation-dev" \
  --profile noaa-target

# Common fixes:
# 1. Increase workers
# 2. Add more memory (switch to G.2X)
# 3. Check S3 permissions
```

#### Issue 3: QuickSight Data Not Refreshing

**Symptom**: Dashboard shows stale data

**Solution**:
```bash
# Manually trigger dataset refresh
aws quicksight create-ingestion \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --ingestion-id manual-refresh-$(date +%s) \
  --profile noaa-target \
  --region us-east-1

# Check refresh status
aws quicksight list-ingestions \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --profile noaa-target \
  --region us-east-1
```

### Alerts Configuration

```bash
# Create SNS topic for alerts
aws sns create-topic \
  --name noaa-enhancements-alerts \
  --profile noaa-target

# Subscribe to alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:899626030376:noaa-enhancements-alerts \
  --protocol email \
  --notification-endpoint your-email@domain.com \
  --profile noaa-target

# Alarms are automatically created by CloudFormation stacks
```

---

## Cost Analysis

### Monthly Cost Breakdown

#### Real-Time Streaming
| Service | Resource | Usage | Cost |
|---------|----------|-------|------|
| Kinesis Data Streams | 6 shards total | 720 hours | ~$86.40 |
| Lambda (Processors) | 3 functions | 500K invocations | ~$5.00 |
| DynamoDB | Metadata table | On-demand | ~$2.50 |
| Data Transfer | Stream to S3 | 100 GB | ~$0.90 |
| **Subtotal** | | | **~$94.80** |

#### Advanced Analytics
| Service | Resource | Usage | Cost |
|---------|----------|-------|------|
| Glue Jobs | Hourly (5 workers) | 720 runs/month | ~$86.40 |
| Glue Jobs | Daily (10 workers) | 30 runs/month | ~$36.00 |
| Glue Jobs | ML Features (15 workers) | 30 runs/month | ~$81.00 |
| Glue Jobs | Cross-pond (20 workers) | 4 runs/month | ~$36.00 |
| Glue Crawlers | 2 crawlers | 248 runs/month | ~$4.96 |
| Athena Queries | Analytics workgroup | 1 TB scanned | ~$5.00 |
| **Subtotal** | | | **~$249.36** |

#### QuickSight Dashboards
| Service | Resource | Usage | Cost |
|---------|----------|-------|------|
| QuickSight Enterprise | Per user/month | 5 authors | ~$90.00 |
| QuickSight Enterprise | Per user/month | 20 readers | ~$50.00 |
| SPICE Capacity | 10 GB | Monthly | ~$2.50 |
| **Subtotal** | | | **~$142.50** |

### Total Enhanced Features Cost
**Estimated Monthly Cost: $486.66**

### Cost Optimization Tips

1. **Use Glue Job Bookmarks**: Reduce redundant processing
2. **Optimize Shard Count**: Start with 1 shard per stream
3. **Use QuickSight Reader Sessions**: Pay-per-session for occasional users
4. **Enable S3 Intelligent-Tiering**: Move old streaming data to cheaper storage
5. **Schedule Jobs Efficiently**: Run heavy jobs during off-peak hours

---

## Best Practices

### Real-Time Streaming

✅ **DO:**
- Use partition keys that distribute load evenly
- Implement exponential backoff for retries
- Monitor iterator age closely
- Archive streaming data to Glacier after 30 days

❌ **DON'T:**
- Use single partition key for all records
- Ignore throttling errors
- Store uncompressed data
- Keep raw streaming data indefinitely

### Analytics Layer

✅ **DO:**
- Use job bookmarks to avoid reprocessing
- Partition data by date (year/month/day)
- Cache intermediate results
- Monitor job execution time trends

❌ **DON'T:**
- Process entire datasets every run
- Skip data quality checks
- Ignore failed job alerts