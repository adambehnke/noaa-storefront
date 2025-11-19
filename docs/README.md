# NOAA Federated Data Lake - Documentation Hub

## Overview

This directory contains all documentation for the NOAA Federated Data Lake system, including testing guides, validation tools, and implementation references. These resources enable you to verify data flow from NOAA source APIs through the medallion architecture (Bronze → Silver → Gold) and into the federated chatbot API.

---

## 📚 Documentation Files

### Core Testing Documentation

#### 1. **NOAA_ENDPOINT_VALIDATION.md** (831 lines)
Comprehensive guide for testing each NOAA endpoint

**Contents:**
- Detailed testing methodology for all endpoints
- All NOAA endpoints organized by data pond (Oceanic, Atmospheric, Buoy, Climate, Spatial, Terrestrial)
- Expected responses with examples
- Bronze/Silver/Gold layer verification steps
- Federated API test queries
- Complete troubleshooting guide
- Implementation status tracking

**Use this when:** You need detailed information about a specific endpoint or want to understand the complete data flow.

---

#### 2. **CURL_EXAMPLES.md** (594 lines)
Quick reference guide with ready-to-use curl commands

**Contents:**
- Copy-paste curl commands for every NOAA endpoint
- Federated API query examples (single-pond, multi-pond, multi-question)
- AWS CLI commands for S3 and Athena
- Station reference tables (CO-OPS stations, NDBC buoys)
- Complete test flow scripts
- Troubleshooting commands

**Use this when:** You need to quickly test an endpoint without reading detailed documentation.

---

#### 3. **QUICKSTART_VALIDATION.md** (279 lines)
5-minute quick start guide

**Contents:**
- Immediate system health check
- Quick test queries
- Data lake verification commands
- Common troubleshooting steps
- What's working vs not yet implemented

**Use this when:** You want to test the system right now without setup.

---

### Summary & Status Documentation

#### 4. **TESTING_FRAMEWORK_SUMMARY.md** (504 lines)
Complete overview of testing framework and system state

**Contents:**
- Testing framework architecture
- Current system state and capabilities
- Data flow diagrams
- Implementation priorities and estimates
- Known limitations and design decisions
- Success criteria

**Use this when:** You need a complete picture of the system's current state and roadmap.

---

#### 5. **VALIDATION_FIXES.md** (327 lines)
Documentation of fixes applied to validation framework

**Contents:**
- Issues found during initial validation
- Root cause analysis
- Fixes applied
- Station capability reference
- Working test examples
- Test results summary

**Use this when:** You want to understand what issues were found and how they were resolved.

---

#### 6. **BASELINE_VALIDATION_REPORT.md**
Initial validation report with system health status

**Contents:**
- NOAA API endpoint test results
- Data lake layer verification
- Federated API test results
- System status summary

**Use this when:** You want to see the baseline validation results.

---

#### 7. **VALIDATION_DELIVERABLES.md**
Summary of deliverables and what was created

**Contents:**
- Documentation suite summary
- File organization structure
- Current system state
- Implementation recommendations
- Git commit suggestions

**Use this when:** You want to see what was delivered in this testing framework.

---

### Automation Tools

#### 8. **Validation Script** (../scripts/validate_all_endpoints.sh - 550 lines)
Automated testing script for all endpoints

**Features:**
- Tests all NOAA API endpoints
- Verifies Bronze layer data in S3
- Queries Gold layer via Athena
- Tests federated API responses
- Tests multi-pond queries
- Checks system health (S3, Athena, Lambda)
- Generates comprehensive markdown report
- Color-coded console output

**Use this when:** You want to run a complete system health check.

---

## Quick Start

### Prerequisites

```bash
# Required tools
- AWS CLI (configured with credentials)
- curl
- jq (JSON processor)
- Bash shell

# Install on macOS
brew install awscli jq

# Install on Linux
apt-get install awscli jq
```

### Run Complete Validation

```bash
# Navigate to project root
cd noaa_storefront

# Make script executable (if not already)
chmod +x scripts/validate_all_endpoints.sh

# Run validation for dev environment
./scripts/validate_all_endpoints.sh dev

# Run with verbose output
./scripts/validate_all_endpoints.sh dev --verbose
```

### Test a Single Endpoint

```bash
# Test water temperature API directly
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&time_zone=GMT&units=metric&format=json" | jq '.data[0]'

# Test via federated API
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in San Francisco?"}' | jq '.'
```

### Verify Data Lake Layers

```bash
# Check Bronze layer
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive | tail -10

# Check Gold layer
aws s3 ls s3://noaa-federated-lake-899626030376-dev/gold/oceanic/ --recursive

# Query via Athena
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.oceanic_aggregated ORDER BY date DESC LIMIT 5" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

---

## Current Implementation Status

### ✅ Fully Implemented

| Pond | Endpoint | Ingestion | Medallion | Federated API |
|------|----------|-----------|-----------|---------------|
| **Oceanic** | Water Temperature | ✅ | ✅ | ✅ |
| **Oceanic** | Water Levels | ✅ | ✅ | ✅ |
| **Atmospheric** | Weather Alerts | ✅ | Pass-through | ✅ |
| **Atmospheric** | Current Weather | ✅ | Pass-through | ✅ |
| **Atmospheric** | Forecasts | ✅ | Pass-through | ✅ |

**Status Legend:**
- ✅ = Fully operational
- Pass-through = API calls work but data not stored in medallion layers

### ⚠️ Partially Implemented

These endpoints are defined in the system but not yet ingested into the data lake:

- Oceanic: Tide Predictions, Currents, Salinity
- Atmospheric: Full medallion architecture (currently pass-through only)
- Spatial: Station/Zone metadata

### ❌ Not Yet Implemented

These ponds are designed but ingestion pipelines not yet built:

- **Buoy Pond** (NDBC) - Marine buoy observations
- **Climate Pond** (CDO) - Historical climate data (API token configured)
- **Terrestrial Pond** - Drought and soil moisture data

---

## Testing Workflow

### 1. Direct NOAA API Test
Verify the source endpoint is responding correctly.

```bash
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=water_temperature&station=9414290&date=latest&format=json" | jq '.'
```

### 2. Bronze Layer Verification
Confirm raw data landed in S3.

```bash
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/oceanic/water_temperature/ --recursive | tail -5
```

### 3. Gold Layer Query
Test aggregated data via Athena.

```bash
# This returns a query ID - you'll need to fetch results asynchronously
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.oceanic_aggregated LIMIT 5" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

