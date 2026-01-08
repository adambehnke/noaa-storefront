# NOAA Enhancements - Quick Start Guide

## ⚡ 5-Minute Deployment

### Prerequisites Checklist
```bash
# Check AWS credentials
aws sts get-caller-identity --profile noaa-target

# Verify environment
source config/environment.sh
echo $AWS_ACCOUNT_ID  # Should be: 899626030376
echo $AWS_REGION      # Should be: us-east-1
```

---

## 🚀 One-Command Deployment

```bash
# Deploy everything
chmod +x deploy_enhancements.sh
./deploy_enhancements.sh all
```

**⏱ Expected Time:** 20-30 minutes

---

## 📦 Individual Deployments

### Option 1: Real-Time Streaming Only
```bash
./deploy_enhancements.sh streaming
```
**Time:** ~10 minutes  
**Cost:** $95/month

### Option 2: Analytics Layer Only
```bash
./deploy_enhancements.sh analytics
```
**Time:** ~12 minutes  
**Cost:** $249/month

### Option 3: QuickSight Dashboards Only
```bash
# Enable QuickSight first (one-time)
# Visit: https://quicksight.aws.amazon.com/

./deploy_enhancements.sh quicksight
```
**Time:** ~8 minutes  
**Cost:** $143/month

---

## ✅ Quick Verification

### Check All Stacks
```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --profile noaa-target \
  --query "StackSummaries[?contains(StackName, 'noaa-')].{Name:StackName,Status:StackStatus}" \
  --output table
```

### Verify Streaming
```bash
# List streams
aws kinesis list-streams --profile noaa-target

# Check stream status
aws kinesis describe-stream \
  --stream-name noaa-stream-atmospheric-dev \
  --profile noaa-target
```

### Verify Analytics
```bash
# List Glue jobs
aws glue list-jobs --profile noaa-target

# List databases
aws glue get-databases --profile noaa-target \
  --query "DatabaseList[?contains(Name, 'noaa_')].Name"
```

### Verify QuickSight
```bash
# List dashboards
aws quicksight list-dashboards \
  --aws-account-id 899626030376 \
  --profile noaa-target \
  --region us-east-1
```

---

## 🎯 Quick Operations

### Test Streaming

#### Send Test Data
```bash
cd real-time-streaming

# Install dependencies
pip install boto3 faker

# Send 10 test records
python test_stream_producer.py --stream atmospheric --count 10

# Send to all streams
python test_stream_producer.py --stream all --count 100

# Continuous streaming (5 records/sec for 60 seconds)
python test_stream_producer.py --stream oceanic --continuous --rate 5 --duration 60
```

#### View Stream Data
```bash
# Get shard iterator
SHARD_ITERATOR=$(aws kinesis get-shard-iterator \
  --stream-name noaa-stream-atmospheric-dev \
  --shard-id shardId-000000000000 \
  --shard-iterator-type LATEST \
  --profile noaa-target \
  --query 'ShardIterator' \
  --output text)

# Read records
aws kinesis get-records \
  --shard-iterator $SHARD_ITERATOR \
  --profile noaa-target
```

### Run Analytics Jobs

#### Trigger Hourly Aggregation
```bash
aws glue start-job-run \
  --job-name noaa-hourly-aggregation-dev \
  --profile noaa-target
```

#### Trigger Daily Aggregation
```bash
aws glue start-job-run \
  --job-name noaa-daily-aggregation-dev \
  --arguments '{"--execution_date":"2024-12-09"}' \
  --profile noaa-target
```

#### Check Job Status
```bash
# List recent runs
aws glue get-job-runs \
  --job-name noaa-hourly-aggregation-dev \
  --max-results 5 \
  --profile noaa-target \
  --query "JobRuns[*].{ID:Id,State:JobRunState,Started:StartedOn}"
```

### Query Analytics Data

#### Athena Query (CLI)
```bash
# Start query
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_analytics_dev.hourly_aggregates LIMIT 10" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --work-group noaa-analytics-dev \
  --profile noaa-target \
  --query 'QueryExecutionId' \
  --output text)

# Wait for completion
aws athena get-query-execution \
  --query-execution-id $QUERY_ID \
  --profile noaa-target

# Get results
aws athena get-query-results \
  --query-execution-id $QUERY_ID \
  --profile noaa-target
```

