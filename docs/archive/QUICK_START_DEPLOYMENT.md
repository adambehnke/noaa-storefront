# 🚀 NOAA 24/7 Ingestion System - Quick Start

Get your comprehensive NOAA data ingestion system running in **under 30 minutes**.

---

## ✅ Prerequisites Checklist

Before you begin, ensure you have:

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Bash shell (macOS/Linux/WSL)
- [ ] Internet connection (to download packages and call NOAA APIs)

### Verify AWS CLI Setup

```bash
# Check AWS credentials
aws sts get-caller-identity

# Should return your account ID, user ARN, etc.
```

---

## 🎯 One-Command Deployment

### Step 1: Set Environment Variables

```bash
# Required
export AWS_REGION=us-east-1
export ENV=dev

# Optional (for climate data)
export NCEI_TOKEN=your_token_here
```

**Get NCEI Token (optional):** https://www.ncdc.noaa.gov/cdo-web/token

### Step 2: Run Deployment Script

```bash
cd noaa_storefront
./deployment/scripts/deploy_comprehensive_ingestion.sh
```

**This script will:**
- ✅ Create S3 buckets and medallion structure
- ✅ Create IAM roles with appropriate permissions
- ✅ Deploy 6 ingestion lambdas (one per data pond)
- ✅ Set up EventBridge schedules (every 15 min + daily backfill)
- ✅ Create Glue database and tables
- ✅ Deploy AI data matching lambda
- ✅ Create CloudWatch dashboard

**Expected Duration:** 10-15 minutes

---

## 🔍 Verify Deployment

### Check 1: Lambda Functions Deployed

```bash
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `noaa-ingest`)].FunctionName' \
  --output table
```

**Expected Output:** 6 lambda functions
```
noaa-ingest-atmospheric-dev
noaa-ingest-oceanic-dev
noaa-ingest-buoy-dev
noaa-ingest-climate-dev
noaa-ingest-spatial-dev
noaa-ingest-terrestrial-dev
```

### Check 2: EventBridge Rules Created

```bash
aws events list-rules \
  --query 'Rules[?contains(Name, `noaa-ingest`)].Name' \
  --output table
```

**Expected Output:** 12 rules (6 ponds × 2 schedules each)

### Check 3: S3 Bucket and Structure

```bash
aws s3 ls s3://noaa-data-lake-${ENV}/ --recursive | head -20
```

**Expected Output:** Bronze/Silver/Gold folders for each pond

### Check 4: Glue Database and Tables

```bash
aws glue get-tables \
  --database-name "noaa_federated_${ENV}" \
  --query 'TableList[].Name' \
  --output table
```

**Expected Output:** 18 tables (6 ponds × 3 layers)

---

## 🧪 Test Ingestion

### Manual Test - Trigger One Lambda

```bash
# Test atmospheric ingestion
aws lambda invoke \
  --function-name "noaa-ingest-atmospheric-${ENV}" \
  --payload '{"mode":"incremental","hours_back":1}' \
  response.json

# View response
cat response.json
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "body": "{\"status\":\"success\",\"stats\":{\"bronze_records\":120,\"silver_records\":120,\"gold_records\":60}}"
}
```

### View Real-Time Logs

```bash
# Watch logs as ingestion happens
aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --follow
```

**Look for:**
- `[INFO] Starting atmospheric ingestion`
- `[INFO] Wrote X records to Bronze`
- `[INFO] Wrote X records to Silver`
- `[INFO] Wrote X records to Gold`
- `[SUCCESS] Ingestion complete`

### Check Data Arrived in S3

```bash
# Check Gold layer for latest data
aws s3 ls s3://noaa-data-lake-${ENV}/gold/atmospheric/observations/ \
  --recursive --human-readable | tail -10
```

**Expected Output:** JSON files with timestamps

---

## 📊 Query Your Data

### Query with Athena (Console)

1. Go to AWS Athena Console: https://console.aws.amazon.com/athena/
2. Select database: `noaa_federated_dev`
3. Run query:

```sql
SELECT * 
FROM atmospheric_gold 
WHERE year = 2024 
LIMIT 10;
```

### Query with AWS CLI

```bash
# Start query
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT COUNT(*) as record_count FROM noaa_federated_${ENV}.atmospheric_gold WHERE year=2024" \
  --result-configuration "OutputLocation=s3://noaa-data-lake-${ENV}/athena-results/" \
  --query-execution-context "Database=noaa_federated_${ENV}" \
  --query 'QueryExecutionId' \
  --output text)

# Wait for completion
aws athena get-query-execution --query-execution-id $QUERY_ID

# Get results
aws athena get-query-results --query-execution-id $QUERY_ID
```

---

## 🎉 Success!

Your system is now:

✅ **Ingesting data every 15 minutes** from all NOAA endpoints  
✅ **Backfilling historical data** daily  
✅ **Processing through medallion architecture** (Bronze → Silver → Gold)  
✅ **Storing in queryable format** (Athena-ready)  
✅ **AI-powered for federated queries** (Bedrock Claude)

---

## 📈 Monitor Your System

### CloudWatch Dashboard

View real-time metrics:
```bash
open "https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=NOAA-Ingestion-${ENV}"
```

