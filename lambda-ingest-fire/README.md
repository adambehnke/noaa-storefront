# NOAA Fire Data Ingestion Lambda

Ingests near real-time wildfire detection data from the NOAA Wildland Fire Data Portal into the **Atmospheric Pond**.

## Overview

This Lambda function fetches fire detection data from NOAA's Next Generation Fire System (NGFS) and stores it in the NOAA Federated Data Lake's atmospheric data pond. Fire data is categorized as atmospheric because wildfire detection is satellite-based atmospheric monitoring related to weather, air quality, and meteorological phenomena.

### Key Features

- ✅ **Near Real-Time** - Ingests data every 15 minutes
- ✅ **Comprehensive Coverage** - East/West CONUS + optional mesoscale regions
- ✅ **Medallion Architecture** - Bronze → Gold layers
- ✅ **Auto-Aggregation** - Summarizes incidents and intensity
- ✅ **Reliable** - Tracks last ingestion time, handles pagination, retries failures
- ✅ **Cost-Effective** - ~$5-10/month operational cost

## Data Source

**API:** https://fire.data.nesdis.noaa.gov/  
**Type:** OGC Features API (RESTful, GeoJSON)  
**Authentication:** None required (public API)  
**Status:** Beta (transitioning to production 2026)

### Collections (Enabled by Default)

| Collection | Coverage | Update Frequency |
|------------|----------|------------------|
| West CONUS | Western United States | 5-15 minutes |
| East CONUS | Eastern United States | 5-15 minutes |

### Optional Collections (Disabled by Default)

| Collection | Coverage | Update Frequency |
|------------|----------|------------------|
| West Mesoscale 1 | Western region | ~1 minute |
| West Mesoscale 2 | Western region | ~1 minute |
| East Mesoscale 1 | Eastern region | ~1 minute |
| East Mesoscale 2 | Eastern region | ~1 minute |

To enable mesoscale collections, edit `lambda_function.py` and set `"enabled": True` for desired collections.

## Data Pond Assignment

**Pond:** Atmospheric  
**Reason:** Fire detection is an atmospheric/meteorological phenomenon

### Data Storage Structure

```
s3://noaa-federated-lake-899626030376-dev/
├── bronze/atmospheric/fire/
│   ├── west_conus/year=2026/month=01/day=13/hour=10/fire_20260113_103045.json
│   └── east_conus/year=2026/month=01/day=13/hour=10/fire_20260113_103045.json
└── gold/atmospheric/fire/
    └── date=2026-01-13/fire_summary_west_conus_20260113_103045.json
```

### Data Format

**Bronze Layer (Raw GeoJSON):**
```json
{
  "type": "FeatureCollection",
  "collection": "ngfs_schema.ngfs_detections_scene_west_conus",
  "numberReturned": 42,
  "features": [{
    "type": "Feature",
    "geometry": {
      "type": "Point",
      "coordinates": [-118.5234, 34.2156]
    },
    "properties": {
      "frp": 45.3,
      "acq_date_time": "2024-11-09T02:15:30",
      "latitude": 34.2156,
      "longitude": -118.5234,
      "pixel_area": 4.5,
      "known_incident_name": "MOUNTAIN FIRE",
      "confidence": "high",
      "satellite": "G17",
      "instrument": "ABI"
    }
  }]
}
```

**Gold Layer (Aggregated Summary):**
```json
{
  "date": "2026-01-13",
  "collection": "west_conus",
  "summary": {
    "total_detections": 42,
    "named_incidents": 3,
    "unnamed_detections": 15,
    "detections_by_intensity": {
      "low": 10,
      "medium": 20,
      "high": 10,
      "extreme": 2
    }
  },
  "incidents": [{
    "incident_name": "MOUNTAIN FIRE",
    "detection_count": 15,
    "max_frp_mw": 125.6,
    "avg_frp_mw": 67.3,
    "center_latitude": 34.2156,
    "center_longitude": -118.5234,
    "first_detection": "2024-11-09T01:30:00",
    "last_detection": "2024-11-09T02:15:30"
  }]
}
```

## Deployment

### Prerequisites

- AWS CLI configured with `noaa-target` profile
- Python 3.12+
- Access to AWS account 899626030376
- S3 bucket exists: `noaa-federated-lake-899626030376-dev`

### Quick Deploy

```bash
cd noaa_storefront/lambda-ingest-fire
chmod +x deploy.sh
./deploy.sh
```

### Custom Deployment