#### Athena Query (SQL - Use in Console)
```sql
-- Switch to analytics database
USE noaa_analytics_dev;

-- View hourly aggregates
SELECT 
  pond_name,
  aggregation_hour,
  record_count,
  avg_value,
  min_value,
  max_value
FROM hourly_aggregates
WHERE aggregation_hour >= current_timestamp - interval '24' hour
ORDER BY aggregation_hour DESC
LIMIT 100;

-- View daily statistics
SELECT 
  pond_name,
  aggregation_date,
  record_count,
  percentile_50 as median
FROM daily_aggregates
WHERE aggregation_date >= current_date - interval '30' day
ORDER BY aggregation_date DESC;

-- ML features
USE noaa_ml_dev;

SELECT * 
FROM features
WHERE year = 2024 AND month = 12
LIMIT 100;
```

### Access QuickSight

#### Get Dashboard URL
```bash
# Get operational dashboard URL
aws cloudformation describe-stacks \
  --stack-name noaa-quicksight-dev \
  --profile noaa-target \
  --query "Stacks[0].Outputs[?OutputKey=='DashboardURL'].OutputValue" \
  --output text
```

#### Manual Refresh Dataset
```bash
aws quicksight create-ingestion \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --ingestion-id refresh-$(date +%s) \
  --profile noaa-target \
  --region us-east-1
```

---

## 📊 Monitoring Commands

### CloudWatch Metrics

#### Stream Metrics
```bash
# Iterator age (should be < 60000ms)
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

#### Glue Job Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace Glue \
  --metric-name glue.driver.aggregate.numCompletedTasks \
  --dimensions Name=JobName,Value=noaa-hourly-aggregation-dev \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --profile noaa-target
```

### View Logs

#### Lambda Logs
```bash
aws logs tail /aws/lambda/noaa-stream-processor-atmospheric-dev \
  --follow \
  --profile noaa-target
```

#### Glue Job Logs
```bash
aws logs tail /aws-glue/jobs/output \
  --follow \
  --filter-pattern "noaa-hourly-aggregation-dev" \
  --profile noaa-target
```

### Check Alarms
```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "noaa-" \
  --profile noaa-target \
  --query "MetricAlarms[*].{Name:AlarmName,State:StateValue}" \
  --output table
```

---

## 🔧 Troubleshooting

### Stream Iterator Age Growing

**Problem:** Data processing is falling behind

```bash
# Scale up shards
aws kinesis update-shard-count \
  --stream-name noaa-stream-atmospheric-dev \
  --target-shard-count 4 \
  --scaling-type UNIFORM_SCALING \
  --profile noaa-target

# Increase Lambda concurrency
aws lambda put-function-concurrency \
  --function-name noaa-stream-processor-atmospheric-dev \
  --reserved-concurrent-executions 10 \
  --profile noaa-target
```

### Glue Job Failing

**Problem:** Job state = FAILED

```bash
# View error details
aws glue get-job-run \
  --job-name noaa-hourly-aggregation-dev \
  --run-id <RUN_ID> \
  --profile noaa-target

# Check logs
aws logs tail /aws-glue/jobs/error \
  --filter-pattern "noaa-hourly-aggregation-dev" \
  --profile noaa-target

# Retry job
aws glue start-job-run \
  --job-name noaa-hourly-aggregation-dev \
  --profile noaa-target
```

### QuickSight Not Loading

**Problem:** Dashboard shows no data

```bash
# Refresh dataset
aws quicksight create-ingestion \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --ingestion-id manual-$(date +%s) \
  --profile noaa-target \
  --region us-east-1

# Check ingestion status
aws quicksight list-ingestions \
  --aws-account-id 899626030376 \
  --data-set-id noaa-atmospheric-dataset-dev \
  --profile noaa-target \
  --region us-east-1
```

### Stack Update Blocked

**Problem:** CloudFormation says "No updates"

