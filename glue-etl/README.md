# NOAA Federated Data Lake - Glue ETL Pipeline

## 🎯 Overview

This Glue ETL pipeline automatically converts NOAA data from **JSON array format** to **JSON Lines format** (newline-delimited JSON), making it queryable via Amazon Athena.

### The Problem

The NOAA ingestion Lambda functions write data as JSON arrays:
```json
[
  {"station_id": "KBOS", "temperature": 5.5, "hour": "2025-11-17T00"},
  {"station_id": "KJFK", "temperature": 6.8, "hour": "2025-11-17T00"}
]
```

However, Athena's JSON SerDe expects **JSON Lines format**:
```json
{"station_id": "KBOS", "temperature": 5.5, "hour": "2025-11-17T00"}
{"station_id": "KJFK", "temperature": 6.8, "hour": "2025-11-17T00"}
```

### The Solution

This automated pipeline:
1. ✅ Reads JSON array files from the Gold layer
2. ✅ Explodes arrays into individual records
3. ✅ Writes as JSON Lines to a "queryable" layer
4. ✅ Catalogs the data with Glue crawlers
5. ✅ Makes everything queryable via Athena
6. ✅ Runs automatically every 15 minutes

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     NOAA Data Lake Pipeline                      │
└─────────────────────────────────────────────────────────────────┘

INGESTION LAYER (Lambda Functions)
    ↓
GOLD LAYER (JSON Arrays)
s3://noaa-data-lake-dev/gold/atmospheric/observations/
    └─ data_20251117_003518.json  [{...}, {...}, {...}]
    
    ↓ Glue ETL Job (Auto-triggered every 15 min)
    
QUERYABLE LAYER (JSON Lines)
s3://noaa-data-lake-dev/queryable/atmospheric/observations/
    └─ year=2025/month=11/day=17/
        └─ part-00000.json  {...}\n{...}\n{...}
    
    ↓ Glue Crawler (Auto-runs every 30 min)
    
ATHENA TABLES (noaa_queryable_dev database)
    └─ observations
    └─ stations
    └─ alerts
```

---

## 📦 Components

### 1. Glue ETL Script
**File:** `json_array_to_jsonlines.py`

- Reads JSON array files from S3
- Uses PySpark to explode arrays
- Preserves partitioning (year/month/day)
- Writes as JSON Lines format
- Handles schema variations gracefully

### 2. CloudFormation Stack
**File:** `glue-etl-stack.yaml`

Deploys:
- **5 Glue ETL Jobs** (one per data type)
- **3 Glue Crawlers** (to catalog queryable data)
- **6 EventBridge Rules** (automatic triggers)
- **IAM Roles** (with least-privilege permissions)
- **Glue Database** (`noaa_queryable_dev`)

### 3. Deployment Script
**File:** `deploy-etl-pipeline.sh`

Automates:
- S3 bucket creation
- Script uploads
- CloudFormation deployment
- Initial ETL job execution
- Crawler runs

---

## 🚀 Quick Start Deployment

### Prerequisites

✅ AWS CLI configured with appropriate credentials  
✅ Existing NOAA data lake with ingestion running  
✅ Bash shell (macOS/Linux/WSL)

### Deploy in 3 Commands

```bash
# 1. Navigate to the Glue ETL directory
cd noaa_storefront/glue-etl

# 2. Make the deployment script executable
chmod +x deploy-etl-pipeline.sh

# 3. Deploy the pipeline
./deploy-etl-pipeline.sh dev
```

**Deployment time:** ~5 minutes  
**First data available:** ~8 minutes after deployment

---

## 📊 Deployed Resources

### Glue ETL Jobs

| Job Name | Description | Trigger | Runtime |
|----------|-------------|---------|---------|
| `noaa-etl-atmospheric-observations-dev` | Convert atmospheric observations | Every 15 min | ~3 min |
| `noaa-etl-atmospheric-stations-dev` | Convert station metadata | Every 1 hour | ~1 min |
| `noaa-etl-atmospheric-alerts-dev` | Convert weather alerts | Every 15 min | ~1 min |
| `noaa-etl-oceanic-dev` | Convert oceanic data | Every 15 min | ~3 min |
| `noaa-etl-buoy-dev` | Convert buoy data | Every 15 min | ~3 min |

### Glue Crawlers

| Crawler Name | Target | Schedule |
|--------------|--------|----------|
| `noaa-queryable-atmospheric-crawler-dev` | Queryable atmospheric data | Every 30 min |
| `noaa-queryable-oceanic-crawler-dev` | Queryable oceanic data | Every 30 min |
| `noaa-queryable-buoy-crawler-dev` | Queryable buoy data | Every 30 min |

### Athena Database

**Database:** `noaa_queryable_dev`

**Tables Created:**
- `observations` - Hourly atmospheric observations
- `stations` - Weather station metadata
- `alerts` - Active weather alerts
- `water_level` - Oceanic water levels
- `water_temperature` - Ocean temperatures
- `wind` - Wind observations
- `air_temperature` - Air temperature
- `air_pressure` - Barometric pressure

---

## 🔍 Querying Data with Athena

### AWS Console Method

1. Go to **AWS Athena Console**: https://console.aws.amazon.com/athena/
2. Select database: `noaa_queryable_dev`
3. Run your SQL queries!

### Example Queries

#### Get Current Weather in Boston
```sql
SELECT 
    station_id,
    hour,
    avg_temperature,
    avg_wind_speed,
    max_wind_speed
