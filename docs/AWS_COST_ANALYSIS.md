# AWS Architecture Cost Analysis - NOAA Federated Data Lake

**Document Version:** 1.0  
**Date:** 2024  
**Purpose:** Architectural cost analysis for porting to NOAA AWS account  
**Current Environment:** Dev (Account: 899626030376)

---

## Executive Summary

The NOAA Federated Data Lake is a serverless, medallion-architecture data platform ingesting from 25+ NOAA API endpoints across 6 specialized data ponds. This document provides a comprehensive inventory of AWS resources and cost projections based on query volume.

**Current Status:**
- ✅ Fully operational in development account
- ✅ 6 data ponds actively ingesting
- ✅ 398+ files / ~175 MB of data (growing)
- ✅ Real-time ingestion (5-60 minute intervals)

---

## 1. AWS Services Inventory

### 1.1 Compute Resources

#### Lambda Functions (11 Total)

| Function Name | Runtime | Memory | Timeout | Trigger | Frequency |
|--------------|---------|--------|---------|---------|-----------|
| **noaa-ingest-atmospheric-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Every 5 min |
| **noaa-ingest-oceanic-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Every 5 min |
| **noaa-ingest-buoy-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Every 5 min |
| **noaa-ingest-climate-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Every 1 hour |
| **noaa-ingest-terrestrial-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Every 30 min |
| **noaa-ingest-spatial-dev** | Python 3.12 | 512 MB | 300s | EventBridge | Daily |
| **noaa-ai-query-dev** | Python 3.12 | 1024 MB | 300s | API Gateway | On-demand |
| **noaa-data-api-dev** | Python 3.12 | 1024 MB | 120s | API Gateway | On-demand |
| **noaa-enhanced-handler-dev** | Python 3.12 | 1024 MB | 300s | API Gateway | On-demand |

**Typical Execution Times:**
- Ingestion functions: 30-180 seconds per execution
- Query functions: 1-5 seconds per request

#### AWS Glue ETL Jobs (5+ Jobs)

| Job Name | Type | Workers | Worker Type | Frequency |
|----------|------|---------|-------------|-----------|
| **BronzeToSilver-Atmospheric** | ETL | 2 | G.1X | Every 15 min |
| **BronzeToSilver-Oceanic** | ETL | 2 | G.1X | Every 15 min |
| **BronzeToSilver-Buoy** | ETL | 2 | G.1X | Every 15 min |
| **SilverToGold-Aggregation** | ETL | 2 | G.1X | Every 30 min |
| **BronzeIngest-NWS** | PythonShell | N/A | 0.0625 DPU | On-demand |
| **BronzeIngest-CDO** | PythonShell | N/A | 0.0625 DPU | Hourly |

**Glue Crawlers (6+ Crawlers):**
- Atmospheric crawler (3 tables)
- Oceanic crawler (3 tables)
- Buoy crawler (2 tables)
- Climate crawler
- Terrestrial crawler
- Spatial crawler
- Frequency: Every 30 minutes

### 1.2 Storage Resources

#### S3 Buckets (2 Primary)

**Data Lake Bucket:** `noaa-federated-lake-{AccountId}-dev`

| Layer | Path | Data Type | Retention | Current Size | Growth Rate |
|-------|------|-----------|-----------|--------------|-------------|
| Bronze | `/bronze/` | Raw JSON | 90 days | ~60 MB | 10-15 MB/day |
| Silver | `/silver/` | Parquet | 365 days | ~60 MB | 8-12 MB/day |
| Gold | `/gold/` | Parquet (optimized) | 730 days | ~55 MB | 5-8 MB/day |

**Sub-paths (6 ponds):**
- `/bronze|silver|gold/atmospheric/` - Observations, alerts, stations, forecasts
- `/bronze|silver|gold/oceanic/` - Water levels, tides, wind, currents
- `/bronze|silver|gold/buoy/` - Metadata, wave data
- `/bronze|silver|gold/climate/` - Daily climate records
- `/bronze|silver|gold/terrestrial/` - River flow, gauges
- `/bronze|silver|gold/spatial/` - Geographic data

**Athena Results Bucket:** `noaa-athena-results-{AccountId}-dev`
- Query results storage
- Retention: 30 days
- Size: ~5-10 MB
- Growth: 50-100 MB/month with active querying

**Deployment Bucket:** `noaa-lambda-deployment-{AccountId}`
- Lambda function packages
- Glue ETL scripts
- Size: ~50-100 MB (static)

**Total Current Storage:** ~175 MB (initial state)  
**Projected Monthly Growth:** 700 MB - 1.2 GB/month

### 1.3 Database Resources

#### AWS Glue Databases (3)

| Database | Purpose | Tables | Partitions |
|----------|---------|--------|------------|
| **noaa_bronze_dev** | Raw ingestion | 6+ | Time-based (hourly) |
| **noaa_silver_dev** | Cleaned/normalized | 6+ | Time-based (daily) |
| **noaa_gold_dev** | Analytics-ready | 15+ | Time-based (daily) |

**Gold Layer Tables (Primary Queryable):**
- `atmospheric_observations` - Weather observations
- `atmospheric_alerts` - Active warnings/alerts
- `atmospheric_stations` - Station metadata
- `atmospheric_forecasts` - Weather forecasts
- `oceanic_water_level` - Tide/water level data
- `oceanic_wind` - Wind measurements
- `oceanic_tides` - Tide predictions
- `buoy_metadata` - Buoy station info
- `climate_daily` - Daily climate records
- `terrestrial_flow` - River flow data
- `spatial_geographic` - Geographic metadata
- Plus aggregated/summary tables