```bash
# Deploy to specific environment
./deploy.sh --env prod --profile noaa-target

# Deploy to dev (default)
./deploy.sh --env dev
```

### What Gets Deployed

1. **Lambda Function:** `noaa-ingest-fire-dev`
   - Runtime: Python 3.12
   - Memory: 512 MB
   - Timeout: 300 seconds (5 minutes)
   - Handler: `lambda_function.lambda_handler`

2. **EventBridge Schedule:** `noaa-ingest-fire-schedule-dev`
   - Trigger: Every 15 minutes
   - Status: Enabled

3. **IAM Role:** `noaa-lambda-execution-role-dev`
   - S3 full access
   - SSM full access
   - CloudWatch logs

4. **SSM Parameters:** (auto-created on first run)
   - `/noaa/dev/atmospheric/fire/last_ingestion/{collection}`
   - Tracks last successful ingestion time per collection

## Testing

### Manual Invocation

```bash
aws lambda invoke \
  --function-name noaa-ingest-fire-dev \
  --profile noaa-target \
  /tmp/fire-test.json

cat /tmp/fire-test.json | jq '.'
```

### Check CloudWatch Logs

```bash
aws logs tail /aws/lambda/noaa-ingest-fire-dev --follow --profile noaa-target
```

### Verify Data in S3

```bash
# Check Bronze layer
aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/fire/ \
  --recursive --profile noaa-target

# Check Gold layer
aws s3 ls s3://noaa-federated-lake-899626030376-dev/gold/atmospheric/fire/ \
  --recursive --profile noaa-target

# View latest Gold summary
aws s3 cp s3://noaa-federated-lake-899626030376-dev/gold/atmospheric/fire/date=$(date +%Y-%m-%d)/ - \
  --recursive --profile noaa-target
```

### Expected Output

```json
{
  "status": "success",
  "timestamp": "2026-01-13T15:30:00Z",
  "collections_processed": {
    "West CONUS": {
      "status": "success",
      "detections": 42,
      "incidents": 3,
      "pages": 1
    },
    "East CONUS": {
      "status": "success",
      "detections": 15,
      "incidents": 1,
      "pages": 1
    }
  },
  "total_detections": 57,
  "total_incidents": 4
}
```

## Configuration

### Enable/Disable Collections

Edit `lambda_function.py`:

```python
COLLECTIONS = [
    {
        "id": "ngfs_schema.ngfs_detections_scene_west_conus",
        "name": "West CONUS",
        "priority": 1,
        "enabled": True,  # ← Change to False to disable
    },
    # ... more collections
]
```

### Environment Variables

Set in Lambda configuration:

- `S3_BUCKET` - Target S3 bucket (default: auto-detected from ENV)
- `ENV` - Environment name (dev/prod)

### Adjust Schedule

To change ingestion frequency:

```bash
aws events put-rule \
  --name noaa-ingest-fire-schedule-dev \
  --schedule-expression "rate(30 minutes)" \
  --profile noaa-target
```

Options:
- `rate(15 minutes)` - Every 15 minutes (default)
- `rate(30 minutes)` - Every 30 minutes
- `rate(1 hour)` - Every hour
- `cron(0 * * * ? *)` - Top of every hour

## Monitoring

### CloudWatch Metrics

Monitor in AWS Console → CloudWatch → Lambda:
- Invocations
- Duration
- Errors
- Throttles

### CloudWatch Logs

```bash
# View recent logs
aws logs tail /aws/lambda/noaa-ingest-fire-dev --since 1h --profile noaa-target

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/noaa-ingest-fire-dev \
  --filter-pattern "ERROR" \
  --profile noaa-target
```

### Key Log Messages

**Successful Ingestion:**
```
Fetch complete: 42 total detections from 1 pages
✓ Saved to Bronze: s3://bucket/bronze/atmospheric/fire/...
✓ Saved to Gold: s3://bucket/gold/atmospheric/fire/...
Fire Data Ingestion Complete
Total detections: 42
```

**No New Data:**
```
✓ No new detections for West CONUS
Fire Data Ingestion Complete
Total detections: 0
```

**Errors:**
```
✗ Error processing West CONUS: Timeout fetching page 1
Status: partial_success
```

## Troubleshooting

### Issue: No data in S3

**Symptoms:** Lambda runs successfully but no files appear in S3

**Solutions:**
1. Check IAM permissions - Lambda needs S3 write access
2. Verify bucket name in environment variables
3. Check CloudWatch logs for permission errors
4. Verify bucket exists: `aws s3 ls s3://noaa-federated-lake-899626030376-dev --profile noaa-target`