FROM noaa_queryable_dev.observations
WHERE station_id = 'KBOS'
  AND year = 2025
  AND month = 11
ORDER BY hour DESC
LIMIT 10;
```

#### Maritime Route Planning (Boston to Portland)
```sql
SELECT 
    station_id,
    hour,
    avg_temperature,
    avg_wind_speed,
    max_wind_speed
FROM noaa_queryable_dev.observations
WHERE station_id IN ('KBOS', 'KPWM', 'KCON', 'KRKD')
  AND year = 2025
  AND month = 11
  AND day = 17
ORDER BY station_id, hour DESC;
```

#### Check Active Weather Alerts
```sql
SELECT 
    event,
    headline,
    severity,
    areas,
    onset,
    expires
FROM noaa_queryable_dev.alerts
WHERE year = 2025
  AND severity IN ('Severe', 'Extreme')
ORDER BY onset DESC;
```

#### Ocean Conditions Along Coast
```sql
SELECT 
    station_id,
    product,
    hour,
    avg_value,
    max_value,
    min_value
FROM noaa_queryable_dev.water_level
WHERE year = 2025
  AND month = 11
  AND day = 17
ORDER BY hour DESC
LIMIT 20;
```

### AWS CLI Method

```bash
# Set environment
export ENV=dev
export AWS_REGION=us-east-1

# Run a query
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_queryable_${ENV}.observations LIMIT 10" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-${ENV}/" \
  --query-execution-context "Database=noaa_queryable_${ENV}" \
  --query 'QueryExecutionId' \
  --output text)

# Wait for completion
sleep 5

# Get results
aws athena get-query-results --query-execution-id $QUERY_ID
```

---

## 🔧 Manual Operations

### Trigger ETL Job Manually

```bash
aws glue start-job-run \
  --job-name "noaa-etl-atmospheric-observations-dev" \
  --region us-east-1
```

### Run Crawler Manually

```bash
aws glue start-crawler \
  --name "noaa-queryable-atmospheric-crawler-dev" \
  --region us-east-1
```

### Check ETL Job Status

```bash
aws glue get-job-runs \
  --job-name "noaa-etl-atmospheric-observations-dev" \
  --max-results 5 \
  --region us-east-1
```

### View ETL Job Logs

```bash
aws logs tail /aws-glue/jobs/output \
  --follow \
  --region us-east-1 \
  --log-stream-name-prefix "noaa-etl-atmospheric"
```

---

## 🎛️ Configuration

### Modify ETL Schedule

Edit the CloudFormation parameter `ETLSchedule`:

```bash
aws cloudformation update-stack \
  --stack-name "noaa-glue-etl-pipeline-dev" \
  --use-previous-template \
  --parameters \
    ParameterKey=Environment,UsePreviousValue=true \
    ParameterKey=DataLakeBucket,UsePreviousValue=true \
    ParameterKey=GlueScriptBucket,UsePreviousValue=true \
    ParameterKey=EnableAutoTrigger,UsePreviousValue=true \
    ParameterKey=ETLSchedule,ParameterValue="rate(10 minutes)" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Disable Automatic Triggers

```bash
# Disable via CloudFormation parameter
aws cloudformation update-stack \
  --stack-name "noaa-glue-etl-pipeline-dev" \
  --use-previous-template \
  --parameters \
    ParameterKey=Environment,UsePreviousValue=true \
    ParameterKey=DataLakeBucket,UsePreviousValue=true \
    ParameterKey=GlueScriptBucket,UsePreviousValue=true \
    ParameterKey=EnableAutoTrigger,ParameterValue="false" \
    ParameterKey=ETLSchedule,UsePreviousValue=true \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Update ETL Script

```bash
# 1. Modify json_array_to_jsonlines.py locally