#### ElastiCache Redis

| Configuration | Specification |
|---------------|---------------|
| **Node Type** | cache.t3.micro (configurable) |
| **Engine** | Redis 6.x |
| **Nodes** | 1 |
| **Memory** | 0.5 GB |
| **VPC** | Private subnets |
| **Purpose** | Query result caching |

### 1.4 API & Networking

#### API Gateway (2 APIs)

**AI Query API:** `noaa-ai-query-api-dev`
- Type: REST API
- Endpoints: `/query` (POST), `/data` (GET)
- Authorization: None (can add IAM/Cognito)
- Throttling: Default (10,000 req/sec burst)
- CORS: Enabled

**Validation API:** `noaa-validation-api-dev` (if deployed)
- Endpoint validation
- Health checks

#### CloudFront Distribution

| Setting | Value |
|---------|-------|
| **Distribution ID** | d244ik6grpfthq |
| **Origin** | API Gateway |
| **Cache Behavior** | Disabled (cache-control: no-cache) |
| **SSL Certificate** | Default CloudFront |
| **Purpose** | Web application hosting + API proxy |

#### VPC Configuration

| Component | Configuration |
|-----------|---------------|
| **VPC CIDR** | 10.0.0.0/16 |
| **Private Subnets** | 2 subnets (10.0.1.0/24, 10.0.2.0/24) |
| **Availability Zones** | us-east-1a, us-east-1b |
| **NAT Gateway** | Not currently deployed (Lambda uses VPC endpoints) |
| **VPC Endpoints** | S3, Glue (for private communication) |

### 1.5 Orchestration & Monitoring

#### Step Functions

**State Machine:** `noaa-medallion-pipeline-dev`
- Purpose: Bronze → Silver → Gold ETL orchestration
- Trigger: EventBridge (every 6 hours)
- Steps: Ingest → Transform → Aggregate → Crawl
- Average Duration: 10-15 minutes per run

#### EventBridge Rules

| Rule Name | Schedule | Target |
|-----------|----------|--------|
| **noaa-ingest-atmospheric-schedule** | rate(5 minutes) | Lambda: atmospheric |
| **noaa-ingest-oceanic-schedule** | rate(5 minutes) | Lambda: oceanic |
| **noaa-ingest-buoy-schedule** | rate(5 minutes) | Lambda: buoy |
| **noaa-ingest-climate-schedule** | rate(1 hour) | Lambda: climate |
| **noaa-ingest-terrestrial-schedule** | rate(30 minutes) | Lambda: terrestrial |
| **noaa-ingest-spatial-schedule** | cron(0 0 * * ? *) | Lambda: spatial |
| **noaa-pipeline-trigger** | rate(6 hours) | Step Functions |
| **noaa-etl-trigger-atmospheric-obs** | rate(15 minutes) | Glue ETL |
| **noaa-etl-trigger-oceanic** | rate(15 minutes) | Glue ETL |
| **noaa-crawler-trigger** | rate(30 minutes) | Glue Crawlers |

#### CloudWatch

- **Log Groups:** 11+ (one per Lambda + Glue jobs)
- **Retention:** 7 days (default, configurable)
- **Metrics:** Lambda invocations, duration, errors, throttles
- **Log Size:** ~50-100 MB/day with current ingestion

#### SNS Topics

**Topic:** `noaa-pipeline-notifications-dev`
- Purpose: ETL pipeline alerts
- Subscribers: Email (configurable)

---

## 2. Current Resource Utilization

### 2.1 Storage Breakdown (Current State)

```
Total Data Lake Storage: ~175 MB

Bronze Layer (Raw JSON):
├── atmospheric/     ~50 MB (50 observations + 50 alerts)
├── oceanic/         ~30 MB (72 water level + wind records)
├── buoy/            ~495 KB (metadata files)
├── climate/         ~20 MB (hourly updates)
├── terrestrial/     ~10 MB (30-min updates)
└── spatial/         ~5 MB (daily updates)

Silver Layer (Cleaned Parquet):
├── atmospheric/     ~45 MB
├── oceanic/         ~28 MB
├── buoy/            ~450 KB
├── climate/         ~18 MB
├── terrestrial/     ~9 MB
└── spatial/         ~5 MB

Gold Layer (Analytics Parquet):
├── atmospheric/     ~40 MB (aggregated observations, alerts)
├── oceanic/         ~25 MB (aggregated tide/wind data)
├── buoy/            ~400 KB
├── climate/         ~15 MB
├── terrestrial/     ~8 MB
└── spatial/         ~5 MB
```

### 2.2 Compute Utilization (Daily Average)

**Lambda Invocations per Day:**
```
Ingestion Lambdas:
- Atmospheric:    288 invocations/day (5 min) × 60-120s = 576-1,152 min
- Oceanic:        288 invocations/day (5 min) × 60-120s = 576-1,152 min
- Buoy:           288 invocations/day (5 min) × 30-90s  = 288-864 min
- Climate:        24 invocations/day (1 hr)  × 60-180s = 24-72 min
- Terrestrial:    48 invocations/day (30 min) × 45-90s = 36-72 min
- Spatial:        1 invocation/day (daily)    × 60s     = 1 min

Total Ingestion: ~937 invocations/day
Total Compute Time: ~1,501-3,313 minutes/day (512 MB memory)

Query Lambdas (variable based on usage):
- Estimated 100-1,000 queries/day during active use
- Average 2-5 seconds per query
- Memory: 1024 MB
```