### 4. Federated API Test
Query via the chatbot interface.

```bash
curl -s -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in San Francisco?"}' | jq '.'
```

### 5. Verify Data Provenance
Ensure the response correctly identifies the NOAA source.

The API response should include:
```json
{
  "answer": "...",
  "data_sources": [
    {
      "pond": "oceanic",
      "endpoint": "https://api.tidesandcurrents.noaa.gov/...",
      "lake_layer": "gold",
      "table": "oceanic_aggregated"
    }
  ]
}
```

---

## Example Test Queries

### Single Pond Queries

```bash
# Oceanic data
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the water temperature in San Francisco?"}'

# Weather alerts
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "Are there any severe weather warnings in California?"}'

# Current weather
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current weather in New York City?"}'
```

### Multi-Pond Queries

```bash
# Weather + Ocean
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in San Francisco and what is the water temperature?"}'

# Multiple questions
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Boston? What are the water levels? Any alerts in Massachusetts?"}'
```

---

## Troubleshooting

### No Data in Bronze Layer

**Problem:** S3 bronze folder is empty or outdated

**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-ingest-oceanic-dev --follow

# Check EventBridge schedule
aws events list-rules --name-prefix noaa-ingest
```

**Solution:**
```bash
# Manually trigger ingestion
aws lambda invoke \
  --function-name noaa-ingest-oceanic-dev \
  --payload '{"hours_back": 24, "env": "dev"}' \
  output.json
```

### Athena Query Fails

**Problem:** Gold layer queries return no results

**Solution:**
```bash
# Repair table partitions
aws athena start-query-execution \
  --query-string "MSCK REPAIR TABLE noaa_gold_dev.oceanic_aggregated" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-899626030376-dev/
```

### API Returns Error

**Problem:** Federated API returns 500 error

**Diagnosis:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/noaa-enhanced-handler-dev --follow

# Test Lambda directly
aws lambda invoke \
  --function-name noaa-enhanced-handler-dev \
  --payload '{"body": "{\"question\": \"test\"}"}' \
  response.json

cat response.json | jq '.'
```

---

## Next Steps for Implementation

### Priority 1: Complete Oceanic Pond
- [ ] Implement tide predictions ingestion
- [ ] Implement currents ingestion  
- [ ] Implement salinity ingestion
- [ ] Estimated effort: 2-3 days each

### Priority 2: Implement Buoy Pond
- [ ] Create NDBC text file parser
- [ ] Build Bronze/Silver/Gold pipeline
- [ ] Add to federated API routing
- [ ] Estimated effort: 3-5 days

### Priority 3: Add Climate Data
- [ ] Implement CDO API integration (token already configured)
- [ ] Build historical data ingestion
- [ ] Create aggregation queries
- [ ] Estimated effort: 5-7 days

### Priority 4: Full Atmospheric Medallion
- [ ] Store weather alerts in Bronze/Silver/Gold (currently pass-through)
- [ ] Store forecast data in medallion layers
- [ ] Add historical weather tracking
- [ ] Estimated effort: 3-5 days

---

## Automated Testing

### Daily Validation

Set up automated daily testing:

```bash
# Add to crontab
0 6 * * * /path/to/noaa_storefront/scripts/validate_all_endpoints.sh dev > /var/log/noaa-validation.log 2>&1
```

### CI/CD Integration

For GitHub Actions or similar:

```yaml
name: NOAA Endpoint Validation
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Run Validation
        run: ./scripts/validate_all_endpoints.sh dev
```

---

## Report Generation

The validation script automatically generates a markdown report:

```bash
# Run validation
./scripts/validate_all_endpoints.sh dev

# Report is saved as
validation_report_YYYYMMDD_HHMMSS.md

# View report
cat validation_report_*.md
```

**Report includes:**
- Test summary with pass/fail/warning counts
- Success rate percentage
- Detailed results for each endpoint
- Recommendations for fixes
- Next steps for implementation

---

## Additional Resources

- **Main Project Documentation:** `../NOAA_FEDERATED_DATA_LAKE_WHITEPAPER.md`
- **API Documentation:** `../MULTI_POND_ARCHITECTURE.md`
- **SQL Schemas:** `../COMPREHENSIVE_SQL_SCHEMA.sql`
- **Deployment Guide:** Check CloudFormation templates in project root

---

## Contact & Support

For questions or issues:
1. Check the troubleshooting section in `NOAA_ENDPOINT_VALIDATION.md`
2. Review Lambda logs in CloudWatch
3. Check S3 bucket permissions and data
4. Verify Athena table schemas

---

## Version History

- **v1.0** (2024) - Initial comprehensive testing documentation
  - Complete endpoint validation guide
  - Automated testing script
  - Curl command reference
  - Current implementation: Oceanic pond (water temp, water levels)

---

**Last Updated:** 2024  
**Maintained by:** NOAA Federated Data Lake Team