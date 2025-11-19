# NOAA Federated Data Lake - Deployment Checklist

> **Version:** 1.0  
> **Last Updated:** November 2024  
> **Purpose:** Complete deployment validation checklist for all environments

## 📋 Overview

This checklist ensures all components of the NOAA Federated Data Lake are properly deployed, configured, and validated across all 6 data ponds.

**Environments:** `dev` | `staging` | `prod`

---

## ✅ Pre-Deployment Checklist

### Prerequisites

- [ ] AWS account with appropriate permissions
- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] AWS credentials valid (`aws sts get-caller-identity`)
- [ ] Python 3.9+ installed (`python3 --version`)
- [ ] Git repository cloned
- [ ] NOAA CDO API token obtained (optional, for climate data)
- [ ] Target environment selected (`dev`, `staging`, or `prod`)

### AWS Account Verification

```bash
# Verify account ID
aws sts get-caller-identity

# Check region
aws configure get region

# Verify S3 access
aws s3 ls
```

- [ ] Account ID: _________________
- [ ] Region: us-east-1
- [ ] IAM permissions verified

### Python Dependencies

- [ ] boto3 installed
- [ ] requests installed
- [ ] pandas installed (optional)

```bash
pip3 install boto3 requests pandas
```

### Repository Setup

- [ ] Repository cloned to local machine
- [ ] All scripts have execute permissions
- [ ] Project structure validated

```bash
cd noaa_storefront
chmod +x scripts/*.sh
ls -la scripts/
```

---

## 🚀 Deployment Steps

### Phase 1: Lambda Function Packaging

**Command:**
```bash
./scripts/package_all_lambdas.sh --env [ENV] --upload --clean
```

**Verification:**
- [ ] All 8 Lambda functions packaged successfully
- [ ] Package sizes within limits (<50MB direct, <250MB uncompressed)
- [ ] Packages uploaded to S3 deployment bucket
- [ ] Deployment manifest generated

**Expected Output:**
```
✓ Package created: ingest-oceanic.zip (15MB)
✓ Package created: ingest-atmospheric.zip (12MB)
✓ Package created: ingest-climate.zip (14MB)
✓ Package created: ingest-spatial.zip (11MB)
✓ Package created: ingest-terrestrial.zip (13MB)
✓ Package created: ingest-buoy.zip (12MB)
✓ Package created: enhanced-handler.zip (18MB)
✓ Package created: intelligent-orchestrator.zip (20MB)
```

**Packages to Verify:**
- [ ] `ingest-oceanic.zip`
- [ ] `ingest-atmospheric.zip`
- [ ] `ingest-climate.zip`
- [ ] `ingest-spatial.zip`
- [ ] `ingest-terrestrial.zip`
- [ ] `ingest-buoy.zip`
- [ ] `enhanced-handler.zip`
- [ ] `intelligent-orchestrator.zip`

### Phase 2: Infrastructure Deployment

**Command:**
```bash
./scripts/deploy_to_aws.sh --env [ENV] --noaa-token [TOKEN] --force
```

**CloudFormation Stack:**
- [ ] Stack created/updated: `noaa-federated-lake-[ENV]`
- [ ] Stack status: `CREATE_COMPLETE` or `UPDATE_COMPLETE`
- [ ] No errors in stack events
- [ ] Outputs generated

**S3 Buckets Created:**
- [ ] `noaa-federated-lake-[ACCOUNT_ID]-[ENV]` - Data lake
- [ ] `noaa-athena-results-[ACCOUNT_ID]-[ENV]` - Query results
- [ ] `noaa-deployment-packages-[ACCOUNT_ID]-[ENV]` - Lambda packages

**Lambda Functions Deployed:**
- [ ] `NOAAIngestOceanic-[ENV]`
- [ ] `NOAAIngestAtmospheric-[ENV]`
- [ ] `NOAAIngestClimate-[ENV]`
- [ ] `NOAAIngestSpatial-[ENV]`
- [ ] `NOAAIngestTerrestrial-[ENV]`
- [ ] `NOAAIngestBuoy-[ENV]`
- [ ] `NOAAEnhancedQueryHandler-[ENV]`
- [ ] `NOAAIntelligentOrchestrator-[ENV]`

**IAM Roles Created:**
- [ ] Lambda execution roles with appropriate permissions
- [ ] S3 read/write permissions
- [ ] Athena query permissions
- [ ] CloudWatch Logs permissions

### Phase 3: Athena Configuration

**Database:**
- [ ] Database created: `noaa_gold_[ENV]`
- [ ] Database visible in Athena console

**Tables Created:**
- [ ] `oceanic_buoys`
- [ ] `oceanic_tides`
- [ ] `atmospheric_forecasts`
- [ ] `atmospheric_alerts`
- [ ] `climate_daily`
- [ ] `spatial_radar` (optional)
- [ ] `terrestrial_gauges` (optional)
- [ ] Additional pond-specific tables

**Verification Query:**
```sql
SHOW TABLES IN noaa_gold_[ENV];
```

### Phase 4: EventBridge Schedules