**Glue ETL Jobs per Day:**
```
- Atmospheric ETL: 96 runs/day (15 min) × 5 min × 2 DPU = 960 DPU-minutes
- Oceanic ETL:     96 runs/day (15 min) × 5 min × 2 DPU = 960 DPU-minutes
- Buoy ETL:        96 runs/day (15 min) × 3 min × 2 DPU = 576 DPU-minutes
- Gold Aggregation: 48 runs/day (30 min) × 8 min × 2 DPU = 768 DPU-minutes

Total: ~3,264 DPU-minutes/day = ~54.4 DPU-hours/day
```

**Glue Crawlers per Day:**
```
- 6 crawlers × 48 runs/day (30 min intervals)
- Average 2-5 minutes per run
- Total: ~576-1,440 crawler-minutes/day
```

### 2.3 Network Traffic

**Data Ingestion (API to Lambda):**
- Inbound: ~10-15 MB/day from NOAA APIs
- Outbound to S3: ~10-15 MB/day

**Query Traffic (CloudFront/API Gateway):**
- Varies by usage: 100-1,000 requests/day currently
- Average response: 10-50 KB per query
- Monthly: 30-150 MB

**Data Transfer:**
- Minimal (within same region: S3 ↔ Lambda ↔ Glue ↔ Athena)
- Cross-region: None currently

---

## 3. Cost Projections by Query Volume

### 3.1 Baseline Costs (Fixed/Scheduled Operations)

These costs occur regardless of query volume:

#### Lambda Ingestion (Scheduled)
```
Monthly Invocations: 937 × 30 = 28,110
Compute Time: ~1,500 minutes/day × 30 = 45,000 minutes
Memory: 512 MB = 0.5 GB
GB-seconds: 45,000 min × 60 × 0.5 = 1,350,000 GB-seconds
Cost: (1,350,000 - 400,000 free tier) × $0.0000166667 = $15.83/month
```

#### Glue ETL Jobs
```
Monthly DPU-hours: 54.4 × 30 = 1,632 DPU-hours
Cost: 1,632 × $0.44 = $718.08/month
```

#### Glue Crawlers
```
Monthly crawler-hours: ~1,000 minutes/day × 30 ÷ 60 = 500 hours
Cost: 500 × $0.44 = $220/month
```

#### S3 Storage (Growing)
```
Month 1: 1 GB × $0.023 = $0.02
Month 6: 6 GB × $0.023 = $0.14
Month 12: 12 GB × $0.023 = $0.28
Year 2: 24 GB × $0.023 = $0.55/month (with lifecycle policies)
```

#### S3 Requests (Ingestion)
```
PUT requests: ~1,000/day × 30 = 30,000/month
Cost: 30,000 × $0.005/1000 = $0.15
GET requests (ETL): ~5,000/day × 30 = 150,000/month
Cost: 150,000 × $0.0004/1000 = $0.06
```

#### ElastiCache Redis
```
cache.t3.micro: $0.017/hour × 730 hours = $12.41/month
```

#### CloudWatch Logs
```
Ingestion: ~2 GB/month × $0.50 = $1.00
Storage: 2 GB × $0.03 = $0.06
```

**Baseline Total: ~$967.60/month** (without query load)

---

### 3.2 Variable Costs by Query Volume

#### Scenario A: 1,000 Queries/Month (Light Use)

| Service | Usage | Cost |
|---------|-------|------|
| **Lambda (Query)** | 1,000 × 3s × 1GB = 3,000 GB-s | $0.05 |
| **API Gateway** | 1,000 requests | $0.0035 |
| **Athena** | 1,000 queries × 10 MB scanned = 10 GB | $0.05 |
| **CloudFront** | 1,000 requests + 10 MB data | $0.01 |
| **S3 GET (Athena)** | 5,000 requests | $0.002 |
| **TOTAL VARIABLE** | | **$0.12** |
| **TOTAL WITH BASELINE** | | **$967.72/month** |

#### Scenario B: 10,000 Queries/Month (Medium Use)

| Service | Usage | Cost |
|---------|-------|------|
| **Lambda (Query)** | 10,000 × 3s × 1GB = 30,000 GB-s | $0.50 |
| **API Gateway** | 10,000 requests | $0.035 |
| **Athena** | 10,000 queries × 10 MB = 100 GB | $0.50 |
| **CloudFront** | 10,000 requests + 100 MB | $0.085 |
| **S3 GET (Athena)** | 50,000 requests | $0.02 |
| **TOTAL VARIABLE** | | **$1.14** |
| **TOTAL WITH BASELINE** | | **$968.74/month** |

#### Scenario C: 100,000 Queries/Month (High Use)

| Service | Usage | Cost |
|---------|-------|------|
| **Lambda (Query)** | 100,000 × 3s × 1GB = 300,000 GB-s | $5.00 |
| **API Gateway** | 100,000 requests | $0.35 |
| **Athena** | 100,000 queries × 10 MB = 1 TB | $5.00 |
| **CloudFront** | 100,000 requests + 1 GB | $0.85 |
| **S3 GET (Athena)** | 500,000 requests | $0.20 |
| **TOTAL VARIABLE** | | **$11.40** |
| **TOTAL WITH BASELINE** | | **$979.00/month** |

#### Scenario D: 1,000,000 Queries/Month (Very High Use)

