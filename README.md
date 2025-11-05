# NOAA Federated Data Lake - AWS Implementation

A complete end-to-end implementation of NOAA's federated data lake using AWS services, featuring medallion architecture (Bronze → Silver → Gold), AI-powered querying with Amazon Bedrock, and real-time data ingestion from multiple NOAA endpoints.

## 🏗️ Architecture Overview

### AWS Stack (Databricks Replacement)

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| **Data Storage** | Amazon S3 | Bronze/Silver/Gold layer storage |
| **ETL Processing** | AWS Glue | PySpark-based data transformations |
| **Data Catalog** | AWS Glue Catalog | Metadata management and schema registry |
| **Query Engine** | Amazon Athena | Serverless SQL queries on S3 data |
| **AI/NLP** | Amazon Bedrock (Claude) | Natural language to SQL translation |
| **API Layer** | Lambda + API Gateway | RESTful API endpoints |
| **Caching** | ElastiCache Redis | Query result caching |
| **Orchestration** | Step Functions | Medallion pipeline workflow |
| **Scheduling** | EventBridge | Automated data ingestion (6-hour intervals) |
| **Monitoring** | CloudWatch + SNS | Logs, metrics, and alerts |

### Medallion Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  NOAA APIs (NWS, Tides & Currents, CDO, NCEI)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  BRONZE LAYER (Raw Ingestion)                              │
│  • JSON files partitioned by date/region                   │
│  • Minimal transformation                                   │
│  • 90-day retention                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  SILVER LAYER (Cleaned & Normalized)                       │
│  • Schema validation                                        │
│  • Deduplication                                            │
│  • Type conversion                                          │
│  • 365-day retention                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  GOLD LAYER (Analytics-Ready)                              │
│  • Parquet format                                           │
│  • Aggregations & enrichment                                │
│  • Optimized for queries                                    │
│  • 730-day retention                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  API + AI Query Layer                                      │
│  • REST API with Redis caching                             │
│  • Bedrock-powered natural language queries                │
│  • Athena SQL execution                                     │
└─────────────────────────────────────────────────────────────┘
```

## 📊 Data Ponds & Endpoints

### MVP Implementation (3 Priority Services)

Based on the specs, we're implementing **25 endpoints across 6+ ponds**:

#### 1. **Atmospheric Pond** (~48%, 12 endpoints)
**Primary Service: NWS API** (National Weather Service)
- ✅ Active Weather Alerts
- ✅ Weather Observations (current conditions)
- ✅ Forecast Zones
- ✅ Radar Stations
- Forecast Grids (7-day forecasts)
- Points (location-based forecasts)
- Stations metadata
- Glossary
- Products (text bulletins)
- Offices
- Zones (fire weather, county)
- Gridpoints

**Base URL:** `https://api.weather.gov`
**Authentication:** None required (rate limited to ~5 req/sec)

#### 2. **Oceanic Pond** (~16%, 4 endpoints)
**Primary Service: Tides & Currents API** (CO-OPS)
- ✅ Water Levels (tides)
- ✅ Water Temperature
- ✅ Meteorological Data (wind, air temp, pressure)
- ✅ Tide Predictions

**Base URL:** `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`
**Authentication:** None required

#### 3. **Restricted Pond** (~28%, 7 endpoints, overlapping)
**Primary Service: CDO (Climate Data Online)**
- ✅ Climate Data (GHCND dataset)
- Datasets
- Data Types
- Locations
- Stations
- Data Categories
- Location Categories

**Base URL:** `https://www.ncdc.noaa.gov/cdo-web/api/v2/`
**Authentication:** API Token required (get at https://www.ncdc.noaa.gov/cdo-web/token)

#### 4. **Terrestrial Pond** (~8%, 2 endpoints)
- Soil moisture
- Vegetation indices

#### 5. **Spatial Pond** (~8%, 2 endpoints)
- GIS layers
- Boundary data

#### 6. **Multi-Type Pond** (~12%, 3 endpoints)
- Cross-domain queries
- Composite datasets

## 🚀 Quick Start

### Prerequisites

1. **AWS Account** with administrative access
2. **AWS CLI** installed and configured
3. **Tools:**
   ```bash
   # macOS
   brew install awscli jq python3
   
   # Linux
   apt-get install awscli jq python3
   ```
4. **NOAA API Token** (optional for CDO): https://www.ncdc.noaa.gov/cdo-web/token

### Setup Instructions

#### Step 1: Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

#### Step 2: Get NOAA CDO API Token (Optional)

1. Visit https://www.ncdc.noaa.gov/cdo-web/token
2. Enter your email
3. Check your email for the token
4. Export it as environment variable:
   ```bash
   export NOAA_CDO_TOKEN="your_token_here"
   ```

#### Step 3: Deploy the Stack

```bash
# Make the deployment script executable
chmod +x deploy.sh

# Deploy to dev environment in us-east-1
./deploy.sh dev us-east-1

# Or deploy to production
./deploy.sh prod us-east-1
```

The deployment takes approximately **10-15 minutes** and creates:
- 3 S3 buckets (data lake, Athena results, Lambda code)
- 3 Glue databases (Bronze, Silver, Gold)
- 5 Glue ETL jobs (NWS, Tides, CDO ingestion + transformations)
- 2 Lambda functions (AI Query, Data API)
- 1 API Gateway
- 1 ElastiCache Redis cluster
- 1 Step Functions state machine
- 1 EventBridge scheduled trigger
- All necessary IAM roles and policies

#### Step 4: Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].StackStatus'

# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`APIEndpoint`].OutputValue' \
  --output text)

