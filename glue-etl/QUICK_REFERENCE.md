# NOAA Glue ETL Pipeline - Quick Reference

**Status:** ✅ Operational | **Environment:** dev | **Region:** us-east-1

---

## 🚀 Quick Start (3 Commands)

```bash
# 1. Navigate to ETL directory
cd noaa_storefront/glue-etl

# 2. Convert data (local Python - fastest)
python3 local_convert.py --pond atmospheric --data-type observations --max-files 50

# 3. Run crawler to catalog
aws glue start-crawler --name noaa-queryable-atmospheric-crawler-dev
```

**Wait 2 minutes, then query in Athena!**

---

## 📊 Query Data (Athena)

### AWS Console
```
https://console.aws.amazon.com/athena/home?region=us-east-1
Database: noaa_queryable_dev
```

### Example Queries

**Boston Weather:**
```sql
SELECT station_id, hour, avg_temperature, avg_wind_speed
FROM noaa_queryable_dev.observations
WHERE station_id = 'KBOS'
ORDER BY hour DESC LIMIT 10;
```

**Maritime Route (Boston to Portland):**
```sql
SELECT station_id, hour, avg_temperature, avg_wind_speed, max_wind_speed
FROM noaa_queryable_dev.observations
WHERE station_id IN ('KBOS', 'KPWM', 'KCON', 'KRKD')
  AND year = 2025 AND month = 11
ORDER BY station_id, hour DESC;
```

**Count Records:**
```sql
SELECT COUNT(*) as total_records 
FROM noaa_queryable_dev.observations;
```

**List All Stations:**
```sql
SELECT DISTINCT station_id 
FROM noaa_queryable_dev.observations 
ORDER BY station_id;
```

---

## 🔄 Convert Data

### Local Python Converter (Recommended)

```bash
# Convert specific pond and data type
python3 local_convert.py --pond atmospheric --data-type observations

# Convert all data in a pond
python3 local_convert.py --pond oceanic --data-type all

# Convert limited files (testing)
python3 local_convert.py --pond atmospheric --data-type observations --max-files 10

# Dry run (don't upload)
python3 local_convert.py --pond atmospheric --dry-run

# Convert multiple ponds
python3 local_convert.py --pond atmospheric --pond oceanic --data-type all
```

**Available Ponds:**
- `atmospheric` - Weather observations, stations, alerts
- `oceanic` - Water levels, temperatures, currents
- `buoy` - Wave heights, sea state
- `climate` - Historical climate data
- `spatial` - Geographic zones
- `terrestrial` - Land-based observations

**Available Data Types:**
- `observations` - Hourly weather observations
- `stations` - Station metadata
- `alerts` - Weather alerts
- `all` - All data types in pond

### AWS Glue ETL Jobs

```bash
# Trigger job
aws glue start-job-run --job-name noaa-etl-atmospheric-observations-dev

# Check status
aws glue get-job-runs \
  --job-name noaa-etl-atmospheric-observations-dev \
  --max-results 1 \
  --query 'JobRuns[0].{Status:JobRunState,Duration:ExecutionTime}'

# View logs
aws logs tail /aws-glue/jobs/output --follow
```

---

## 🕷️ Run Crawlers

```bash
# Start crawler
aws glue start-crawler --name noaa-queryable-atmospheric-crawler-dev

# Check status
aws glue get-crawler --name noaa-queryable-atmospheric-crawler-dev \
  --query 'Crawler.{State:State,LastRunStatus:LastCrawl.Status}'

# Start all crawlers
for crawler in atmospheric oceanic buoy; do
  aws glue start-crawler --name noaa-queryable-${crawler}-crawler-dev
done
```

---

## 🔍 Check Data

### S3 Data

```bash
# Check source (Gold layer - JSON arrays)
aws s3 ls s3://noaa-data-lake-dev/gold/atmospheric/observations/ --recursive | tail -10

# Check converted (Queryable layer - JSON Lines)
aws s3 ls s3://noaa-data-lake-dev/queryable/atmospheric/observations/ --recursive | tail -10

# Count files
aws s3 ls s3://noaa-data-lake-dev/queryable/ --recursive | wc -l
```

### Glue Catalog

```bash
# List databases
aws glue get-databases --query 'DatabaseList[].Name'

# List tables in database
aws glue get-tables --database-name noaa_queryable_dev \
  --query 'TableList[].Name' --output table

# Get table schema
aws glue get-table --database-name noaa_queryable_dev \
  --name observations \
  --query 'Table.StorageDescriptor.Columns[*].[Name,Type]' \
  --output table

# Count partitions
aws glue get-partitions --database-name noaa_queryable_dev \
  --table-name observations \
  --query 'length(Partitions)'
```

### Athena Queries

```bash
# Run query via CLI
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_queryable_dev.observations" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --query-execution-context "Database=noaa_queryable_dev" \
  --query 'QueryExecutionId' --output text)

# Wait and get results
sleep 5
aws athena get-query-results --query-execution-id $QUERY_ID

# Check query status
aws athena get-query-execution --query-execution-id $QUERY_ID \
  --query 'QueryExecution.Status'
```

