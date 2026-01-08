# NOAA Federated Data Lake - Quick Deploy Guide

**Last Updated:** December 2025  
**Estimated Time:** 30-45 minutes  
**Difficulty:** Intermediate

---

## 🚀 Quick Start (TL;DR)

```bash
# 1. Verify AWS credentials
aws sts get-caller-identity

# 2. Run migration script (automated)
./scripts/migrate_to_new_account.sh --env dev --force

# 3. Verify deployment
aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName'

# 4. Wait 15 minutes and check for data
aws s3 ls s3://noaa-federated-lake-$(aws sts get-caller-identity --query Account --output text)-dev/bronze/atmospheric/ --recursive | tail -5
```

Done! 🎉

---

## 📋 Prerequisites

### Required Tools

- ✅ **AWS CLI** (v2.x recommended)
  ```bash
  aws --version  # Should be 2.x or higher
  ```

- ✅ **Python 3.9+**
  ```bash
  python3 --version
  ```

- ✅ **Bash 4.0+**
  ```bash
  bash --version
  ```

### AWS Permissions Required

Your AWS credentials need the following permissions:

```yaml
Services Required:
  - Lambda: Create functions, layers
  - S3: Create/manage buckets
  - EventBridge: Create/manage rules
  - IAM: Create/manage roles
  - Athena: Create databases/tables
  - CloudFormation: Deploy stacks (optional)
  - Glue: Create crawlers/jobs (optional)
```

**Recommended:** Use an IAM user with `AdministratorAccess` or a custom policy with these permissions.

### Verify AWS Configuration

```bash
# Check current account and region
aws sts get-caller-identity
aws configure get region

# Set region if needed
export AWS_REGION=us-east-1

# Optional: Set AWS profile
export AWS_PROFILE=my-profile-name
```

---

## 🎯 Deployment Methods

### Method 1: Automated Migration Script (Recommended)

**Best for:** Moving to a new AWS account or fresh deployment

```bash
# Step 1: Review what will change (dry run)
./scripts/migrate_to_new_account.sh --env dev --dry-run

# Step 2: Execute migration
./scripts/migrate_to_new_account.sh --env dev

# Step 3: Follow prompts and wait for completion
```

**What it does:**
- ✅ Fixes hardcoded account references
- ✅ Updates configuration files
- ✅ Creates S3 buckets
- ✅ Deploys Lambda functions
- ✅ Configures EventBridge schedules
- ✅ Verifies deployment

### Method 2: Manual Step-by-Step

**Best for:** Understanding the process or custom deployments

#### Step 1: Fix Account References

```bash
# Update deployment bucket reference
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "noaa-deployment-${ACCOUNT_ID}-dev" > .deployment-bucket

# Fix Glue ETL script (if it exists)
if [ -f glue-etl/run-etl-now.sh ]; then
    sed -i.bak "s|899626030376|${ACCOUNT_ID}|g" glue-etl/run-etl-now.sh
fi
```

#### Step 2: Package Lambda Functions

```bash
cd scripts/
./package_all_lambdas.sh
```

This creates:
- Lambda deployment packages
- Layers with dependencies
- Uploads to S3 deployment bucket

#### Step 3: Deploy Infrastructure

```bash
./deploy_to_aws.sh --env dev --region us-east-1
```

This deploys:
- S3 buckets (data lake, athena results, deployment)
- Lambda functions (6 ingestion + 1 AI query)
- EventBridge schedules
- IAM roles and policies
- Athena databases

#### Step 4: Create Athena Tables

```bash
# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Run SQL to create Gold layer tables
aws athena start-query-execution \
  --query-string "$(cat sql/create-all-gold-tables.sql)" \
  --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-dev/ \
  --query-execution-context Database=noaa_gold_dev
```

#### Step 5: Verify Deployment

```bash
./scripts/verify_system.sh
```

---

## ✅ Verification Checklist

After deployment, verify each component:

### 1. S3 Buckets

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Should see 3-4 buckets
aws s3 ls | grep noaa

# Expected buckets:
# - noaa-federated-lake-{ACCOUNT_ID}-dev
# - noaa-athena-results-{ACCOUNT_ID}-dev
# - noaa-deployment-{ACCOUNT_ID}-dev
```

### 2. Lambda Functions

```bash
# Should see 6-7 functions
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' \
  --output table

# Expected functions:
# - noaa-ingest-atmospheric-dev
# - noaa-ingest-oceanic-dev
# - noaa-ingest-buoy-dev
# - noaa-ingest-climate-dev
# - noaa-ingest-terrestrial-dev
# - noaa-ingest-spatial-dev
# - noaa-ai-query-dev (optional)
```

### 3. EventBridge Rules

```bash
# Should see 18+ rules
aws events list-rules \
  --query 'Rules[?contains(Name, `noaa`)].{Name:Name,State:State}' \
  --output table

