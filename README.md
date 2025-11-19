# NOAA Federated Data Lake

A comprehensive, production-ready data lake for ingesting, processing, and querying NOAA (National Oceanic and Atmospheric Administration) data across multiple environmental domains.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![AWS](https://img.shields.io/badge/AWS-Lambda%20%7C%20S3%20%7C%20Athena-orange.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)

## 🌊 Overview

The NOAA Federated Data Lake is a unified platform that ingests, processes, and federates environmental data from 25+ NOAA API endpoints across six specialized data "ponds":

- **🌊 Oceanic** - Buoys, tides, currents, and marine conditions
- **🌤️ Atmospheric** - Weather forecasts, alerts, and observations
- **🌡️ Climate** - Historical climate data and normals
- **🛰️ Spatial** - Radar and satellite imagery metadata
- **🏞️ Terrestrial** - River gauges and precipitation
- **⚓ Buoy** - Real-time marine buoy observations

### Key Features

✅ **Medallion Architecture** - Bronze → Silver → Gold data layers  
✅ **25+ NOAA Endpoints** - Comprehensive data coverage  
✅ **Automated Ingestion** - EventBridge-scheduled Lambda functions  
✅ **Federated Queries** - Query across multiple ponds seamlessly  
✅ **Production-Ready** - Full error handling, logging, and monitoring  
✅ **Scalable** - Serverless architecture grows with your needs  
✅ **Cost-Effective** - Pay only for what you use  

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     NOAA API Endpoints (25+)                    │
│  Weather.gov | Tides | Buoys | Climate | Satellite | Rivers    │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Lambda Ingestion Functions (6 ponds)               │
│    EventBridge Scheduled: 15min - 1hr intervals                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Medallion Architecture                       │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│  │  Bronze  │  →   │  Silver  │  →   │   Gold   │             │
│  │   Raw    │      │ Processed│      │Analytics │             │
│  │   JSON   │      │  Parquet │      │  Ready   │             │
│  │ 90 days  │      │ 365 days │      │ 730 days │             │
│  └──────────┘      └──────────┘      └──────────┘             │
│                    S3 Data Lake                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Athena + Federated Queries                   │
│  Query any pond or join multiple ponds for comprehensive data  │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
noaa_storefront/
├── README.md                          # This file
├── cloudformation/                    # CloudFormation templates
│   ├── noaa-complete-stack.yaml      # Main infrastructure template
│   └── noaa-ai-query.yaml            # AI query handler template
├── config/                            # Configuration files
│   ├── ai_query_config.yaml          # AI query configuration
│   └── *.json                         # IAM policies, EventBridge rules
├── docs/                              # Documentation
│   ├── CHATBOT_INTEGRATION_GUIDE.md  # Chatbot integration
│   ├── QUICKSTART_VALIDATION.md      # Quick start guide
│   └── *.md                           # Additional documentation
├── lambda-ingest-*/                   # Lambda ingestion functions (6)
│   ├── *_ingest.py                    # Ingestion script
│   └── requirements.txt               # Dependencies
├── lambda-enhanced-handler/           # Query handler Lambda
├── intelligent-orchestrator-package/  # Query orchestrator
├── lambda-packages/                   # Packaged Lambda functions
├── logs/                              # Log files
├── scripts/                           # Deployment and utility scripts
│   ├── master_deploy.sh              # 🌟 Master orchestrator
│   ├── deploy_to_aws.sh              # AWS deployment
│   ├── package_all_lambdas.sh        # Lambda packaging
│   ├── validate_endpoints_and_queries.py  # Endpoint validation
│   └── *.py                           # Medallion transformation scripts
├── sql/                               # SQL schemas
│   └── create-all-gold-tables.sql    # Athena table definitions
├── tests/                             # Test suites
│   ├── test_all_ponds.py             # Comprehensive pond tests
│   └── *.sh                           # Test scripts
└── webapp/                            # Web interface (optional)
```

## 🚀 Quick Start

### Prerequisites

- **AWS Account** with appropriate permissions
- **AWS CLI** configured (`aws configure`)
- **Python 3.9+** with pip
- **NOAA CDO API Token** (optional, for climate data) - Get from [https://www.ncdc.noaa.gov/cdo-web/token](https://www.ncdc.noaa.gov/cdo-web/token)

### One-Command Deployment

The easiest way to deploy the entire system:

```bash
cd noaa_storefront
chmod +x scripts/master_deploy.sh
./scripts/master_deploy.sh --env dev --full-deploy
```

This single command will:
1. ✅ Validate prerequisites
2. ✅ Package all Lambda functions
3. ✅ Deploy CloudFormation infrastructure
4. ✅ Create Athena databases and tables
5. ✅ Configure EventBridge schedules
6. ✅ Trigger initial data ingestion
7. ✅ Run comprehensive validation tests
8. ✅ Generate deployment report

### Step-by-Step Deployment

If you prefer more control:

#### 1. Package Lambda Functions

```bash
cd scripts
./package_all_lambdas.sh --env dev --upload --clean
```

#### 2. Deploy Infrastructure

```bash
./deploy_to_aws.sh --env dev --noaa-token YOUR_TOKEN
```

#### 3. Validate Deployment

```bash
cd ../tests
python3 test_all_ponds.py --env dev
```

#### 4. Validate Endpoints

```bash
cd ../scripts
python3 validate_endpoints_and_queries.py --env dev --test-queries
```

## 📊 Data Ponds

### 1. 🌊 Oceanic Pond

**Endpoints:** 5+  
**Update Frequency:** Every 15 minutes  
**Data Sources:** NOAA Buoys, Tides and Currents API

**Available Data:**
- Real-time buoy measurements (wave height, water temp, wind)
- Tidal predictions and observations
- Ocean currents
- Water levels at coastal stations

**Sample Query:**
```sql
SELECT station_name, wave_height, sea_surface_temperature, wind_speed
FROM noaa_gold_dev.oceanic_buoys
WHERE date = date_format(current_date, '%Y-%m-%d')
  AND wave_height > 10
ORDER BY wave_height DESC;
```

### 2. 🌤️ Atmospheric Pond

**Endpoints:** 8+  
**Update Frequency:** Every 15 minutes  
**Data Sources:** National Weather Service API

**Available Data:**
- Weather forecasts (7-day, hourly)
- Active weather alerts and warnings
- Current observations from 50+ stations
- Regional weather patterns

**Sample Query:**
```sql
SELECT location_name, state, current_temperature, 
       wind_speed, short_forecast
FROM noaa_gold_dev.atmospheric_forecasts
WHERE state = 'CA'
  AND date = date_format(current_date, '%Y-%m-%d')
ORDER BY current_temperature DESC;
```

### 3. 🌡️ Climate Pond

**Endpoints:** 4+  
**Update Frequency:** Every hour  
**Data Sources:** NOAA Climate Data Online (CDO)

**Available Data:**
- Historical daily climate data
- Temperature extremes
- Precipitation records
- Climate normals

**Sample Query:**
```sql
SELECT station_id, AVG(temperature_max) as avg_high,
       AVG(precipitation) as avg_precip
FROM noaa_gold_dev.climate_daily
WHERE date >= date_format(current_date - interval '30' day, '%Y-%m-%d')
GROUP BY station_id;
```

### 4. 🛰️ Spatial Pond

**Endpoints:** 2+  
**Update Frequency:** Every 30 minutes  
**Data Sources:** NOAA Radar, Satellite Products

**Available Data:**
- Radar station metadata
- Satellite product availability
- Coverage maps

### 5. 🏞️ Terrestrial Pond

**Endpoints:** 2+  
**Update Frequency:** Every 30 minutes  
**Data Sources:** USGS Water Services, NWS

**Available Data:**
- River gauge heights
- Stream flow rates
- Precipitation measurements
- Flood stage data

### 6. ⚓ Buoy Pond

**Endpoints:** 3+  
**Update Frequency:** Every 15 minutes  
**Data Sources:** NDBC (National Data Buoy Center)

**Available Data:**
- Real-time meteorological data
- Marine conditions
- Offshore weather observations

## 🔍 Federated Query Examples

### Cross-Pond Temperature Analysis

Compare air and water temperatures:

```sql
SELECT 
    a.location_name,
    a.state,
    a.current_temperature as air_temp,
    o.water_temperature as water_temp,
    ABS(a.current_temperature - (o.water_temperature * 1.8 + 32)) as temp_diff
FROM noaa_gold_dev.atmospheric_forecasts a
LEFT JOIN noaa_gold_dev.oceanic_tides o
    ON a.state = o.state
    AND a.date = o.date
WHERE a.date = date_format(current_date, '%Y-%m-%d')
ORDER BY temp_diff DESC
LIMIT 10;
```

### Regional Weather Summary

Complete weather picture by state:

```sql
SELECT 
    COALESCE(a.state, c.state) as state,
    COUNT(DISTINCT a.location_name) as forecast_locations,
    AVG(a.current_temperature) as avg_current_temp,
    AVG(c.precipitation) as avg_precipitation,
    MAX(al.total_alerts) as active_alerts
FROM noaa_gold_dev.atmospheric_forecasts a
FULL OUTER JOIN noaa_gold_dev.climate_daily c
    ON a.state = c.state AND a.date = c.date
LEFT JOIN noaa_gold_dev.atmospheric_alerts al
    ON a.date = al.date
WHERE a.date = date_format(current_date, '%Y-%m-%d')
GROUP BY COALESCE(a.state, c.state)
ORDER BY state;
```

### Marine Conditions Overview

Complete marine weather:

```sql
SELECT 
    b.station_name,
    b.latitude,
    b.longitude,
    b.wave_height,
    b.sea_surface_temperature,
    b.wind_speed,
    o.water_level
FROM noaa_gold_dev.oceanic_buoys b
LEFT JOIN noaa_gold_dev.oceanic_tides o
    ON b.station_id = o.station_id
    AND b.date = o.date
WHERE b.date = date_format(current_date, '%Y-%m-%d')
  AND b.wave_height IS NOT NULL
ORDER BY b.wave_height DESC
LIMIT 20;
```

## 🧪 Testing

### Run All Tests

```bash
python3 tests/test_all_ponds.py --env dev
```

### Test Specific Pond

```bash
python3 tests/test_all_ponds.py --env dev --pond oceanic
```

### Validate Endpoints

```bash
python3 scripts/validate_endpoints_and_queries.py --env dev --test-queries
```

### Quick Validation

```bash
./scripts/master_deploy.sh --env dev --validate-only --quick
```

## 📈 Monitoring

### View Lambda Logs

```bash
# Oceanic ingestion
aws logs tail /aws/lambda/NOAAIngestOceanic-dev --follow

# Atmospheric ingestion
aws logs tail /aws/lambda/NOAAIngestAtmospheric-dev --follow
```

### Check S3 Data

```bash
# List recent data
aws s3 ls s3://noaa-federated-lake-ACCOUNT_ID-dev/gold/ --recursive | tail -20

# Check bronze layer
aws s3 ls s3://noaa-federated-lake-ACCOUNT_ID-dev/bronze/oceanic/ --recursive
```

### Query Athena

```bash
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_gold_dev.oceanic_buoys" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-ACCOUNT_ID-dev/"
```

## 🔧 Configuration

### Environment Variables

Lambda functions use these environment variables:

- `ENVIRONMENT` - Deployment environment (dev/staging/prod)
- `DATA_LAKE_BUCKET` - S3 bucket for data storage
- `GOLD_DATABASE` - Athena database name
- `NOAA_CDO_TOKEN` - NOAA Climate Data API token (optional)

### Ingestion Schedules

Modify EventBridge rules to change ingestion frequency:

```bash
aws events put-rule \
  --name NOAAIngestOceanic-dev-schedule \
  --schedule-expression "rate(15 minutes)"
```

### Retention Policies

Data retention is managed via S3 lifecycle rules:
- **Bronze:** 90 days
- **Silver:** 365 days
- **Gold:** 730 days

## 🛠️ Troubleshooting

### Lambda Function Fails

1. Check CloudWatch Logs for error messages
2. Verify IAM permissions
3. Check NOAA API availability
4. Validate S3 bucket permissions

```bash
aws lambda invoke \
  --function-name NOAAIngestOceanic-dev \
  --payload '{"env":"dev"}' \
  response.json
cat response.json
```

### No Data in Athena Tables

1. Verify Lambda functions are running
2. Check S3 for data files
3. Run MSCK REPAIR TABLE to update partitions

```sql
MSCK REPAIR TABLE noaa_gold_dev.oceanic_buoys;
```

### Endpoint Validation Failures

Run diagnostic validation:

```bash
python3 scripts/validate_endpoints_and_queries.py --env dev
```

### High Costs

1. Review ingestion frequency (reduce if needed)
2. Check S3 storage size
3. Optimize Athena queries (use partitions)
4. Review Lambda execution times

## 📝 API Reference

### Lambda Function Handlers

All ingestion functions accept:

```json
{
  "env": "dev",
  "locations": ["new_york", "los_angeles"],  // optional
  "force_refresh": false                      // optional
}
```

### Query Handler

Enhanced query handler accepts natural language:

```json
{
  "query": "What's the weather in California?",
  "ponds": ["atmospheric"],
  "max_results": 10
}
```

## 🤝 Contributing

This is a production system. For modifications:

1. Test in `dev` environment first
2. Run validation suite
3. Update documentation
4. Deploy to `staging` for testing
5. Deploy to `prod` after approval

## 📄 License

MIT License - See LICENSE file for details

## 🆘 Support

### Common Commands

```bash
# Full deployment
./scripts/master_deploy.sh --env dev --full-deploy

# Validation only
./scripts/master_deploy.sh --env dev --validate-only

# Package Lambdas
./scripts/package_all_lambdas.sh --env dev --upload

# Test all ponds
python3 tests/test_all_ponds.py --env dev

# Validate endpoints
python3 scripts/validate_endpoints_and_queries.py --env dev
```

### Resources

- **NOAA API Documentation:** https://www.weather.gov/documentation/services-web-api
- **AWS Lambda:** https://docs.aws.amazon.com/lambda/
- **AWS Athena:** https://docs.aws.amazon.com/athena/
- **NOAA Data Access:** https://www.ncdc.noaa.gov/cdo-web/

## 🎯 Roadmap

- [ ] Add more international data sources
- [ ] Implement ML-based anomaly detection
- [ ] Real-time alerting system
- [ ] Mobile app integration
- [ ] Advanced visualization dashboard
- [ ] Data quality scoring
- [ ] Historical trend analysis

---

**Version:** 1.0.0  
**Last Updated:** November 2024  
**Status:** 🟢 Production Ready

Built with ❤️ for environmental data access