**Rules Created:**
- [ ] `NOAAIngestOceanic-[ENV]-schedule` - rate(15 minutes)
- [ ] `NOAAIngestAtmospheric-[ENV]-schedule` - rate(15 minutes)
- [ ] `NOAAIngestClimate-[ENV]-schedule` - rate(1 hour)
- [ ] `NOAAIngestSpatial-[ENV]-schedule` - rate(30 minutes)
- [ ] `NOAAIngestTerrestrial-[ENV]-schedule` - rate(30 minutes)
- [ ] `NOAAIngestBuoy-[ENV]-schedule` - rate(15 minutes)

**Verification:**
```bash
aws events list-rules --name-prefix "NOAAIngest"
```

- [ ] All rules in `ENABLED` state
- [ ] Targets configured correctly
- [ ] Lambda permissions granted

### Phase 5: Initial Data Ingestion

**Trigger Initial Load:**
```bash
aws lambda invoke \
  --function-name NOAAIngestOceanic-[ENV] \
  --invocation-type Event \
  --payload '{"env":"[ENV]"}' \
  response.json
```

**Repeat for each pond:**
- [ ] Oceanic pond invoked
- [ ] Atmospheric pond invoked
- [ ] Climate pond invoked
- [ ] Spatial pond invoked
- [ ] Terrestrial pond invoked
- [ ] Buoy pond invoked

**Wait Time:** 5-10 minutes for initial data collection

---

## 🧪 Validation Steps

### Step 1: Endpoint Validation

**Command:**
```bash
python3 scripts/validate_endpoints_and_queries.py --env [ENV] --test-queries
```

**Expected Results:**
- [ ] 20+ endpoints tested
- [ ] Success rate > 80%
- [ ] All critical endpoints responding
- [ ] No authentication errors
- [ ] Validation report generated

**Key Metrics:**
- Total endpoints tested: __________
- Successful: __________
- Failed: __________
- Success rate: __________%

### Step 2: Pond Testing

**Command:**
```bash
python3 tests/test_all_ponds.py --env [ENV]
```