# All rules should show: State = ENABLED
```

### 4. Test Lambda Function Manually

```bash
# Trigger atmospheric ingestion
aws lambda invoke \
  --function-name noaa-ingest-atmospheric-dev \
  --invocation-type RequestResponse \
  --log-type Tail \
  response.json

# Check response
cat response.json

# Should see: "statusCode": 200
```

### 5. Verify Data Ingestion

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Wait 5-10 minutes after deployment, then check:
aws s3 ls s3://noaa-federated-lake-${ACCOUNT_ID}-dev/bronze/atmospheric/ \
  --recursive --human-readable | tail -10

# You should see fresh JSON files with today's date
```

### 6. Check Lambda Logs

```bash
# View recent logs
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev --follow

# Look for:
# - "Successfully wrote X records"
# - "Execution completed"
# - No ERROR messages
```

### 7. Verify Athena Database

```bash
# List databases
aws athena list-databases --catalog-name AwsDataCatalog \
  --query 'DatabaseList[?contains(Name, `noaa`)].Name'

# Expected: noaa_gold_dev or similar

# List tables
aws athena list-table-metadata \
  --catalog-name AwsDataCatalog \
  --database-name noaa_gold_dev \
  --query 'TableMetadataList[].Name'
```

---

## 🐛 Troubleshooting

### Issue: "No Lambda functions deployed"

**Symptoms:**
- `aws lambda list-functions` returns empty
- EventBridge rules show "No targets"

**Solution:**
```bash
# Check if deployment bucket exists
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 ls s3://noaa-deployment-${ACCOUNT_ID}-dev/

# If empty or doesn't exist, repackage and deploy
cd scripts/
./package_all_lambdas.sh
./deploy_to_aws.sh --env dev
```

### Issue: "Lambda execution errors"

**Symptoms:**
- Functions return errors in logs
- No data appearing in S3

**Check:**
```bash
# View detailed logs
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev \
  --since 30m \
  --follow

# Common issues:
# 1. Missing IAM permissions → Check execution role
# 2. API rate limiting → Normal, will retry
# 3. Network timeouts → Increase Lambda timeout
```

**Fix permissions:**
```bash
# Verify Lambda execution role has S3 write access
aws iam get-role --role-name noaa-lambda-execution-role-dev
```

### Issue: "EventBridge rules not triggering"

**Symptoms:**
- No recent Lambda executions
- No new data in S3

**Check:**
```bash
# Verify rule status
aws events list-rules \
  --query 'Rules[?contains(Name, `noaa`)].{Name:Name,State:State,Schedule:ScheduleExpression}'

# Check if rules have targets
aws events list-targets-by-rule \
  --rule noaa-ingest-atmospheric-schedule-dev
```

**Fix:**
```bash
# Re-add permission for EventBridge to invoke Lambda
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws lambda add-permission \
  --function-name noaa-ingest-atmospheric-dev \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:${ACCOUNT_ID}:rule/noaa-ingest-atmospheric-schedule-dev
```

### Issue: "No data in Bronze layer"

**Symptoms:**
- Lambda executes successfully
- But no files in `s3://noaa-federated-lake-*/bronze/`

**Debug:**
```bash
# Manually invoke Lambda and check output
aws lambda invoke \
  --function-name noaa-ingest-atmospheric-dev \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json

# Check CloudWatch logs for S3 write operations
aws logs filter-log-events \
  --log-group-name /aws/lambda/noaa-ingest-atmospheric-dev \
  --filter-pattern "s3.put_object"
```

### Issue: "Athena queries fail"

**Symptoms:**
- Tables not found
- Schema errors

**Fix:**
```bash
# Recreate Athena database
aws athena start-query-execution \
  --query-string "CREATE DATABASE IF NOT EXISTS noaa_gold_dev" \
  --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-dev/

# Recreate tables
aws athena start-query-execution \
  --query-string "$(cat sql/create-all-gold-tables.sql)" \
  --result-configuration OutputLocation=s3://noaa-athena-results-${ACCOUNT_ID}-dev/ \
  --query-execution-context Database=noaa_gold_dev
```

---

## 📊 System Health Check

Run this comprehensive health check:

```bash
#!/bin/bash
# health_check.sh

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ENV="dev"

echo "=== NOAA System Health Check ==="
echo ""

# 1. S3 Buckets
echo "📦 S3 Buckets:"
aws s3 ls | grep noaa | wc -l | xargs echo "  Found buckets:"

# 2. Lambda Functions
echo "⚡ Lambda Functions:"
aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' --output text | wc -w | xargs echo "  Found functions:"

# 3. EventBridge Rules
echo "⏰ EventBridge Rules:"
aws events list-rules --query 'Rules[?contains(Name, `noaa`)].Name' --output text | wc -w | xargs echo "  Found rules:"

# 4. Recent Data
echo "📊 Recent Data:"
RECENT_FILES=$(aws s3 ls s3://noaa-federated-lake-${ACCOUNT_ID}-${ENV}/bronze/atmospheric/ --recursive | grep "$(date +%Y-%m-%d)" | wc -l)
echo "  Files today: ${RECENT_FILES}"

# 5. Lambda Invocations (last hour)
echo "🔄 Recent Invocations:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=noaa-ingest-atmospheric-${ENV} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --query 'Datapoints[0].Sum' \
  --output text | xargs echo "  Last hour:"

echo ""
echo "✅ Health check complete"
```