| Service | Usage | Cost |
|---------|-------|------|
| **Lambda (Query)** | 1M × 3s × 1GB = 3M GB-s | $50.00 |
| **API Gateway** | 1M requests | $3.50 |
| **Athena** | 1M queries × 10 MB = 10 TB | $50.00 |
| **CloudFront** | 1M requests + 10 GB | $8.50 |
| **S3 GET (Athena)** | 5M requests | $2.00 |
| **TOTAL VARIABLE** | | **$114.00** |
| **TOTAL WITH BASELINE** | | **$1,081.60/month** |

---

### 3.3 Annual Projections

| Query Volume | Monthly Cost | Annual Cost | Notes |
|--------------|--------------|-------------|-------|
| **1K/month** | $967.72 | $11,612.64 | Minimal query load |
| **10K/month** | $968.74 | $11,624.88 | Light production use |
| **100K/month** | $979.00 | $11,748.00 | Medium production use |
| **1M/month** | $1,081.60 | $12,979.20 | High production use |

**Key Insight:** Query volume has minimal impact on total cost due to low variable costs. **Baseline ingestion/ETL operations dominate** (~90% of costs).

---

## 4. Cost Optimization Opportunities

### 4.1 Immediate Optimizations

#### 1. Reduce Glue ETL Frequency
**Current:** 15-minute intervals for Bronze→Silver  
**Recommended:** 30-minute or hourly intervals  
**Savings:** 50-75% reduction = **$350-$550/month**

```yaml
Rationale:
- NOAA data doesn't change that frequently
- Bronze data available for real-time queries
- Gold layer aggregations can be delayed
```

#### 2. Use Glue Flex Execution
**Current:** Standard Glue jobs  
**Recommended:** Glue Flex for non-time-sensitive jobs  
**Savings:** 34% discount = **$244/month**

#### 3. Optimize Crawler Schedule
**Current:** Every 30 minutes  
**Recommended:** Hourly or on-demand after ETL  
**Savings:** 50% reduction = **$110/month**

#### 4. S3 Lifecycle Policies (Already Configured)
**Current:** Bronze 90d, Silver 365d, Gold 730d  
**Status:** ✅ Already optimized  
**Impact:** Prevents storage from growing indefinitely

#### 5. Reserved Capacity (ElastiCache)
**Current:** On-demand pricing  
**Recommended:** 1-year reserved instance  
**Savings:** 30-40% = **$3.72-$4.96/month** (small but adds up)

#### 6. CloudWatch Log Retention
**Current:** 7 days (default)  
**Recommended:** 3 days for verbose logs, 30 days for errors  
**Savings:** ~30% = **$0.30/month**

**Total Potential Monthly Savings: $708-$867/month**  
**Optimized Monthly Cost: ~$100-$260/month** (depending on query volume)

### 4.2 Advanced Optimizations

#### 7. Athena Query Result Caching
- Cache common queries in Redis
- Reduce Athena scans by 60-80%
- Savings scale with query volume

#### 8. Partition Pruning
- Ensure all queries use partition filters (date, pond)
- Reduces data scanned per query
- Can reduce Athena costs by 90%

#### 9. Compress Parquet Files
- Enable Snappy compression (if not already)
- Reduces storage and scan costs
- 3-5x compression ratio

#### 10. Lambda SnapStart
- Enable for Java-based Lambdas (if any)
- Reduces cold start times
- Minimal cost impact

---

## 5. Resource Requirements by Environment

### 5.1 Development Environment

```yaml
Lambda:
  Ingestion: 6 functions × 512 MB
  Query: 3 functions × 1024 MB
  Concurrency: 5 (reserved)

Glue:
  ETL Jobs: 5 jobs × 2 DPU
  Crawlers: 6 crawlers
  Schedule: Hourly (not 15 min)

S3:
  Storage: 5-10 GB (with lifecycle)
  Retention: Bronze 30d, Silver 90d, Gold 365d

ElastiCache:
  Node: cache.t3.micro (0.5 GB)

Estimated Monthly: $100-$150
```

### 5.2 Staging/QA Environment

```yaml
Lambda:
  Ingestion: 6 functions × 512 MB
  Query: 3 functions × 1024 MB
  Concurrency: 10

Glue:
  ETL Jobs: 5 jobs × 2 DPU
  Crawlers: 6 crawlers
  Schedule: Every 30 min

S3:
  Storage: 10-20 GB
  Retention: Bronze 60d, Silver 180d, Gold 730d

ElastiCache:
  Node: cache.t3.small (1.5 GB)

Estimated Monthly: $300-$450
```

### 5.3 Production Environment

```yaml
Lambda:
  Ingestion: 6 functions × 1024 MB (increased)
  Query: 3 functions × 2048 MB (increased)
  Concurrency: 50-100 (reserved)

Glue:
  ETL Jobs: 10 jobs × 4 DPU (increased parallelism)
  Crawlers: 6 crawlers
  Schedule: Every 15-30 min

S3:
  Storage: 50-100 GB (year 1)
  Retention: Bronze 90d, Silver 365d, Gold 730d
  Intelligent-Tiering: Enabled

ElastiCache:
  Node: cache.r6g.large (13 GB) or larger
  Multi-AZ: Enabled

High Availability:
  Multi-region: Optional
  Backup: Enabled
  Monitoring: Enhanced

Estimated Monthly: $1,200-$1,800
```

---

## 6. Scaling Projections

### 6.1 Storage Growth Over Time

```
Month 1:   1 GB    ($0.02/month)
Month 3:   3 GB    ($0.07/month)
Month 6:   6 GB    ($0.14/month)
Year 1:    12 GB   ($0.28/month)
Year 2:    20 GB   ($0.46/month) [with lifecycle policies]
Year 3:    25 GB   ($0.58/month) [reaches steady state]

Without lifecycle policies:
Year 1:    12 GB   ($0.28/month)
Year 2:    36 GB   ($0.83/month)
Year 3:    72 GB   ($1.66/month)
```