echo "API Endpoint: $API_ENDPOINT"

# Test health check
curl "${API_ENDPOINT}/data?ping=true"
```

## 📡 API Usage

### Data Query API

#### Basic Data Query

```bash
# Get atmospheric data for California
curl "${API_ENDPOINT}/data?service=atmospheric&region=CA&limit=10"

# Get oceanic data (tides)
curl "${API_ENDPOINT}/data?service=oceanic&region=West%20Coast&limit=20"

# Get data with date range
curl "${API_ENDPOINT}/data?service=nws&start_date=2024-01-01&end_date=2024-01-31&limit=50"
```

#### Query Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `service` | string | Service type: `nws`, `atmospheric`, `oceanic`, `tides`, `cdo` | `atmospheric` |
| `region` | string | State code (CA, TX) or region name | None (all regions) |
| `start_date` | string | Start date (YYYY-MM-DD) | 7 days ago |
| `end_date` | string | End date (YYYY-MM-DD) | Today |
| `limit` | integer | Max records to return | 100 |
| `fields` | string | Comma-separated fields or `*` for all | `*` |
| `ping` | boolean | Health check | false |

#### Response Format

```json
{
  "source": "cache",
  "service": "atmospheric",
  "data": [
    {
      "region": "CA",
      "event_type": "Heat Advisory",
      "severity": "Moderate",
      "alert_count": 12,
      "date": "2024-01-15"
    }
  ],
  "count": 1,
  "parameters": {
    "service": "atmospheric",
    "region": "CA",
    "start_date": "2024-01-08",
    "end_date": "2024-01-15",
    "limit": 100
  }
}
```

### AI Query API

Ask questions in natural language and get SQL results!

```bash
# Natural language query
curl -X POST "${API_ENDPOINT}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "ai_query",
    "question": "Show me all weather alerts in California from last week"
  }'

# Another example
curl -X POST "${API_ENDPOINT}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "ai_query",
    "question": "What is the average water temperature in San Francisco?"
  }'

# Direct SQL query
curl -X POST "${API_ENDPOINT}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "query",
    "sql": "SELECT * FROM noaa_gold_dev.atmospheric_aggregated LIMIT 10"
  }'
```

## 🔄 Data Ingestion Pipeline

### Manual Trigger

```bash
# Get the state machine ARN
STATE_MACHINE_ARN=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
  --output text)

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn "${STATE_MACHINE_ARN}" \
  --name "manual-run-$(date +%s)"
```

### Pipeline Stages

1. **Ingest NWS Data** → Bronze layer (alerts, observations, zones)
2. **Ingest Tides Data** → Bronze layer (water levels, temps, predictions)
3. **Ingest CDO Data** → Bronze layer (climate data)
4. **Bronze → Silver** → Clean and normalize
5. **Silver → Gold** → Aggregate and enrich
6. **Notify** → SNS notification on success/failure

### Automated Schedule

The pipeline runs automatically **every 6 hours** via EventBridge:
- 00:00 UTC
- 06:00 UTC
- 12:00 UTC
- 18:00 UTC

### Monitor Pipeline

```bash
# View recent executions
aws stepfunctions list-executions \
  --state-machine-arn "${STATE_MACHINE_ARN}" \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn "<execution-arn>"
```

## 🗂️ Data Access with Athena

### Using AWS Console

1. Go to Athena: https://console.aws.amazon.com/athena/
2. Select workgroup: `primary`
3. Choose database: `noaa_gold_dev`
4. Run queries:

```sql
-- View available tables
SHOW TABLES;

-- Query atmospheric data
SELECT region, event_type, severity, alert_count, date
FROM atmospheric_aggregated
WHERE date >= DATE '2024-01-01'
ORDER BY date DESC
LIMIT 10;

