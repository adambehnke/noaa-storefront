# NOAA Federated Data Lake - Quick Start Guide

## 🎯 What We've Built

A complete AWS-based data lake that replaces Databricks with native AWS services:
- **3 Priority NOAA Data Sources:** NWS (weather), Tides & Currents (ocean), CDO (climate)
- **Medallion Architecture:** Bronze → Silver → Gold data layers
- **AI-Powered Queries:** Natural language to SQL with Amazon Bedrock
- **RESTful API:** Fast queries with Redis caching
- **Automated Pipeline:** Scheduled data ingestion every 6 hours

## 📋 Prerequisites (5 minutes)

```bash
# 1. Verify AWS CLI
aws --version  # Should be 2.x

# 2. Verify AWS credentials
aws sts get-caller-identity

# 3. Verify tools
jq --version
python3 --version  # Should be 3.9+
```

## 🚀 Deployment (15 minutes)

### Step 1: Test NOAA API Access

```bash
# Test connectivity to all NOAA APIs
python3 test_noaa_apis.py

# ✓ If all tests pass, proceed to deployment
# ✗ If tests fail, check your internet connection
```

### Step 2: Get NOAA CDO Token (Optional)

1. Visit: https://www.ncdc.noaa.gov/cdo-web/token
2. Enter your email
3. Check email for token
4. Export it:
   ```bash
   export NOAA_CDO_TOKEN="your_token_here"
   ```

### Step 3: Deploy the Stack

```bash
# Deploy to dev environment
./deploy.sh dev us-east-1

# This takes 10-15 minutes and creates:
# - 3 S3 buckets
# - 3 Glue databases
# - 5 Glue ETL jobs
# - 2 Lambda functions
# - 1 API Gateway
# - 1 ElastiCache Redis
# - 1 Step Functions pipeline
```

### Step 4: Verify Deployment

```bash
# Get API endpoint
export API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
  --output text)

# Test health check
curl "$API_ENDPOINT/data?ping=true" | jq

# Expected: {"status": "healthy", "env": "dev"}
```

## 🧪 Testing (10 minutes)

### Test 1: Check Data Ingestion

```bash
# Get bucket name
export DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DataLakeBucketName`].OutputValue' \
  --output text)

# Check Bronze layer
aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/atmospheric/" --recursive | head -10

# You should see files like:
# bronze/atmospheric/nws_alerts/date=2024-01-15/alerts_20240115_120000.json
```

### Test 2: Query the API

```bash
# Query atmospheric data
curl "$API_ENDPOINT/data?service=atmospheric&limit=10" | jq

# Query oceanic data
curl "$API_ENDPOINT/data?service=oceanic&limit=10" | jq

# Query with filters
curl "$API_ENDPOINT/data?service=nws&region=CA&limit=5" | jq
```

### Test 3: AI-Powered Query

```bash
# Ask a natural language question
curl -X POST "$API_ENDPOINT/query" \
  -H "Content-Type: application/json" \
  -d '{"action":"ai_query","question":"Show me weather alerts in California"}' | jq

# The AI will generate SQL and execute it automatically!
```

### Test 4: Query with Athena

1. Go to: https://console.aws.amazon.com/athena/
2. Select database: `noaa_gold_dev`
3. Run query:
   ```sql
   SELECT * FROM atmospheric_aggregated LIMIT 10;
   ```

## 📊 Monitor Pipeline

```bash
# Get state machine ARN
export STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# List recent pipeline runs
aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --max-results 5

# Or view in console
echo "https://console.aws.amazon.com/states/home?region=us-east-1#/statemachines/view/$STATE_MACHINE_ARN"
```

## 🎓 What to Do Next

### Option 1: Explore the Data

```bash
# Download sample data
mkdir -p sample-data
aws s3 cp "s3://$DATA_LAKE_BUCKET/bronze/atmospheric/" ./sample-data/ --recursive --exclude "*" --include "*.json"

# View it
cat sample-data/*.json | jq '.[0]' | head -50
```

### Option 2: Run More Queries

```bash
# Get data by date range
curl "$API_ENDPOINT/data?service=atmospheric&start_date=2024-01-01&end_date=2024-01-31&limit=100" | jq

# Get specific fields
curl "$API_ENDPOINT/data?service=oceanic&fields=station_id,region,date&limit=20" | jq
```

### Option 3: Set Up Alerts

```bash
# Subscribe to pipeline notifications
SNS_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PipelineNotificationTopic`].OutputValue' \
  --output text)

aws sns subscribe \
  --topic-arn "$SNS_TOPIC" \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm via email
```

## 🐛 Troubleshooting

### Issue: No data in Bronze layer

```bash
# Check Glue job status
aws glue list-jobs

# Get recent job runs
aws glue get-job-runs --job-name noaa-bronze-ingest-nws-dev --max-results 1

# View logs
aws logs tail /aws-glue/jobs/output --follow
```

### Issue: API returns empty results

```bash
# Check if Gold layer has data
aws s3 ls "s3://$DATA_LAKE_BUCKET/gold/" --recursive

# Run pipeline manually
aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE_ARN"
```

### Issue: Lambda timeout

```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-data-api-dev --follow

# Reduce query size
curl "$API_ENDPOINT/data?service=atmospheric&limit=5" | jq
```

## 📚 Documentation

- **Full Documentation:** `README.md`
- **Implementation Guide:** `IMPLEMENTATION_GUIDE.md`
- **Recommendations:** `RECOMMENDATIONS.md`
- **AWS Athena:** https://console.aws.amazon.com/athena/
- **AWS Step Functions:** https://console.aws.amazon.com/states/
- **AWS CloudWatch:** https://console.aws.amazon.com/cloudwatch/

## 💡 Key Endpoints Summary

### NOAA APIs (What We're Ingesting)

1. **NWS API** - Weather alerts and observations
   - URL: https://api.weather.gov
   - Auth: None (rate limited)

2. **Tides & Currents** - Ocean and coastal data
   - URL: https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
   - Auth: None

3. **CDO API** - Climate data
   - URL: https://www.ncdc.noaa.gov/cdo-web/api/v2
   - Auth: Token required

### Your API Endpoints

- **Health Check:** `GET /data?ping=true`
- **Query Data:** `GET /data?service=<service>&region=<region>&limit=<n>`
- **AI Query:** `POST /query` with `{"action":"ai_query","question":"..."}`
- **Direct SQL:** `POST /query` with `{"action":"query","sql":"..."}`

## 🎯 Success Criteria

✅ **You're successful if:**
- Stack deploys without errors
- API health check returns "healthy"
- Bronze layer contains JSON files
- Athena can query Gold tables
- API returns real NOAA data

## 💰 Estimated Costs

**Dev Environment:**
- Daily: ~$3-5
- Monthly: ~$100-150

**Note:** Delete the stack when not in use to save costs:
```bash
aws cloudformation delete-stack --stack-name noaa-federated-lake-dev
```

## 🆘 Need Help?

1. Check CloudWatch logs
2. Review `README.md` for detailed docs
3. Test NOAA APIs with `python3 test_noaa_apis.py`
4. Check AWS service limits and quotas

## 🎉 You're Done!

You now have a fully functional NOAA data lake with:
- Real-time weather alerts
- Ocean and tide data
- Climate observations
- AI-powered querying
- RESTful API

**Try it out:**
```bash
curl "$API_ENDPOINT/data?service=atmospheric&limit=5" | jq '.data[0]'
```

Happy data exploring! 🌊🌤️📊