# 2. Upload new version
aws s3 cp json_array_to_jsonlines.py \
  s3://noaa-glue-scripts-dev/glue-etl/json_array_to_jsonlines.py

# 3. Jobs will automatically use the new version on next run
```

---

## 🌍 Cross-Region / Multi-Environment Deployment

### Deploy to Different Region

```bash
export AWS_REGION=us-west-2
./deploy-etl-pipeline.sh dev
```

### Deploy to Staging Environment

```bash
./deploy-etl-pipeline.sh staging
```

### Deploy to Production

```bash
./deploy-etl-pipeline.sh prod
```

Each environment gets:
- Isolated S3 buckets
- Separate Glue jobs and crawlers
- Independent EventBridge schedules
- Distinct Athena databases

---

## 📈 Monitoring & Observability

### CloudWatch Metrics

**View in Console:**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#metricsV2:graph=~()
```

**Key Metrics:**
- `glue.driver.aggregate.numCompletedStages` - Completed Spark stages
- `glue.driver.aggregate.numFailedTasks` - Failed tasks
- `glue.ALL.s3.filesystem.read_bytes` - Data read from S3
- `glue.ALL.s3.filesystem.write_bytes` - Data written to S3

### CloudWatch Dashboards

Monitor all ETL jobs in one place:

```bash
# Create a custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "NOAA-ETL-Pipeline-dev" \
  --dashboard-body file://dashboard-config.json
```

### SNS Alerts (Optional)

Set up notifications for job failures:

```bash
# Create SNS topic
aws sns create-topic --name noaa-etl-alerts-dev

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:noaa-etl-alerts-dev \
  --protocol email \
  --notification-endpoint your-email@example.com

# Add to CloudFormation stack (see stack YAML)
```

---

## 🛠️ Troubleshooting

### Issue: No Data Appearing in Queryable Layer

**Diagnosis:**
```bash
# Check if source data exists
aws s3 ls s3://noaa-data-lake-dev/gold/atmospheric/observations/ --recursive | tail -10

# Check ETL job status
aws glue get-job-runs \
  --job-name "noaa-etl-atmospheric-observations-dev" \
  --max-results 1
```

**Solution:**
- Ensure ingestion Lambdas are running
- Check Glue job logs for errors
- Verify S3 permissions on GlueETLRole

### Issue: Athena Queries Return Zero Results

**Diagnosis:**
```bash
# Check if queryable data exists
aws s3 ls s3://noaa-data-lake-dev/queryable/atmospheric/observations/ --recursive | tail -10

# Check if crawler has run
aws glue get-crawler \
  --name "noaa-queryable-atmospheric-crawler-dev"
```

**Solution:**
```bash
# Manually repair table partitions
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE noaa_queryable_dev.observations" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --query-execution-context "Database=noaa_queryable_dev"
```

### Issue: ETL Job Fails with Schema Error

**Diagnosis:**
Check logs for:
```
FAILED: SemanticException Schema mismatch
```

**Solution:**
The JSON array structure changed. Update the schema in `json_array_to_jsonlines.py`:

```python
SCHEMAS = {
    "atmospheric_observations": StructType([
        # Add/modify fields here
        StructField("new_field", StringType(), True),
    ]),
}
```

### Issue: High Glue Costs

**Diagnosis:**
```bash
# Check job DPU usage
aws glue get-job-runs \
  --job-name "noaa-etl-atmospheric-observations-dev" \
  --query 'JobRuns[0].[AllocatedCapacity,ExecutionTime]'
```

**Solution:**
- Reduce `MaxCapacity` in CloudFormation (default: 2.0 DPU)
- Increase ETL schedule interval (e.g., from 15 min to 30 min)
- Enable S3 Select to pre-filter data

---

## 💰 Cost Optimization

### Current Cost Estimate (per month)

**Glue ETL:**
- 5 jobs × 4 runs/hour × 3 min × $0.44/DPU-hour × 2 DPU = ~$800/month
- Can be reduced by adjusting schedules

**Glue Crawlers:**
- 3 crawlers × 2 runs/hour × 10 seconds = Minimal (~$5/month)

**S3 Storage:**
- Queryable layer is same size as Gold layer
- With lifecycle policies: ~$20/month for 100GB