### 6.2 Compute Scaling

**Current State:**
- 937 Lambda invocations/day
- 54 Glue DPU-hours/day

**With Additional Data Sources (2x endpoints):**
- 1,874 Lambda invocations/day
- 108 Glue DPU-hours/day
- Cost impact: +100% = **$967 → $1,934/month**

**With Higher Frequency (5 min for all ponds):**
- 1,728 Lambda invocations/day
- 96 Glue DPU-hours/day
- Cost impact: +75% = **$967 → $1,693/month**

### 6.3 Query Scaling Limits

**API Gateway Limits:**
- Default: 10,000 req/sec burst, 5,000 req/sec steady
- Can handle: **13M queries/month** without throttling

**Lambda Concurrency:**
- Account limit: 1,000 concurrent executions
- Reserved: 50-100 for this application
- Can handle: **1M queries/day** with proper configuration

**Athena:**
- Query queue: 20-25 concurrent queries (standard)
- Can be increased to 100+
- Handles: **Millions of queries/day**

**Bottlenecks:**
- ElastiCache Redis: Will need scaling beyond 10K QPS
- Glue crawlers: May need more frequent runs with high query loads

---

## 7. NOAA AWS Account Migration Considerations

### 7.1 Account-Specific Changes Required

#### IAM Roles & Policies
```yaml
Update Required:
- Lambda execution roles
- Glue service roles
- EventBridge invoke roles
- Step Functions roles
- Cross-service permissions

Action: Replace account ID 899626030376 with NOAA account ID
```

#### S3 Bucket Names
```yaml
Current Pattern: noaa-federated-lake-{AccountId}-{Environment}
NOAA Pattern: noaa-federated-lake-{NOAAAccountId}-{Environment}

Buckets to Create:
- Data lake bucket
- Athena results bucket
- Lambda deployment bucket
```

#### VPC Configuration
```yaml
Determine:
- Use existing NOAA VPC or create new
- Subnet allocation
- Security group rules
- VPC endpoints (S3, Glue, Bedrock)
- NAT Gateway requirements
```

#### API Gateway Custom Domain (Optional)
```yaml
Consider:
- Custom domain: api.noaa.gov/data-lake
- SSL certificate via ACM
- Route53 DNS configuration
```

### 7.2 Migration Checklist

#### Pre-Migration
- [ ] Obtain NOAA AWS account ID
- [ ] Verify NOAA account service quotas (Lambda, Glue, S3)
- [ ] Plan VPC/networking architecture
- [ ] Identify existing NOAA security requirements
- [ ] Determine environment strategy (dev/staging/prod)
- [ ] Review compliance requirements (FedRAMP, etc.)

#### Infrastructure Migration
- [ ] Deploy CloudFormation stacks in NOAA account
- [ ] Create S3 buckets with proper naming
- [ ] Configure VPC, subnets, security groups
- [ ] Deploy ElastiCache Redis cluster
- [ ] Set up IAM roles and policies
- [ ] Deploy Lambda functions
- [ ] Create Glue jobs and crawlers
- [ ] Configure API Gateway
- [ ] Set up CloudFront distribution (if needed)
- [ ] Create EventBridge schedules
- [ ] Deploy Step Functions state machine

#### Data Migration (if needed)
- [ ] Export historical data from current account
- [ ] Transfer to NOAA S3 bucket (S3 Transfer or DataSync)
- [ ] Run crawlers to catalog transferred data
- [ ] Validate data integrity

#### Configuration & Testing
- [ ] Update environment variables
- [ ] Configure NOAA CDO API token
- [ ] Test ingestion pipelines
- [ ] Validate ETL transformations
- [ ] Test query APIs
- [ ] Run comprehensive validation suite
- [ ] Load testing (if production)

#### Monitoring & Operations
- [ ] Set up CloudWatch dashboards
- [ ] Configure SNS alerts
- [ ] Document runbooks
- [ ] Train NOAA team on operations
- [ ] Set up cost monitoring/budgets

### 7.3 Recommended Deployment Strategy

```
Phase 1: Development Environment (Week 1)
├── Deploy infrastructure
├── Validate ingestion
├── Test queries
└── Document any issues

Phase 2: Staging Environment (Week 2)
├── Deploy with production-like config
├── Load testing
├── Security review
└── Performance tuning

Phase 3: Production Environment (Week 3-4)
├── Deploy production infrastructure
├── Gradual rollout (low-frequency ingestion first)
├── Monitor for 7 days
├── Increase ingestion frequency gradually
└── Full production cutover

Phase 4: Optimization (Ongoing)
├── Monitor costs daily
├── Tune ETL schedules based on usage
├── Implement caching strategies
└── Continuous improvement
```

---

## 8. Cost Monitoring & Budgets

### 8.1 Recommended AWS Budgets

#### Development Environment
```yaml
Monthly Budget: $200
Alerts:
  - 50% threshold: $100 (email notification)
  - 80% threshold: $160 (email + SNS)
  - 100% threshold: $200 (email + SNS + escalation)
```

#### Production Environment
```yaml
Monthly Budget: $2,000
Alerts:
  - 50% threshold: $1,000 (email)
  - 75% threshold: $1,500 (email + SNS)
  - 90% threshold: $1,800 (email + SNS + review)
  - 100% threshold: $2,000 (email + SNS + escalation)
```

### 8.2 Cost Allocation Tags

Recommended tagging strategy:

```yaml
Required Tags:
  Environment: dev|staging|prod
  Project: NOAA-Federated-Lake
  CostCenter: [NOAA Department Code]
  Owner: [Team/Individual]
  DataPond: atmospheric|oceanic|buoy|climate|terrestrial|spatial
  
Optional Tags:
  Application: data-ingestion|etl|query-api
  Criticality: high|medium|low
  Compliance: yes|no
```

### 8.3 Cost Anomaly Detection

Enable AWS Cost Anomaly Detection:
```yaml
Monitor:
  - Glue ETL job costs (>$50 increase)
  - Lambda invocation spikes (>2x normal)
  - S3 storage growth (>50% month-over-month)
  - Athena query costs (>$20/day unusual)
  
Alert Channels:
  - Email
  - SNS topic: noaa-cost-alerts
  - Slack integration (optional)
```

### 8.4 Daily Cost Monitoring Queries

**Cost Explorer Queries:**

1. **Cost by Service (Daily)**
   - Group by: Service
   - Time: Last 7 days
   - Track: Lambda, Glue, S3, Athena trends

2. **Cost by Data Pond**
   - Group by: Tag (DataPond)
   - Identify expensive ponds
   - Optimize high-cost areas

3. **Cost by Environment**
   - Compare dev vs staging vs prod
   - Ensure dev isn't over-provisioned

---

## 9. Performance & Capacity Planning

### 9.1 Current Performance Metrics

| Metric | Current | Target | Bottleneck |
|--------|---------|--------|------------|
| **Ingestion Latency** | 5-10 min | <5 min | NOAA API response time |
| **Query Response Time** | 1-2 sec | <1 sec | Athena scan time |
| **ETL Processing Time** | 3-8 min | <5 min | Glue startup time |
| **Data Freshness** | 5 min | 1 min | Ingestion frequency |
| **API Availability** | 99.5% | 99.9% | Lambda cold starts |

### 9.2 Capacity Limits

#### AWS Service Quotas to Monitor

| Service | Quota | Current Usage | Headroom |
|---------|-------|---------------|----------|
| **Lambda Concurrent Executions** | 1,000 | ~50 peak | 95% available |
| **API Gateway Requests/sec** | 10,000 | ~10 | 99.9% available |
| **S3 Requests/sec** | 5,500 | ~100 | 98% available |
| **Glue Concurrent Jobs** | 50 | 10 | 80% available |
| **Athena Concurrent Queries** | 25 | 5 | 80% available |

#### Recommended Quota Increases (Production)

```yaml
Request Increases:
  - Lambda Concurrent Executions: 1,000 → 2,000
  - Athena Concurrent Queries: 25 → 100
  - Glue Concurrent Jobs: 50 → 100
  
Rationale: Handle traffic spikes and batch processing
Timeline: Request 2-3 weeks before production launch
```

### 9.3 Horizontal Scaling Strategy

**Lambda Auto-Scaling:**
- Already built-in (up to concurrency limit)
- Set reserved concurrency per function
- Monitor throttles in CloudWatch

**Glue Job Scaling:**
- Increase DPU per job (2 → 4 → 10)
- Add more parallel jobs
- Use Glue Auto Scaling (for Spark jobs)

**ElastiCache Scaling:**
- Vertical: Upgrade node type (t3.micro → t3.small → r6g.large)
- Horizontal: Add read replicas (Multi-AZ)

**S3:**
- No scaling needed (auto-scales infinitely)
- Use S3 Transfer Acceleration for high-throughput ingestion

---

## 10. Security & Compliance Costs

### 10.1 Additional Security Services (Optional)

| Service | Purpose | Monthly Cost |
|---------|---------|--------------|
| **AWS WAF** | API Gateway protection | $5 + $1/rule |
| **GuardDuty** | Threat detection | $4.62/month (minimal logs) |
| **CloudTrail** | Audit logging | $2.00 (first trail free) |
| **KMS** | Data encryption at rest | $1/key + $0.03/10k requests |
| **Secrets Manager** | API token storage | $0.40/secret + $0.05/10k API calls |
| **Config** | Compliance monitoring | $0.003/config item/region |

**Recommended for Production:** $20-50/month additional

### 10.2 Compliance Considerations

**If FedRAMP Compliance Required:**
- Use GovCloud regions (+10-20% cost premium)
- Enable AWS Config rules
- Implement KMS encryption for all S3 buckets
- Enable CloudTrail in all regions
- Estimated additional cost: **+15-25%**

**FISMA Compliance:**
- Similar to FedRAMP requirements
- May require additional logging and monitoring
- Estimated additional cost: **+10-15%**

---

## 11. Disaster Recovery & Business Continuity

### 11.1 Backup Strategy

**Current State:**
- S3 versioning: Enabled
- Cross-region replication: Not enabled
- Backup frequency: Continuous (S3 versioning)

**Recommended for Production:**

```yaml
S3 Cross-Region Replication:
  Source: us-east-1
  Destination: us-west-2
  Cost: $0.02/GB transferred + $0.023/GB storage
  Monthly: ~$1-2 for 20 GB
  
Glue Data Catalog Backup:
  Export to S3 daily
  Cost: Negligible (<$0.10/month)
  
Lambda Function Versioning:
  Keep last 5 versions
  Cost: Included in Lambda pricing
```

### 11.2 Recovery Time Objective (RTO) & Recovery Point Objective (RPO)

