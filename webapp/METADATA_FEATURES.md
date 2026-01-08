# NOAA Data Lake Metadata Features

## Overview

The NOAA Federated Data Lake chatbot now includes **dynamic, real-time metadata** about all data ponds. This feature provides fresh information about data freshness, file counts, sizes, and ingestion statistics collected directly from S3 whenever requested.

## Features

### 1. **Real-Time Metadata Collection**
- Metadata is collected **on-demand** from S3, ensuring fresh data every time
- No static files - always shows current state of the data lake
- Fast response times (typically under 3 seconds)

### 2. **Comprehensive Metrics**

For each data pond, you get:

#### Storage Metrics
- **Total Files**: Number of files across all layers
- **Total Size**: Storage used (in MB and GB)
- **Layer Breakdown**: Bronze, Silver, and Gold layer statistics

#### Freshness Indicators
- **Latest Ingestion**: Timestamp of most recent data ingestion
- **Freshness Minutes**: How many minutes ago data was last updated
- **Freshness Status**: 
  - 🟢 **Excellent** (< 30 minutes)
  - 🟢 **Good** (< 2 hours)
  - 🟡 **Moderate** (< 6 hours)
  - 🔴 **Stale** (> 6 hours)

#### Pond Status
- **Active**: Pond is receiving data regularly
- **Empty**: No data currently in pond
- **Checking**: Metadata collection in progress

## How to Use

### Method 1: Data Lake Metrics Button

1. Open the chatbot at https://d244ik6grpfthq.cloudfront.net/
2. Look in the left sidebar under **Quick Actions**
3. Click **"Data Lake Metrics"** button
4. View comprehensive metadata for all 6 data ponds

### Method 2: Click on Endpoint Names

1. In the left sidebar, expand **"Endpoints & Services"**
2. Click on any **pond name** (the underlined text)
3. View detailed metadata for that specific pond

### Method 3: Ask the Chatbot

You can ask questions like:
- "Show me data lake metrics"
- "How fresh is the atmospheric data?"
- "What's the status of all ponds?"
- "Show metadata for oceanic pond"

## API Endpoint

### Lambda Function: `noaa-ai-query-dev`

#### Request Format

```json
{
  "action": "get_metadata",
  "pond": "atmospheric"  // Optional - omit to get all ponds
}
```

#### Response Format

```json
{
  "success": true,
  "action": "metadata",
  "data": {
    "collection_timestamp": "2025-12-09T19:03:27.976243+00:00",
    "bucket": "noaa-federated-lake-899626030376-dev",
    "ponds": {
      "atmospheric": {
        "pond_name": "atmospheric",
        "status": "active",
        "total_files": 51301,
        "total_size_mb": 44460.15,
        "total_size_gb": 43.42,
        "latest_ingestion": "2025-12-09T18:59:59+00:00",
        "freshness_minutes": 3,
        "freshness_status": "excellent",
        "layers": {
          "bronze": {
            "file_count": 17101,
            "size_mb": 26510.49,
            "latest_file": "2025-12-09T18:59:59+00:00"
          },
          "silver": {
            "file_count": 17100,
            "size_mb": 10828.56,
            "latest_file": "2025-12-09T18:59:59+00:00"
          },
          "gold": {
            "file_count": 17100,
            "size_mb": 7121.10,
            "latest_file": "2025-12-09T18:59:59+00:00"
          }
        }
      }
    },
    "summary": {
      "total_ponds": 6,
      "active_ponds": 6,
      "total_files": 217574,
      "total_size_mb": 74474.46,
      "total_size_gb": 72.73
    }
  }
}
```

## Data Ponds Monitored

1. **Atmospheric** - Weather forecasts, alerts, and observations
2. **Oceanic** - Tides, currents, and water levels
3. **Buoy** - Real-time marine buoy data
4. **Climate** - Historical climate data
5. **Spatial** - Geographic and spatial data
6. **Terrestrial** - Land-based environmental data

## Architecture

```
User Request → Chatbot UI → Lambda (noaa-ai-query-dev) 
                                ↓
                            S3 List API
                                ↓
                    Analyze all layers (bronze/silver/gold)
                                ↓
                    Calculate metrics & freshness
                                ↓
                        Return JSON response
                                ↓
                    Display in chatbot with formatting
```

## Performance

- **Metadata Collection**: 2-4 seconds (checks up to 1000 files per layer)
- **Response Size**: ~10-20 KB (compressed JSON)
- **Update Frequency**: On-demand (fetched fresh each time)

## Benefits

### For Developers
- Monitor data pipeline health in real-time
- Identify stale data quickly
- Understand storage usage per pond
- Debug ingestion issues

### For Users
- Know how fresh the data is before making decisions
- Understand what data is available
- See the scale of the data lake
- Verify data is being updated regularly

### For Operations
- Real-time monitoring without additional tools
- No need for separate monitoring dashboards
- Instant visibility into all ponds
- Quick health checks

## Example Use Cases

### 1. Pre-Query Data Check
Before running an analysis, check if data is fresh:
```
User: "Show me atmospheric pond metadata"
Bot: Shows that data was updated 5 minutes ago ✓
User: "Great! Now show me weather in Seattle"
```

### 2. Troubleshooting
Identify which pond has stale data:
```
User: "Data Lake Metrics"
Bot: Shows spatial pond is 20 hours stale ⚠️
Action: Investigate spatial ingestion Lambda
```

### 3. Capacity Planning
Understand storage growth:
```
User: "Data Lake Metrics"
Bot: Shows atmospheric pond is 43 GB and growing
Action: Review retention policies
```

## Technical Details

### Lambda Function Updates
- Added `collect_pond_metadata_dynamic()` function
- S3 client initialization with proper IAM permissions
- Pagination support for large S3 prefixes
- Timezone-aware timestamp handling

### Frontend Updates
- `loadPondMetadata()` - Fetches fresh metadata via API
- `displayPondMetadata()` - Displays single pond metrics
- `displayAllPondsMetadata()` - Displays overview of all ponds
- Click handlers on endpoint names for metadata view

### IAM Permissions Required
Lambda function needs:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:ListBucket",
    "s3:GetObject"
  ],
  "Resource": [
    "arn:aws:s3:::noaa-federated-lake-899626030376-dev",
    "arn:aws:s3:::noaa-federated-lake-899626030376-dev/*"
  ]
}
```

## Future Enhancements

Potential additions:
- [ ] Endpoint-level metrics (individual API statistics)
- [ ] Historical freshness trends (charts)
- [ ] Automated alerts when data becomes stale
- [ ] Ingestion rate calculations (files per hour)
- [ ] Cost estimates based on storage
- [ ] Data quality metrics integration
- [ ] Export metadata to CSV/JSON

## Related Files

- `lambda-enhanced-handler/lambda_function.py` - Lambda handler with metadata logic
- `webapp/app.js` - Frontend JavaScript with metadata functions
- `webapp/index.html` - UI with metadata button
- `scripts/collect_pond_metadata.py` - Standalone metadata collection script

## Support

For issues or questions:
1. Check Lambda logs in CloudWatch: `/aws/lambda/noaa-ai-query-dev`
2. Verify S3 bucket access: `noaa-federated-lake-899626030376-dev`
3. Test API endpoint directly via Postman/curl
4. Review browser console for frontend errors

## Version History

- **v1.0** (2025-12-09) - Initial release
  - Dynamic metadata collection from S3
  - Frontend integration
  - Quick action button
  - Click-to-view on endpoint names

---

**Last Updated**: December 9, 2025
**Status**: ✅ Deployed to Production
**URL**: https://d244ik6grpfthq.cloudfront.net/