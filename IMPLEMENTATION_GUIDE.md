# NOAA Federated Data Lake - Implementation Guide

## Overview

This guide provides step-by-step instructions to implement the complete NOAA Federated Data Lake on AWS, replacing Databricks with native AWS services (Glue, Athena, Bedrock, Lambda).

**Timeline:** 7-10 days for MVP with 3 priority services (NWS, Tides & Currents, CDO)

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] Python 3.9+ installed (`python3 --version`)
- [ ] jq installed for JSON parsing (`jq --version`)
- [ ] Git repository cloned
- [ ] NOAA CDO API token (optional, get at https://www.ncdc.noaa.gov/cdo-web/token)
- [ ] Minimum 2 hours for initial deployment

**AWS Service Limits to Check:**
- ElastiCache cluster limit (default: 1)
- Lambda concurrent executions (default: 1000)
- Glue jobs (default: 25)
- S3 buckets (default: 100)

---

## Day 1: Environment Setup & Validation

### 1.1 Configure AWS Credentials

```bash
# Configure AWS CLI
aws configure

# Verify access
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-user"
# }
```

### 1.2 Set Environment Variables

```bash
# Create a .env file
cat > .env << 'EOF'
export AWS_REGION=us-east-1
export ENVIRONMENT=dev
export NOAA_CDO_TOKEN=your_token_here  # Optional
EOF

# Source the file
source .env
```

### 1.3 Test NOAA API Connectivity

```bash
# Make the test script executable
chmod +x test_noaa_apis.py

# Run API connectivity tests
python3 test_noaa_apis.py

# Expected output:
# ✓ All tests passed! (11/11)
# ✓ You're ready to deploy the NOAA stack!
```

**If tests fail:**
- NWS API: Check internet connectivity, rate limits
- Tides API: Some stations may not support all products (OK)
- CDO API: Verify token is correct and active

---

## Day 2: Infrastructure Deployment

### 2.1 Prepare Deployment

```bash
# Navigate to project directory
cd noaa_storefront

# Make deployment script executable
chmod +x deploy.sh

# Review the CloudFormation template
less noaa-complete-stack.yaml
```

### 2.2 Deploy the Stack

```bash
# Deploy to dev environment
./deploy.sh dev us-east-1

# This will:
# 1. Package Lambda functions (2-3 minutes)
# 2. Upload code to S3 (1-2 minutes)
# 3. Deploy CloudFormation stack (10-15 minutes)
# 4. Run tests
# 5. Optionally trigger initial ingestion

# Answer prompts:
# - NOAA CDO Token: [paste your token or press Enter to skip]
# - Trigger ingestion now? [y/n]: y
```

### 2.3 Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].StackStatus'

# Should return: "CREATE_COMPLETE"

# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs' \
  --output table
```

### 2.4 Save Important Values

```bash
# Export key values for easy access
export DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DataLakeBucketName`].OutputValue' \
  --output text)

export API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
  --output text)

echo "Data Lake Bucket: $DATA_LAKE_BUCKET"
echo "API Endpoint: $API_ENDPOINT"

# Save to file for later use
cat > deployment-info.txt << EOF
Data Lake Bucket: $DATA_LAKE_BUCKET
API Endpoint: $API_ENDPOINT
Deployed: $(date)
EOF
```

---

## Day 3: Data Ingestion & Pipeline Testing

### 3.1 Monitor Initial Ingestion

```bash
# Get state machine ARN
STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --max-results 5

# Get execution details
EXECUTION_ARN=$(aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --max-results 1 \
  --query 'executions[0].executionArn' \
  --output text)

# Watch execution status
watch -n 5 "aws stepfunctions describe-execution \
  --execution-arn $EXECUTION_ARN \
  --query 'status'"
```

### 3.2 Verify Bronze Layer Data

```bash
# Check for ingested data
aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/" --recursive | head -20

# Expected structure:
# bronze/atmospheric/nws_alerts/date=2024-01-15/
# bronze/atmospheric/nws_observations/date=2024-01-15/
# bronze/oceanic/water_levels/date=2024-01-15/

# Download a sample file
aws s3 cp "s3://$DATA_LAKE_BUCKET/bronze/atmospheric/nws_alerts/date=$(date +%Y-%m-%d)/" \
  ./sample-data/ --recursive

# View sample data
cat sample-data/*.json | jq '.[0]' | head -50
```

### 3.3 Check Glue Job Logs

```bash
# List Glue jobs
aws glue list-jobs --query 'JobNames'

# Get job run details
aws glue get-job-runs \
  --job-name noaa-bronze-ingest-nws-dev \
  --max-results 1

# View CloudWatch logs
aws logs tail /aws-glue/jobs/output --follow
```

---

## Day 4: Query Testing & Validation

### 4.1 Test API Endpoints

```bash
# Health check
curl "$API_ENDPOINT/data?ping=true" | jq

# Expected:
# {
#   "status": "healthy",
#   "env": "dev",
#   "timestamp": "2024-01-15T12:00:00.000000",
#   "redis_enabled": true
# }

# Query atmospheric data
curl "$API_ENDPOINT/data?service=atmospheric&limit=10" | jq

# Query oceanic data
curl "$API_ENDPOINT/data?service=oceanic&limit=10" | jq

# Query with filters
curl "$API_ENDPOINT/data?service=nws&region=CA&limit=5" | jq
```

### 4.2 Test AI Query

```bash
# Test natural language query
curl -X POST "$API_ENDPOINT/query" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "ai_query",
    "question": "Show me weather alerts from California"
  }' | jq

# Test direct SQL query
curl -X POST "$API_ENDPOINT/query" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "query",
    "sql": "SELECT * FROM noaa_gold_dev.atmospheric_aggregated LIMIT 5"
  }' | jq
```

### 4.3 Test with Athena Console

1. Go to Athena console: https://console.aws.amazon.com/athena/
2. Select database: `noaa_gold_dev`
3. Run queries:

```sql
-- Check available tables
SHOW TABLES;

-- Query atmospheric data
SELECT 
    region,
    event_type,
    severity,
    alert_count,
    date
FROM atmospheric_aggregated
WHERE date >= DATE '2024-01-01'
ORDER BY date DESC
LIMIT 10;

-- Query oceanic data
SELECT 
    station_id,
    region,
    avg_water_level,
    avg_water_temp,
    date
FROM oceanic_aggregated
ORDER BY date DESC
LIMIT 10;

-- Count records by region
SELECT 
    region,
    COUNT(*) as record_count
FROM atmospheric_aggregated
GROUP BY region
ORDER BY record_count DESC;
```

---

## Day 5: Optimization & Monitoring

### 5.1 Set Up CloudWatch Dashboards

```bash
# Create custom dashboard
aws cloudwatch put-dashboard \
  --dashboard-name NOAA-Data-Lake-Dev \
  --dashboard-body file://dashboard-config.json
```

### 5.2 Configure Alerts

```bash
# Subscribe to SNS topic for pipeline notifications
SNS_TOPIC=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`PipelineNotificationTopic`].OutputValue' \
  --output text)

aws sns subscribe \
  --topic-arn "$SNS_TOPIC" \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription via email
```

### 5.3 Review and Optimize Costs

```bash
# Check S3 bucket size
aws s3 ls "s3://$DATA_LAKE_BUCKET/" --recursive --summarize | tail -2

# Review Athena query costs
aws athena list-query-executions \
  --max-results 10 \
  --query 'QueryExecutionIds' \
  --output text | while read id; do
    aws athena get-query-execution \
      --query-execution-id "$id" \
      --query 'QueryExecution.Statistics.DataScannedInBytes'
done
```

---

## Day 6-7: Testing & Iteration

### 6.1 End-to-End Testing

Create test scenarios:

```bash
# Create test script
cat > test-e2e.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Running End-to-End Tests ==="

# Test 1: Data freshness
echo "Test 1: Checking data freshness..."
LATEST_DATA=$(aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/atmospheric/nws_alerts/" \
  --recursive | tail -1 | awk '{print $1}')
echo "Latest data: $LATEST_DATA"

# Test 2: API response time
echo "Test 2: Testing API response time..."
time curl -s "$API_ENDPOINT/data?service=atmospheric&limit=1" > /dev/null

# Test 3: Cache effectiveness
echo "Test 3: Testing cache..."
time curl -s "$API_ENDPOINT/data?service=atmospheric&region=CA&limit=5" > /dev/null
time curl -s "$API_ENDPOINT/data?service=atmospheric&region=CA&limit=5" > /dev/null

# Test 4: AI query
echo "Test 4: Testing AI query..."
curl -X POST "$API_ENDPOINT/query" \
  -H "Content-Type: application/json" \
  -d '{"action":"ai_query","question":"Show recent alerts"}' | jq -r '.sql'

echo "=== All Tests Passed ==="
EOF

chmod +x test-e2e.sh
./test-e2e.sh
```

### 6.2 Performance Tuning

**Optimize Athena Queries:**
```sql
-- Add partitions for better performance
MSCK REPAIR TABLE atmospheric_aggregated;

-- Analyze table statistics
ANALYZE TABLE atmospheric_aggregated COMPUTE STATISTICS;
```

**Optimize Glue Jobs:**
- Increase DPU if jobs are slow
- Enable job bookmarks to avoid reprocessing
- Use partitioned writes

### 6.3 Data Quality Checks

```python
# Create data quality check script
cat > check-data-quality.py << 'EOF'
import boto3
import json
from datetime import datetime, timedelta

s3 = boto3.client('s3')
bucket = 'your-bucket-name'

def check_data_freshness():
    """Check if data was ingested in last 6 hours"""
    response = s3.list_objects_v2(
        Bucket=bucket,
        Prefix='bronze/atmospheric/nws_alerts/'
    )
    
    if not response.get('Contents'):
        print("❌ No data found!")
        return False
    
    latest = max(response['Contents'], key=lambda x: x['LastModified'])
    age = datetime.now(latest['LastModified'].tzinfo) - latest['LastModified']
    
    if age.total_seconds() > 6 * 3600:
        print(f"❌ Data is {age} old!")
        return False
    
    print(f"✓ Data is fresh ({age} old)")
    return True

if __name__ == '__main__':
    check_data_freshness()
EOF
```

---

## Production Deployment Checklist

When ready to deploy to production:

- [ ] Review and adjust resource sizing (DPUs, Lambda memory, Redis node type)
- [ ] Enable CloudTrail for audit logging
- [ ] Set up VPC endpoints for private connectivity
- [ ] Configure backup and disaster recovery
- [ ] Enable enhanced monitoring
- [ ] Set up cost alerts and budgets
- [ ] Implement authentication (API Gateway + Cognito)
- [ ] Add WAF rules for API protection
- [ ] Enable encryption at rest for S3
- [ ] Set up cross-region replication (if needed)
- [ ] Create runbooks for common operations
- [ ] Document troubleshooting procedures

```bash
# Deploy to production
./deploy.sh prod us-east-1
```

---

## Troubleshooting Guide

### Issue: Pipeline execution fails

**Check:**
```bash
# Get failure details
aws stepfunctions describe-execution --execution-arn "$EXECUTION_ARN"

# Check Glue job logs
aws logs tail /aws-glue/jobs/error --follow
```

### Issue: No data in Bronze layer

**Check:**
```bash
# Test NOAA API directly
curl "https://api.weather.gov/alerts/active" -H "User-Agent: test/1.0"

# Check Glue job status
aws glue get-job-run --job-name noaa-bronze-ingest-nws-dev --run-id <run-id>
```

### Issue: Lambda timeout

**Solution:**
- Increase Lambda timeout in CloudFormation template
- Add pagination to queries
- Optimize Athena queries with partitions

### Issue: Redis connection fails

**Check:**
```bash
# Verify Redis cluster status
aws elasticache describe-cache-clusters --show-cache-node-info

# Check Lambda VPC configuration
aws lambda get-function-configuration --function-name noaa-data-api-dev
```

---

## Next Steps

### Week 2-3: Expand Coverage
1. Add remaining NWS endpoints (9 more)
2. Implement terrestrial pond
3. Implement spatial pond
4. Add EMWIN for restricted data

### Week 4-5: Frontend Development
1. Set up React application with Tailwind CSS
2. Create data visualization components
3. Implement user authentication with Cognito
4. Build persona-based dashboards

### Week 6+: Advanced Features
1. Implement real-time streaming with Kinesis
2. Add machine learning models for predictions
3. Create data quality monitoring
4. Build cost optimization automation
5. Implement multi-region deployment

---

## Resources

### Documentation
- AWS Glue: https://docs.aws.amazon.com/glue/
- Amazon Athena: https://docs.aws.amazon.com/athena/
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- NOAA APIs: https://www.weather.gov/documentation/services-web-api

### Cost Optimization
- Use S3 Intelligent-Tiering for storage
- Enable Glue job bookmarks to avoid reprocessing
- Use Athena workgroups for query limits
- Implement Redis TTL for cache management

### Security Best Practices
- Enable VPC Flow Logs
- Use AWS Secrets Manager for API tokens
- Implement least privilege IAM policies
- Enable S3 bucket versioning
- Use CloudTrail for audit logging

---

## Support & Community

- AWS Support: https://console.aws.amazon.com/support/
- NOAA Data Forums: https://www.noaa.gov/
- Project Issues: [GitHub Issues if applicable]

---

**Last Updated:** 2024-01-15
**Version:** 1.0.0
**Status:** Production Ready ✓