-- Query oceanic data
SELECT station_id, region, avg_water_level, avg_water_temp, date
FROM oceanic_aggregated
WHERE region = 'West Coast'
ORDER BY date DESC
LIMIT 10;
```

### Using AWS CLI

```bash
# Start query execution
QUERY_ID=$(aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.atmospheric_aggregated LIMIT 10" \
  --query-execution-context Database=noaa_gold_dev \
  --result-configuration OutputLocation=s3://noaa-athena-results-${AWS_ACCOUNT_ID}-dev/ \
  --query 'QueryExecutionId' \
  --output text)

# Wait for completion
aws athena get-query-execution \
  --query-execution-id "${QUERY_ID}"

# Get results
aws athena get-query-results \
  --query-execution-id "${QUERY_ID}"
```

## 📦 S3 Data Structure

```
s3://noaa-federated-lake-{account-id}-dev/
├── bronze/
│   ├── atmospheric/
│   │   ├── nws_alerts/
│   │   │   ├── date=2024-01-15/
│   │   │   │   └── alerts_20240115_120000.json
│   │   │   └── state=CA/
│   │   │       └── date=2024-01-15/
│   │   │           └── alerts_20240115_120000.json
│   │   ├── nws_observations/
│   │   ├── nws_forecast_zones/
│   │   └── nws_radar_stations/
│   └── oceanic/
│       ├── water_levels/
│       ├── water_temperature/
│       ├── meteorological/
│       └── tide_predictions/
├── silver/
│   ├── atmospheric_cleaned/
│   └── oceanic_cleaned/
└── gold/
    ├── atmospheric_aggregated/
    └── oceanic_aggregated/
```

## 🛠️ Troubleshooting

### Issue: Lambda timeout when querying large datasets

**Solution:** Increase pagination or add more specific filters:
```bash
curl "${API_ENDPOINT}/data?service=atmospheric&region=CA&limit=10"
```

### Issue: Redis connection errors

**Check:** Ensure Lambda is in VPC and can reach Redis:
```bash
aws elasticache describe-cache-clusters \
  --cache-cluster-id <cluster-id> \
  --show-cache-node-info
```

### Issue: Glue job fails with "No data found"

**Check:** Verify data exists in Bronze layer:
```bash
DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name noaa-federated-lake-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DataLakeBucketName`].OutputValue' \
  --output text)

aws s3 ls "s3://${DATA_LAKE_BUCKET}/bronze/atmospheric/" --recursive
```

### Issue: NWS API rate limiting

**Solution:** The ingestion script includes retry logic with exponential backoff. If persistent, reduce the number of sample stations in `bronze_ingest_nws_enhanced.py`.

### View Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/noaa-ai-query-dev --follow

# Glue job logs
aws logs tail /aws-glue/jobs/output --follow
```

## 🎯 Next Steps

### Phase 1: Complete MVP (Weeks 1-4)
- [x] Set up AWS infrastructure
- [x] Implement Bronze layer ingestion (NWS, Tides, CDO)
- [x] Create Silver layer transformations
- [x] Build Gold layer aggregations
- [x] Deploy AI Query API with Bedrock
- [x] Set up Redis caching
- [ ] **Test with real NOAA data**
- [ ] **Fine-tune Bedrock prompts for better SQL generation**
- [ ] **Add monitoring dashboards**

### Phase 2: Additional Endpoints (Weeks 5-8)
- [ ] Add remaining atmospheric endpoints (9 more)
- [ ] Implement terrestrial pond (soil moisture, vegetation)
- [ ] Implement spatial pond (GIS layers)
- [ ] Add multi-type pond for cross-domain queries
- [ ] Implement EMWIN for restricted data

### Phase 3: Frontend & UX (Weeks 9-12)
- [ ] Build React dashboard with Tailwind CSS
- [ ] Add data visualization (charts, maps)
- [ ] Implement user authentication (Cognito)
- [ ] Create persona-based views
- [ ] Add export functionality (CSV, JSON, Parquet)

### Phase 4: Optimization (Weeks 13+)
- [ ] Implement data partitioning strategies
- [ ] Add compression (Snappy, Zstandard)
- [ ] Optimize Athena queries with partitions
- [ ] Set up cost monitoring and alerts
- [ ] Implement data quality checks
- [ ] Add automated testing

## 💰 Cost Estimates (Monthly, Dev Environment)

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| S3 Storage | 1 TB | $23 |
| Glue Jobs | 20 runs/day × 5 DPUs × 15 min | $150 |
| Athena | 1 TB scanned | $5 |
| Lambda | 100K invocations | $0.20 |
| ElastiCache | t3.micro × 730 hrs | $12 |
| API Gateway | 100K requests | $0.35 |
| **Total** | | **~$190/month** |

**Production:** Expect 2-3x higher costs due to increased data volume and traffic.

## 📚 References

### NOAA APIs
- NWS API Docs: https://www.weather.gov/documentation/services-web-api
- Tides & Currents: https://api.tidesandcurrents.noaa.gov/api/prod/
- CDO API: https://www.ncdc.noaa.gov/cdo-web/webservices/v2

### AWS Services
- AWS Glue: https://docs.aws.amazon.com/glue/
- Amazon Athena: https://docs.aws.amazon.com/athena/
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/
- Step Functions: https://docs.aws.amazon.com/step-functions/

## 📝 License

This project is for NOAA data lake implementation. Ensure compliance with NOAA data usage policies.

## 🤝 Contributing

1. Test changes in dev environment first
2. Update documentation for any new endpoints
3. Follow AWS best practices for security
4. Add monitoring for new services

## 📧 Support

For issues or questions:
- Check logs in CloudWatch
- Review Athena query history
- Monitor Step Functions executions
- Check SNS notifications for pipeline alerts

---

**Built with ❤️ using AWS services instead of Databricks**