**Athena Queries:**
- Pay per query: $5 per TB scanned
- Partitioning reduces costs significantly

### Optimization Tips

1. **Reduce ETL Frequency:**
   ```yaml
   ETLSchedule: 'rate(30 minutes)'  # Instead of 15 min
   ```

2. **Use Smaller DPU Allocation:**
   ```yaml
   MaxCapacity: 1.0  # Instead of 2.0
   ```

3. **Enable S3 Lifecycle Policies:**
   ```bash
   # Move queryable data to Glacier after 30 days
   aws s3api put-bucket-lifecycle-configuration \
     --bucket noaa-data-lake-dev \
     --lifecycle-configuration file://lifecycle.json
   ```

4. **Partition Pruning in Athena:**
   ```sql
   -- Always include partition filters
   WHERE year = 2025 AND month = 11 AND day = 17
   ```

---

## 🧪 Testing

### Unit Test ETL Script Locally

```bash
# Install dependencies
pip install pyspark boto3

# Run with sample data
python json_array_to_jsonlines.py \
  --JOB_NAME test \
  --SOURCE_BUCKET test-bucket \
  --SOURCE_PREFIX test-data/ \
  --TARGET_BUCKET test-bucket \
  --TARGET_PREFIX test-output/ \
  --POND_NAME atmospheric \
  --DATA_TYPE atmospheric_observations
```

### Integration Test End-to-End

```bash
# 1. Trigger ingestion Lambda
aws lambda invoke \
  --function-name "noaa-ingest-atmospheric-dev" \
  --payload '{"mode":"incremental","hours_back":1}' \
  response.json

# 2. Wait for ingestion
sleep 30

# 3. Trigger ETL job
aws glue start-job-run \
  --job-name "noaa-etl-atmospheric-observations-dev"

# 4. Wait for ETL
sleep 180

# 5. Run crawler
aws glue start-crawler \
  --name "noaa-queryable-atmospheric-crawler-dev"

# 6. Wait for crawler
sleep 60

# 7. Query data
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_queryable_dev.observations WHERE year=2025"
```

---

## 🚀 Advanced Features

### Parallel Processing

Glue automatically parallelizes processing across partitions. Increase DPU for faster processing:

```yaml
MaxCapacity: 5.0  # Uses 5 DPUs for parallel processing
```

### Custom Transformations

Add data quality checks or transformations in the ETL script:

```python
# Add after exploded_df
from pyspark.sql.functions import when, col

# Filter out bad data
clean_df = exploded_df.filter(
    (col("avg_temperature") > -50) & 
    (col("avg_temperature") < 60)
)

# Add derived columns
enriched_df = clean_df.withColumn(
    "temp_fahrenheit",
    (col("avg_temperature") * 9/5) + 32
)
```

### Integration with Lambda

Update the enhanced handler to query the new database:

```python
# In lambda-enhanced-handler/lambda_function.py
GOLD_DB = os.environ.get("GOLD_DB", "noaa_queryable_dev")
```

---

## 📚 Additional Resources

- **AWS Glue Documentation:** https://docs.aws.amazon.com/glue/
- **Athena Best Practices:** https://docs.aws.amazon.com/athena/latest/ug/performance-tuning.html
- **PySpark API:** https://spark.apache.org/docs/latest/api/python/
- **NOAA Data Lake Whitepaper:** `../NOAA_FEDERATED_DATA_LAKE_WHITEPAPER.md`

---

## 📝 Changelog

### Version 1.0 (2025-11-17)
- ✅ Initial release
- ✅ JSON array to JSON Lines conversion
- ✅ Automatic scheduling via EventBridge
- ✅ Support for 5 data types across 3 ponds
- ✅ CloudFormation-based deployment
- ✅ Cross-region and multi-environment support

---

## 🤝 Contributing

To contribute improvements to the ETL pipeline:

1. Modify the Glue ETL script
2. Test locally with sample data
3. Upload to S3 script bucket
4. Monitor first production run
5. Document any schema changes

---

## 📞 Support

**Issues:**
- Check CloudWatch Logs: `/aws-glue/jobs/output`
- Review job metrics in Glue Console
- Validate S3 permissions and data format

**Contact:**
- Documentation: This README
- Architecture: `NOAA_FEDERATED_DATA_LAKE_WHITEPAPER.md`
- Deployment Logs: `deployment-info-{env}.json`

---

**Status:** ✅ Production Ready  
**Last Updated:** 2025-11-17  
**Version:** 1.0.0  
**Maintainer:** NOAA Federated Data Lake Team