| Scenario | RTO | RPO | Cost Impact |
|----------|-----|-----|-------------|
| **Single Lambda Failure** | <1 min | 0 | None (auto-retry) |
| **S3 Bucket Corruption** | <10 min | 0 | None (versioning) |
| **Region Failure** | 1-4 hours | 15 min | +20% (multi-region) |
| **Complete Account Loss** | 1-2 days | 1 hour | Rebuild from IaC |

### 11.3 Multi-Region Architecture (Optional)

**Cost for Active-Passive DR:**
```yaml
Additional Resources:
  - S3 replication: +$2/month
  - Cross-region data transfer: +$5-10/month
  - Standby Lambda (warm): +$20/month
  - RDS Aurora Global Database (if added): +$200/month
  
Total DR Cost: $27-32/month (without RDS)
Percentage Increase: +3-4%
```

---

## 12. Cost Comparison: Alternatives

### 12.1 Alternative Architecture Costs

#### Option A: EC2-Based (Traditional)

```yaml
Resources:
  - 2× t3.medium EC2 (ingestion): $60/month
  - 1× t3.large EC2 (ETL): $60/month
  - 100 GB EBS storage: $10/month
  - Application Load Balancer: $22/month
  - RDS PostgreSQL (db.t3.medium): $83/month
  
Total: ~$235/month (baseline)
Scaling: Manual, slower
Maintenance: High (patching, updates)
```

**Verdict:** Lower baseline cost but higher operational overhead and poor elasticity.

#### Option B: Fully Managed (AWS Data Pipeline + EMR)

```yaml
Resources:
  - Data Pipeline: $1/pipeline/month × 6 = $6
  - EMR cluster (on-demand): $500-800/month
  - S3: Same as current
  - Athena: Same as current
  
Total: ~$600-900/month
Scaling: Better than EC2
Maintenance: Lower than EC2
```

**Verdict:** Higher cost than serverless, less flexible.

#### Option C: Current Serverless Architecture (WINNER)

```yaml
Resources: As detailed above
Total: ~$260/month (optimized)
Scaling: Automatic, instant
Maintenance: Minimal
Elasticity: Perfect for variable workloads
```

**Verdict:** Best cost-to-performance ratio for variable workloads.

---

## 13. Summary & Recommendations

### 13.1 Cost Summary Table

| Cost Category | Current (Dev) | Optimized | Production |
|---------------|---------------|-----------|------------|
| **Compute (Lambda)** | $15.83 | $15.83 | $50 |
| **Compute (Glue ETL)** | $718.08 | $370 | $1,200 |
| **Compute (Crawlers)** | $220 | $110 | $200 |
| **Storage (S3)** | $0.23 | $0.23 | $2 |
| **Database (ElastiCache)** | $12.41 | $8.70 | $300 |
| **Networking** | $1 | $1 | $50 |
| **Monitoring** | $1.06 | $1.06 | $20 |
| **Query Costs (10K/month)** | $1.14 | $1.14 | $10 |
| **Security (optional)** | $0 | $0 | $50 |
| **DR (optional)** | $0 | $0 | $30 |
| **TOTAL** | **$969.75** | **$507.96** | **$1,912** |

### 13.2 Key Findings

1. **Baseline costs dominate** (~90%): Scheduled ingestion and ETL operations
2. **Query volume has minimal impact**: Even 1M queries/month only adds $114
3. **Biggest cost driver**: Glue ETL jobs running every 15 minutes
4. **Optimization potential**: 48% cost reduction possible ($970 → $508)
5. **Production scaling**: ~2-3x dev costs with proper optimization

### 13.3 Recommended Actions for NOAA

#### Immediate (Pre-Migration)
1. ✅ Review and approve architecture
2. ✅ Determine query volume projections
3. ✅ Decide on optimization level (aggressive vs. conservative)
4. ✅ Allocate budget: **$500-600/month per environment**
5. ✅ Identify NOAA AWS account and security requirements

#### Short-Term (Migration Phase)
1. Deploy with conservative settings (15-min ETL)
2. Monitor actual usage for 2-4 weeks
3. Implement optimizations gradually
4. Set up cost monitoring and alerts
5. Document operational procedures

#### Long-Term (Post-Migration)
1. Optimize ETL schedules based on real usage patterns
2. Implement advanced caching strategies
3. Consider reserved capacity for stable workloads
4. Evaluate multi-region DR needs
5. Continuous cost optimization

### 13.4 Budget Recommendations

**Conservative Budget (Safety Buffer):**
```yaml
Development: $600/month ($7,200/year)
Staging: $800/month ($9,600/year)
Production: $2,500/month ($30,000/year)

Total Annual: $47,400
```

**Optimized Budget (Post-Tuning):**
```yaml
Development: $300/month ($3,600/year)
Staging: $500/month ($6,000/year)
Production: $1,500/month ($18,000/year)

Total Annual: $27,600
Savings: $19,800/year (42%)
```

### 13.5 Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Cost Overrun** | Medium | High | Implement budgets & alerts |
| **Performance Issues** | Low | Medium | Load testing before production |
| **Data Loss** | Very Low | High | S3 versioning + replication |
| **Security Breach** | Low | High | WAF, GuardDuty, least privilege |
| **NOAA API Rate Limits** | Medium | Medium | Implement backoff & caching |
| **Service Quotas** | Low | Medium | Request increases proactively |

---

## 14. Appendix A: Detailed Cost Calculations

### Lambda Cost Breakdown