### Watch All Ponds

```bash
# Simple monitoring script
for pond in atmospheric oceanic buoy climate spatial terrestrial; do
  echo "=== $pond ==="
  aws logs tail /aws/lambda/noaa-ingest-${pond}-${ENV} --since 1h | grep "Ingestion complete" | tail -1
done
```

### Check Data Volume

```bash
# See how much data you've ingested
aws s3 ls s3://noaa-data-lake-${ENV}/ --recursive --summarize | tail -2
```

---

## 🛠️ Common Commands

### Pause All Ingestion

```bash
# Disable all EventBridge rules
for rule in $(aws events list-rules --query 'Rules[?contains(Name, `noaa-ingest`)].Name' --output text); do
  aws events disable-rule --name $rule
  echo "Disabled: $rule"
done
```

### Resume All Ingestion

```bash
# Enable all EventBridge rules
for rule in $(aws events list-rules --query 'Rules[?contains(Name, `noaa-ingest`)].Name' --output text); do
  aws events enable-rule --name $rule
  echo "Enabled: $rule"
done
```

### Check Costs So Far

```bash
# View costs for last 7 days
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --group-by Type=SERVICE
```

### Delete Everything (Cleanup)

```bash
# WARNING: This will delete all ingestion infrastructure
# Delete all lambdas
for func in $(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa-ingest`)].FunctionName' --output text); do
  aws lambda delete-function --function-name $func
done

# Delete EventBridge rules
for rule in $(aws events list-rules --query 'Rules[?contains(Name, `noaa-ingest`)].Name' --output text); do
  # Remove targets first
  aws events remove-targets --rule $rule --ids 1
  aws events delete-rule --name $rule
done

# Delete S3 bucket (WARNING: deletes all data)
aws s3 rb s3://noaa-data-lake-${ENV} --force

# Delete Glue database
aws glue delete-database --name noaa_federated_${ENV}
```

---

## 🆘 Troubleshooting

### Issue: Deployment script fails

**Check:** AWS credentials and permissions
```bash
aws sts get-caller-identity
aws iam get-user
```

**Solution:** Ensure you have admin access or required permissions

### Issue: Lambda timeout errors

**Check logs:**
```bash
aws logs tail /aws/lambda/noaa-ingest-atmospheric-${ENV} --since 1h | grep ERROR
```

**Solution:** Lambdas have 15-minute timeout, but some ponds may need tuning. Reduce station lists if needed.

### Issue: No data appearing in S3

**Check:** Lambda is being triggered
```bash
aws events list-targets-by-rule --rule noaa-ingest-atmospheric-${ENV}-incremental
```

**Solution:** Manually invoke lambda to test, check logs for API errors

### Issue: Athena returns no results

**Fix partitions:**
```sql
MSCK REPAIR TABLE noaa_federated_dev.atmospheric_gold;
```

**Check S3:**
```bash
aws s3 ls s3://noaa-data-lake-${ENV}/gold/atmospheric/ --recursive | head -20
```

---

## 📚 Next Steps

1. **Review Full Documentation:** `docs/COMPREHENSIVE_INGESTION.md`
2. **Customize Station Lists:** Edit lambda code to add/remove stations
3. **Set Up Alerts:** Configure SNS for ingestion failures
4. **Optimize Costs:** Implement S3 lifecycle policies
5. **Build Dashboards:** Create custom visualizations with QuickSight
6. **Integrate with Webapp:** Connect federated query system to frontend

---

## 💡 Pro Tips

### Speed Up Initial Backfill

Run all ponds in parallel:
```bash
for pond in atmospheric oceanic buoy climate spatial terrestrial; do
  aws lambda invoke \
    --function-name "noaa-ingest-${pond}-${ENV}" \
    --payload '{"mode":"backfill","days_back":7}' \
    --invocation-type Event \
    response-${pond}.json &
done
wait
```

### Convert to Parquet for Better Performance

```sql
-- Much faster Athena queries
CREATE TABLE atmospheric_gold_parquet
WITH (
  format='PARQUET',
  external_location='s3://noaa-data-lake-dev/gold-parquet/atmospheric/'
)
AS SELECT * FROM noaa_federated_dev.atmospheric_gold;
```

### Set Up Cost Alerts

```bash
# Create budget alert at $500/month
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

---

## 📞 Support

- **Documentation:** `docs/COMPREHENSIVE_INGESTION.md`
- **Deployment Logs:** `deployment/logs/deployment_*.log`
- **Lambda Code:** `ingestion/lambdas/{pond}/lambda_function.py`
- **AWS Console:** https://console.aws.amazon.com/

---

**Deployed Successfully?** 🎊

Your NOAA Data Lake is now ingesting data 24/7 from all NOAA endpoints!

**Current Status:**
- ✅ 6 Data Ponds Operational
- ✅ 100+ Stations Being Monitored
- ✅ Medallion Architecture Active
- ✅ AI-Powered Cross-Pond Queries Enabled
- ✅ Continuous & Historical Data Ingestion

**Data is flowing! Check back in 15 minutes to see your first ingestion cycle complete.**

---

**Version:** 1.0.0  
**Last Updated:** 2024-01-15  
**Status:** 🟢 Production Ready