### Issue: API timeouts

**Symptoms:** Log shows "Timeout fetching page X"

**Solutions:**
1. Increase Lambda timeout (currently 300 seconds)
2. Reduce number of enabled collections
3. Check NOAA API status: https://fire.data.nesdis.noaa.gov/
4. API is in beta - occasional outages expected

### Issue: Lambda errors

**Symptoms:** Lambda invocation fails with error

**Solutions:**
1. Check CloudWatch logs for stack trace
2. Verify Python dependencies in `requirements.txt`
3. Test locally: `python lambda_function.py`
4. Verify IAM role has necessary permissions

### Issue: High costs

**Symptoms:** AWS bill higher than expected

**Solutions:**
1. Check invocation count - should be ~2,880/month (every 15 min)
2. Disable mesoscale collections if not needed
3. Increase schedule interval to 30 minutes
4. Review CloudWatch logs size and retention

### Issue: Duplicate detections

**Symptoms:** Same fire appears multiple times

**Solutions:**
- This is expected - satellites scan same area multiple times
- Gold layer aggregates by incident name
- Implement deduplication in Silver layer (future enhancement)

## Architecture

```
┌─────────────────────────────────────────┐
│   NOAA Fire Data Portal API             │
│   https://fire.data.nesdis.noaa.gov/    │
└─────────────────────────────────────────┘
                  │
                  │ HTTPS GET (every 15 min)
                  ▼
┌─────────────────────────────────────────┐
│   Lambda: noaa-ingest-fire-dev          │
│   - Fetch GeoJSON from API              │
│   - Track last ingestion time (SSM)     │
│   - Paginate results                    │
│   - Handle errors & retries             │
└─────────────────────────────────────────┘
                  │
                  ├─────────────────────┐
                  ▼                     ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│ Bronze Layer (Raw)       │  │ Gold Layer (Aggregated)  │
│ bronze/atmospheric/fire/ │  │ gold/atmospheric/fire/   │
│ - Raw GeoJSON            │  │ - Incident summaries     │
│ - Partitioned by time    │  │ - Intensity stats        │
│ - Full API response      │  │ - Geographic centers     │
└──────────────────────────┘  └──────────────────────────┘
```

## Cost Analysis

**Monthly Costs (Estimated):**

| Component | Usage | Cost |
|-----------|-------|------|
| Lambda Invocations | 2,880/month @ 30s avg | $5-8 |
| S3 Storage | ~5-10 GB/month | $0.25 |
| SSM Parameters | 6 parameters | $0 |
| CloudWatch Logs | ~1 GB/month | $0.50 |
| **Total** | | **$5-10/month** |

**Cost Optimization:**
- Use 30-minute schedule instead of 15 minutes → saves 50%
- Disable mesoscale collections if not needed
- Set CloudWatch log retention to 7 days

## Integration with Data Lake

### Athena Queries (Future)

```sql
-- Once Glue ETL is implemented
SELECT 
    incident_name,
    COUNT(*) as detections,
    MAX(fire_radiative_power) as max_frp_mw
FROM noaa_silver_dev.fire_detections
WHERE year = 2026 AND month = 1
GROUP BY incident_name
ORDER BY detections DESC;
```

### AI Query Handler

Fire data can be queried via `noaa-ai-query-dev` Lambda:
- "What wildfires are currently active?"
- "Show me fire detections in California today"
- "What's the intensity of the Mountain Fire?"

## Next Steps

1. **Deploy Lambda** - Run `./deploy.sh`
2. **Monitor First Run** - Check CloudWatch logs
3. **Verify Data** - Check S3 Bronze/Gold layers
4. **Create Glue ETL** - Transform Bronze → Silver (optional)
5. **Create Athena Tables** - For SQL queries (optional)
6. **Update AI Handler** - Add fire query support (optional)

## Support

- **API Issues:** https://fire.data.nesdis.noaa.gov/faq
- **AWS Issues:** Check CloudWatch logs
- **Lambda Issues:** Review logs and IAM permissions

## References

- [NOAA Fire Data Portal](https://fire.data.nesdis.noaa.gov/)
- [Fire Portal Tutorials](https://fire.data.nesdis.noaa.gov/tutorials)
- [OGC Features API](https://www.ogc.org/standards/ogcapi-features)
- [NESDIS](https://www.nesdis.noaa.gov/)

---

**Version:** 1.0  
**Last Updated:** January 13, 2026  
**Maintainer:** NOAA Data Lake Team