---

## 🛠️ Troubleshooting

### Query Returns 0 Records

```bash
# 1. Check if data exists in S3
aws s3 ls s3://noaa-data-lake-dev/queryable/atmospheric/observations/ --recursive

# 2. Repair table partitions
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE noaa_queryable_dev.observations" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --query-execution-context "Database=noaa_queryable_dev"

# 3. Re-run crawler
aws glue start-crawler --name noaa-queryable-atmospheric-crawler-dev
```

### Crawler Fails

```bash
# Check crawler status
aws glue get-crawler --name noaa-queryable-atmospheric-crawler-dev

# View crawler logs
aws logs tail /aws-glue/crawlers --since 1h
```

### No Source Data

```bash
# Trigger ingestion Lambda
aws lambda invoke \
  --function-name noaa-ingest-atmospheric-dev \
  --payload '{"mode":"incremental","hours_back":24}' \
  response.json

# Check Lambda logs
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev --since 30m
```

---

## 📈 Monitoring

### CloudFormation Stack

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name noaa-glue-etl-pipeline-dev \
  --query 'Stacks[0].StackStatus'

# List stack resources
aws cloudformation list-stack-resources \
  --stack-name noaa-glue-etl-pipeline-dev \
  --query 'StackResourceSummaries[*].[ResourceType,LogicalResourceId,ResourceStatus]' \
  --output table
```

### Glue Job Metrics

```bash
# Recent job runs
aws glue get-job-runs \
  --job-name noaa-etl-atmospheric-observations-dev \
  --max-results 5 \
  --query 'JobRuns[*].[StartedOn,JobRunState,ExecutionTime]' \
  --output table

# Failed jobs
aws glue get-job-runs \
  --job-name noaa-etl-atmospheric-observations-dev \
  --query 'JobRuns[?JobRunState==`FAILED`]' \
  --output table
```

### Cost Monitoring

```bash
# Glue job costs (last 7 days)
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://<(echo '{"Dimensions":{"Key":"SERVICE","Values":["AWS Glue"]}}')

# S3 storage size
aws s3 ls s3://noaa-data-lake-dev/queryable/ --recursive --summarize | tail -2
```

---

## 🔄 Full Pipeline Execution

```bash
#!/bin/bash
# Complete end-to-end data pipeline

# 1. Trigger ingestion (if needed)
aws lambda invoke \
  --function-name noaa-ingest-atmospheric-dev \
  --payload '{"mode":"incremental","hours_back":6}' \
  /tmp/response.json

# 2. Wait for ingestion
sleep 120

# 3. Convert data
python3 local_convert.py --pond atmospheric --data-type observations --max-files 50

# 4. Convert oceanic
python3 local_convert.py --pond oceanic --data-type all --max-files 20

# 5. Run crawlers
aws glue start-crawler --name noaa-queryable-atmospheric-crawler-dev
aws glue start-crawler --name noaa-queryable-oceanic-crawler-dev

# 6. Wait for crawlers
sleep 120

# 7. Test query
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_queryable_dev.observations" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --query-execution-context "Database=noaa_queryable_dev"

echo "✅ Pipeline complete! Query data in Athena."
```

---

## 🌍 Multi-Environment

```bash
# Deploy to staging
cd noaa_storefront/glue-etl
./deploy-etl-pipeline.sh staging

# Convert data in production
python3 local_convert.py --pond atmospheric --environment prod

# Query production database
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_queryable_prod.observations LIMIT 10" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-prod/" \
  --query-execution-context "Database=noaa_queryable_prod"
```

---

## 📝 Environment Variables

```bash
export AWS_REGION=us-east-1
export ENV=dev
export DATA_LAKE_BUCKET=noaa-data-lake-${ENV}
export ATHENA_OUTPUT=s3://noaa-athena-results-899626030376-${ENV}/
export QUERYABLE_DB=noaa_queryable_${ENV}
```

---

## 🔗 Quick Links

| Resource | URL |
|----------|-----|
| Athena Console | https://console.aws.amazon.com/athena/home?region=us-east-1 |
| Glue Console | https://console.aws.amazon.com/glue/home?region=us-east-1 |
| S3 Console | https://s3.console.aws.amazon.com/s3/buckets/noaa-data-lake-dev |
| CloudFormation | https://console.aws.amazon.com/cloudformation/home?region=us-east-1 |
| CloudWatch Logs | https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups |

---

## 📚 Documentation

- **Full README:** `noaa_storefront/glue-etl/README.md`
- **Deployment Guide:** `noaa_storefront/glue-etl/DEPLOYMENT_SUCCESS.md`
- **ETL Script:** `noaa_storefront/glue-etl/json_array_to_jsonlines.py`
- **Converter:** `noaa_storefront/glue-etl/local_convert.py`

---

**Last Updated:** 2025-11-18  
**Version:** 1.0  
**Status:** ✅ Production Ready