**Oceanic Pond:**
- [ ] Bronze data exists (s3://bucket/bronze/oceanic/)
- [ ] Gold data exists (s3://bucket/gold/oceanic/)
- [ ] Athena tables queryable
- [ ] Data count > 10 records
- [ ] Recent data (< 24 hours old)

**Atmospheric Pond:**
- [ ] Bronze data exists
- [ ] Gold data exists
- [ ] Alert data present
- [ ] Forecast data present
- [ ] Multiple states covered

**Climate Pond:**
- [ ] Bronze data exists
- [ ] Gold data exists
- [ ] Historical data accessible
- [ ] Station metadata present

**Spatial Pond:**
- [ ] Metadata collected
- [ ] Product listings available

**Terrestrial Pond:**
- [ ] River gauge data present
- [ ] Precipitation data present

**Buoy Pond:**
- [ ] Real-time data collected
- [ ] Multiple buoy stations
- [ ] Marine conditions data

### Step 3: Medallion Architecture Validation

**Bronze Layer (Raw Data):**
```bash
aws s3 ls s3://noaa-federated-lake-[ACCOUNT_ID]-[ENV]/bronze/ --recursive | wc -l
```
- [ ] Files present in bronze/oceanic/
- [ ] Files present in bronze/atmospheric/
- [ ] Files present in bronze/climate/
- [ ] Files present in bronze/spatial/
- [ ] Files present in bronze/terrestrial/
- [ ] Total files: __________ (expect 50+)

**Silver Layer (Processed):**
- [ ] Transformation scripts exist
- [ ] Silver layer structure defined

**Gold Layer (Analytics-Ready):**
```bash
aws s3 ls s3://noaa-federated-lake-[ACCOUNT_ID]-[ENV]/gold/ --recursive | wc -l
```
- [ ] Files present in gold/oceanic/
- [ ] Files present in gold/atmospheric/
- [ ] Files present in gold/climate/
- [ ] Total files: __________ (expect 20+)

### Step 4: Athena Query Validation

**Test Query 1: Count Records**
```sql
SELECT COUNT(*) as total_records
FROM noaa_gold_[ENV].oceanic_buoys
WHERE date >= date_format(current_date - interval '7' day, '%Y-%m-%d');
```
- [ ] Query executes successfully
- [ ] Returns > 0 records
- [ ] Result count: __________

**Test Query 2: Recent Data**
```sql
SELECT MAX(date) as latest_date
FROM noaa_gold_[ENV].atmospheric_forecasts;
```
- [ ] Query executes successfully
- [ ] Date is recent (< 24 hours old)
- [ ] Latest date: __________

**Test Query 3: Federated Query**
```sql
SELECT 'oceanic' as pond, COUNT(*) as records 
FROM noaa_gold_[ENV].oceanic_buoys
UNION ALL
SELECT 'atmospheric', COUNT(*) 
FROM noaa_gold_[ENV].atmospheric_forecasts
UNION ALL
SELECT 'climate', COUNT(*) 
FROM noaa_gold_[ENV].climate_daily;
```
- [ ] Query executes successfully
- [ ] All ponds return data
- [ ] Results validated

### Step 5: Lambda Function Health

**Check CloudWatch Logs:**
```bash
aws logs tail /aws/lambda/NOAAIngestOceanic-[ENV] --since 1h
```

**For each Lambda function:**
- [ ] No error messages in logs
- [ ] Successful execution messages
- [ ] Data ingestion confirmed
- [ ] API calls successful
- [ ] S3 writes successful

**Lambda Metrics:**
- [ ] Duration < timeout (< 15 minutes)
- [ ] Memory usage < limit
- [ ] No throttling errors
- [ ] Invocation success rate > 95%

---

## 📊 Post-Deployment Verification

### Data Quality Checks

**Completeness:**
- [ ] All 6 ponds have data
- [ ] Data from last 24 hours present
- [ ] Multiple stations/locations per pond
- [ ] No empty partitions

**Freshness:**
- [ ] Oceanic data < 15 minutes old
- [ ] Atmospheric data < 15 minutes old
- [ ] Climate data < 1 hour old
- [ ] Buoy data < 15 minutes old

**Consistency:**
- [ ] No duplicate records
- [ ] Date partitions correct
- [ ] JSON structure valid
- [ ] Required fields present

### Performance Validation

**Lambda Execution Times:**
- [ ] Oceanic: < 5 minutes
- [ ] Atmospheric: < 5 minutes
- [ ] Climate: < 10 minutes
- [ ] Buoy: < 5 minutes

**Athena Query Performance:**
- [ ] Simple queries: < 5 seconds
- [ ] Federated queries: < 15 seconds
- [ ] No query timeouts

**S3 Storage:**
- [ ] Total size: __________ GB
- [ ] Within expected limits
- [ ] Lifecycle rules active

### Cost Verification

**Expected Monthly Costs (dev environment):**
- Lambda: $5-10
- S3: $2-5
- Athena: $5-20
- Data Transfer: $1-5
- **Total:** ~$15-40/month

- [ ] Costs within expected range
- [ ] No unexpected charges
- [ ] Billing alerts configured

---

## 🔍 Monitoring Setup

### CloudWatch Alarms

- [ ] Lambda error rate alarm
- [ ] Lambda duration alarm
- [ ] S3 storage alarm
- [ ] Athena query failure alarm

### CloudWatch Dashboards

- [ ] Ingestion metrics dashboard
- [ ] Query performance dashboard
- [ ] Data freshness dashboard

### Logs

- [ ] Lambda log groups created
- [ ] Retention period set (7-14 days)
- [ ] Log insights queries configured

---

## 🐛 Troubleshooting Checklist

If issues arise, verify:

**Lambda Failures:**
- [ ] IAM permissions correct
- [ ] Environment variables set
- [ ] NOAA APIs responding
- [ ] S3 bucket accessible
- [ ] No network issues

**No Data in Athena:**
- [ ] Lambda functions executing
- [ ] Data in S3 bronze/gold layers
- [ ] Partitions refreshed (MSCK REPAIR TABLE)
- [ ] Table schema correct

**High Costs:**
- [ ] Ingestion frequency appropriate
- [ ] No infinite loops
- [ ] Query optimization enabled
- [ ] Lifecycle rules active

**Data Quality Issues:**
- [ ] Source API returning valid data
- [ ] Transformation logic correct
- [ ] Schema matches expectations
- [ ] No data corruption

---

## ✍️ Sign-Off

### Deployment Information

- **Environment:** [ ] dev [ ] staging [ ] prod
- **Deployment Date:** __________
- **Deployed By:** __________
- **AWS Account ID:** __________
- **Region:** __________

### Verification Sign-Off

- [ ] All infrastructure deployed successfully
- [ ] All Lambda functions operational
- [ ] All data ponds collecting data
- [ ] Athena queries working
- [ ] Validation tests passed
- [ ] Documentation updated
- [ ] Team notified

### Final Checks

- [ ] Deployment report generated and reviewed
- [ ] Log files archived
- [ ] Monitoring configured
- [ ] Runbook updated
- [ ] Stakeholders informed

### Approval

**Technical Lead:** __________________ Date: __________

**Project Manager:** __________________ Date: __________

**Notes:**
```
[Add any deployment notes, issues encountered, or follow-up items]
```

---

## 📝 Post-Deployment Tasks

Within 24 hours:
- [ ] Monitor Lambda executions
- [ ] Verify data freshness
- [ ] Check error rates
- [ ] Review CloudWatch metrics

Within 1 week:
- [ ] Validate data quality
- [ ] Review cost metrics
- [ ] Optimize queries if needed
- [ ] Update documentation

Within 1 month:
- [ ] Performance review
- [ ] Cost optimization
- [ ] User feedback collected
- [ ] Enhancement planning

---

## 📚 References

- [Main README](../README.md)
- [Quick Start Guide](QUICKSTART_VALIDATION.md)
- [Chatbot Integration](CHATBOT_INTEGRATION_GUIDE.md)
- [Testing Framework](TESTING_FRAMEWORK_SUMMARY.md)

---

**Checklist Version:** 1.0  
**Last Updated:** November 2024  
**Next Review:** December 2024