Save as `health_check.sh`, make executable, and run:
```bash
chmod +x health_check.sh
./health_check.sh
```

---

## 🔄 Updating the System

### Update Lambda Code

```bash
# 1. Modify Lambda code in lambda-ingest-* directories
# 2. Repackage
cd scripts/
./package_all_lambdas.sh

# 3. Redeploy specific function
aws lambda update-function-code \
  --function-name noaa-ingest-atmospheric-dev \
  --s3-bucket noaa-deployment-${ACCOUNT_ID}-dev \
  --s3-key lambda/atmospheric_ingest.zip
```

### Update EventBridge Schedules

```bash
# Change schedule frequency
aws events put-rule \
  --name noaa-ingest-atmospheric-schedule-dev \
  --schedule-expression "rate(5 minutes)" \
  --state ENABLED
```

### Add New Data Pond

1. Create new Lambda function directory: `lambda-ingest-newpond/`
2. Add ingestion script: `newpond_ingest.py`
3. Update `package_all_lambdas.sh`
4. Deploy using `deploy_to_aws.sh`

---

## 💰 Cost Monitoring

### Check Current Costs

```bash
# Get cost for last 30 days
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '30 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter file://cost-filter.json

# cost-filter.json:
# {
#   "Tags": {
#     "Key": "Project",
#     "Values": ["NOAA-Federated-Lake"]
#   }
# }
```

### Expected Costs (dev environment)

```
Monthly Cost Estimate:
- Lambda:           $3-5
- S3 Storage:       $5-10
- Athena:           $2-3
- Data Transfer:    $1-2
- CloudWatch:       $2-3
- EventBridge:      <$1
- Bedrock (if AI):  $10-15
----------------------------
TOTAL:              $23-40/month
```

---

## 🎓 Next Steps

### 1. Set Up Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name NOAA-System-Health \
  --dashboard-body file://dashboard.json
```

### 2. Configure Alerts

```bash
# Alert on Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name noaa-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

### 3. Enable Cost Allocation Tags

```bash
# Add tags to all resources
aws resourcegroupstaggingapi tag-resources \
  --resource-arn-list $(aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionArn' --output text) \
  --tags Project=NOAA-Federated-Lake,Environment=dev,CostCenter=DataEngineering
```

### 4. Set Up Backups

```bash
# Enable S3 versioning
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3api put-bucket-versioning \
  --bucket noaa-federated-lake-${ACCOUNT_ID}-dev \
  --versioning-configuration Status=Enabled

# Enable S3 replication (for disaster recovery)
# See AWS documentation for cross-region replication setup
```

### 5. Implement Data Quality Checks

```bash
# Deploy data quality Lambda
cd lambda-data-quality/
zip -r quality.zip .
aws lambda create-function \
  --function-name noaa-data-quality-dev \
  --runtime python3.12 \
  --handler quality.lambda_handler \
  --zip-file fileb://quality.zip \
  --role arn:aws:iam::${ACCOUNT_ID}:role/noaa-lambda-execution-role-dev
```

---

## 📚 Additional Resources

- **Full Documentation:** See `README.md`
- **System Analysis:** See `SYSTEM_ANALYSIS_AND_PORTABILITY.md`
- **Operational Report:** See `OPERATIONAL_STATUS_REPORT.md`
- **Migration Script:** `scripts/migrate_to_new_account.sh`
- **AWS Best Practices:** https://docs.aws.amazon.com/wellarchitected/

---

## 🆘 Getting Help

### Check Logs

```bash
# All logs in one place
tail -f logs/deployment_*.log

# Lambda logs
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev --follow

# All NOAA log groups
aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `noaa`)].logGroupName'
```

### Common Commands Reference

```bash
# List all NOAA resources
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=NOAA-Federated-Lake

# Stop ingestion (disable all rules)
aws events list-rules --query 'Rules[?contains(Name, `noaa`)].Name' --output text | \
  xargs -I {} aws events disable-rule --name {}

# Resume ingestion (enable all rules)
aws events list-rules --query 'Rules[?contains(Name, `noaa`)].Name' --output text | \
  xargs -I {} aws events enable-rule --name {}
```

---

## ✅ Success Criteria

Your deployment is successful when:

- ✅ All 6-7 Lambda functions are deployed
- ✅ All EventBridge rules are enabled
- ✅ Fresh data appears in Bronze layer within 15 minutes
- ✅ No errors in Lambda CloudWatch logs
- ✅ Athena queries return results
- ✅ System costs are within expected range

**Congratulations! Your NOAA Federated Data Lake is operational! 🎉**

---

**Last Updated:** December 2025  
**Version:** 1.0  
**Maintained By:** Data Engineering Team