```
Pricing Model:
- Requests: $0.20 per 1M requests
- Compute: $0.0000166667 per GB-second
- Free Tier: 1M requests + 400,000 GB-seconds/month

Ingestion Lambda (512 MB, 120s avg, 937 runs/day):
  Monthly Requests: 28,110
  Request Cost: (28,110 - 1,000,000 free tier) = $0
  GB-seconds: 28,110 × 120 × 0.5 = 1,686,600
  Compute Cost: (1,686,600 - 400,000 free) × $0.0000166667 = $21.44

Query Lambda (1024 MB, 3s avg, 10,000 runs/month):
  Monthly Requests: 10,000
  Request Cost: $0.002
  GB-seconds: 10,000 × 3 × 1 = 30,000
  Compute Cost: 30,000 × $0.0000166667 = $0.50
  Total: $0.502
```

### Glue Cost Breakdown

```
Pricing:
- ETL DPU-Hour: $0.44
- Crawler DPU-Hour: $0.44
- Data Catalog: $1/100,000 objects (first 1M free)

Current Usage:
  ETL Jobs: 1,632 DPU-hours/month × $0.44 = $718.08
  Crawlers: 500 DPU-hours/month × $0.44 = $220
  Data Catalog: Free (under 1M objects)
  
Optimized (30-min intervals):
  ETL Jobs: 816 DPU-hours/month × $0.44 = $359.04
  Crawlers: 250 DPU-hours/month × $0.44 = $110
  Savings: $469.04/month (50%)
```

### S3 Cost Breakdown

```
Storage (Standard Class):
- First 50 TB: $0.023/GB/month
- Next 450 TB: $0.022/GB/month

Requests:
- PUT/POST: $0.005 per 1,000 requests
- GET: $0.0004 per 1,000 requests
- DELETE: Free

Current Monthly:
  Storage: 1 GB × $0.023 = $0.023
  PUT: 30,000 × $0.005/1000 = $0.15
  GET: 150,000 × $0.0004/1000 = $0.06
  Total: $0.233

Year 1 (with lifecycle):
  Storage: 12 GB × $0.023 = $0.276
  Requests: Same = $0.21
  Total: $0.486/month
```

### Athena Cost Breakdown

```
Pricing: $5 per TB scanned

Query Patterns:
  Small query (10 MB): $0.00005
  Medium query (100 MB): $0.0005
  Large query (1 GB): $0.005
  
Monthly Cost by Volume:
  1K queries × 10 MB: 10 GB × $5/TB = $0.05
  10K queries × 10 MB: 100 GB × $5/TB = $0.50
  100K queries × 10 MB: 1 TB × $5/TB = $5.00
  1M queries × 10 MB: 10 TB × $5/TB = $50.00

Optimization via Partitioning:
  Without partitions: Scan 1 GB per query
  With partitions: Scan 10 MB per query
  Savings: 99% reduction in data scanned
```

---

## 15. Appendix B: CloudFormation Resource Map

### Main Stack Resources

```yaml
noaa-complete-stack.yaml:
  S3 Buckets: 2
  Glue Databases: 3
  Glue Tables: 20+
  Glue Jobs: 5
  IAM Roles: 4
  Lambda Functions: 2 (query handlers)
  API Gateway: 1
  ElastiCache: 1
  VPC Resources: 1 VPC, 2 subnets, 2 SGs
  Step Functions: 1
  EventBridge Rules: 1
  SNS Topics: 1
```

### Ingestion Stack (Separate Deployment)

```yaml
Individual Lambda Deployments:
  - lambda-ingest-atmospheric
  - lambda-ingest-oceanic
  - lambda-ingest-buoy
  - lambda-ingest-climate
  - lambda-ingest-terrestrial
  - lambda-ingest-spatial
  
Each with:
  - Lambda Function
  - EventBridge Schedule
  - IAM Execution Role
  - CloudWatch Log Group
```

### ETL Stack

```yaml
glue-etl-stack.yaml:
  Glue Jobs: 10+
  Glue Crawlers: 6
  EventBridge Rules: 10+
  IAM Roles: 1
```

**Total Resources Deployed: 80-100 AWS resources**

---

## 16. Appendix C: Quick Reference

### Cost by Service (Monthly, Optimized Production)

| Service | Cost | % of Total |
|---------|------|------------|
| Glue ETL | $600 | 40% |
| ElastiCache | $300 | 20% |
| Glue Crawlers | $200 | 13% |
| Lambda | $100 | 7% |
| Security | $50 | 3% |
| Networking | $50 | 3% |
| Athena | $50 | 3% |
| Monitoring | $20 | 1% |
| S3 Storage | $10 | 1% |
| Other | $120 | 9% |
| **TOTAL** | **$1,500** | **100%** |

### Key Metrics Dashboard

```yaml
Track Daily:
  - Total AWS Cost (yesterday)
  - Lambda invocations (by function)
  - Glue job runs (success/failure)
  - S3 storage size (by layer)
  - API Gateway requests
  - Athena queries & data scanned
  
Track Weekly:
  - Cost trends by service
  - Storage growth rate
  - Query performance metrics
  - Error rates & retries
  
Track Monthly:
  - Budget vs actual
  - Cost optimization opportunities
  - Capacity planning needs
  - Service quota utilization
```

### Contact & Support

```yaml
AWS Support:
  - Basic: Included (for account/billing)
  - Developer: $29/month (business hours)
  - Business: $100/month minimum (24/7)
  - Recommended: Business tier for production
  
Documentation:
  - Architecture: README.md
  - Deployment: DEPLOYMENT_COMPLETE.md
  - Status: SYSTEM_STATUS.md
  - This Document: AWS_COST_ANALYSIS.md
```

---

## Document Change Log

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2024 | Initial comprehensive cost analysis | System |

---

**END OF DOCUMENT**