```bash
# Force update with dummy parameter
aws cloudformation update-stack \
  --stack-name noaa-streaming-dev \
  --use-previous-template \
  --parameters ParameterKey=ShardCount,ParameterValue=2 \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile noaa-target
```

---

## 🗑️ Cleanup (Remove All Resources)

### Delete All Stacks
```bash
# Delete in reverse order
aws cloudformation delete-stack --stack-name noaa-quicksight-dev --profile noaa-target
aws cloudformation delete-stack --stack-name noaa-analytics-dev --profile noaa-target
aws cloudformation delete-stack --stack-name noaa-streaming-dev --profile noaa-target

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name noaa-quicksight-dev --profile noaa-target
aws cloudformation wait stack-delete-complete --stack-name noaa-analytics-dev --profile noaa-target
aws cloudformation wait stack-delete-complete --stack-name noaa-streaming-dev --profile noaa-target
```

### Manual Cleanup
```bash
# Delete S3 streaming data (if needed)
aws s3 rm s3://noaa-federated-lake-899626030376-dev/streaming/ \
  --recursive \
  --profile noaa-target

# Delete Athena query results
aws s3 rm s3://noaa-athena-results-899626030376-dev/analytics/ \
  --recursive \
  --profile noaa-target
```

---

## 📈 Cost Monitoring

### Check Current Spend
```bash
# Get month-to-date costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://<(echo '{
    "Tags": {
      "Key": "Project",
      "Values": ["NOAA-Federated-Lake"]
    }
  }') \
  --profile noaa-target
```

### Set Budget Alert
```bash
# Create budget (one-time)
aws budgets create-budget \
  --account-id 899626030376 \
  --budget '{
    "BudgetName": "NOAA-Enhancements-Budget",
    "BudgetLimit": {"Amount": "600", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --profile noaa-target
```

---

## 📚 Additional Resources

| Resource | Location |
|----------|----------|
| **Full Documentation** | `ENHANCEMENTS_DEPLOYMENT_GUIDE.md` |
| **Executive Summary** | `ENHANCEMENTS_EXECUTIVE_SUMMARY.md` |
| **Streaming Code** | `real-time-streaming/` |
| **Analytics Scripts** | `analytics-layer/` |
| **Dashboard Config** | `quicksight-dashboards/` |
| **Environment Config** | `config/environment.sh` |

---

## 🎯 Common Use Cases

### Use Case 1: Real-Time Weather Monitoring
```bash
# Start streaming
python real-time-streaming/test_stream_producer.py \
  --stream atmospheric --continuous --rate 10 --duration 3600

# Monitor in another terminal
aws logs tail /aws/lambda/noaa-stream-processor-atmospheric-dev --follow --profile noaa-target
```

### Use Case 2: Daily Analytics Report
```bash
# Run daily aggregation
aws glue start-job-run --job-name noaa-daily-aggregation-dev --profile noaa-target

# Query results
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_analytics_dev.daily_aggregates WHERE aggregation_date = current_date" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target
```

### Use Case 3: ML Model Training
```bash
# Generate features
aws glue start-job-run --job-name noaa-ml-feature-engineering-dev --profile noaa-target

# Export to local (for training)
aws s3 sync s3://noaa-federated-lake-899626030376-dev/ml-datasets/features/ \
  ./ml-training-data/ \
  --profile noaa-target
```

---

## ⚡ Performance Tips

1. **Batch Operations**: Use `put_records` instead of `put_record` for Kinesis
2. **Partition Wisely**: Use diverse partition keys for even shard distribution
3. **Glue Bookmarks**: Enable job bookmarks to avoid reprocessing
4. **Athena Partitions**: Always filter by partition keys (year/month/day)
5. **QuickSight SPICE**: Import frequently-used datasets to SPICE for faster queries

---

## 🆘 Quick Support

### Get Help
```bash
# View deployment script help
./deploy_enhancements.sh --help

# View test script help
python real-time-streaming/test_stream_producer.py --help
```

### Check System Status
```bash
# All-in-one status check
./verify_complete_system.sh
```

---

**Last Updated:** December 10, 2024  
**Version:** 1.0  
**Maintained By:** NOAA Data Engineering Team