# NOAA Dashboard - Dynamic Data Architecture

## Overview

This dashboard implementation uses **real-time data from AWS services** instead of hardcoded values. When you click on any element (Bronze layer, Silver layer, Gold layer, ponds, etc.), the dashboard makes API calls to fetch actual metrics from:

- **S3**: Storage metrics, file counts, sizes
- **Athena**: Record counts, query performance, table schemas
- **Glue**: ETL job status, processing times
- **CloudWatch**: Lambda invocations, error rates, execution times
- **Bedrock**: AI model usage and costs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Browser                            │
│  dashboard_comprehensive.html                                │
│  ├── dashboard-modals.css (styling)                         │
│  └── dashboard-dynamic.js (API calls)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTPS Request
                       │ GET /metrics?metric_type=bronze_layer
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Lambda Function (Metrics API)                   │
│  monitoring/lambda/dashboard_metrics.py                      │
│  ├── Queries S3 for storage metrics                         │
│  ├── Queries Athena for record counts                       │
│  ├── Queries Glue for ETL job status                        │
│  ├── Queries CloudWatch for performance                     │
│  └── Returns JSON response                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Boto3 API Calls
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    AWS Services                              │
│  ├── S3: List objects, get file sizes                       │
│  ├── Athena: Execute queries, get results                   │
│  ├── Glue: Get job runs, table metadata                     │
│  ├── CloudWatch: Get metrics (invocations, errors, etc.)    │
│  └── Lambda: List functions, get configs                    │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. **No Hardcoded Data**
Every metric you see is fetched in real-time from AWS services. Numbers like "77,542 files" or "28.5 GB" are actual counts from your S3 bucket.

### 2. **5-Minute Client-Side Cache**
To avoid hitting AWS APIs too frequently, the JavaScript caches responses for 5 minutes. This balances freshness with cost.

### 3. **Loading States**
While fetching data, the dashboard shows a loading spinner with "Loading real-time data from AWS..."

### 4. **Error Handling**
If an API call fails, users see a friendly error message with a reload button.

### 5. **Detailed Drill-Down**
- **Bronze Layer**: Shows actual Lambda functions, API endpoints, and recent S3 samples
- **Silver Layer**: Shows Glue ETL job status, processing times, and before/after transformations
- **Gold Layer**: Shows Athena tables, query performance, compression ratios
- **Ponds**: Shows Lambda configs, storage per layer, record counts, recent data samples
- **AI Metrics**: Shows Bedrock usage, query counts, success rates, costs

## Files

### Core Dashboard Files
```
monitoring/
├── dashboard_comprehensive.html      # Main HTML structure
├── dashboard-modals.css             # Modal styling
├── dashboard-dynamic.js             # API client & drill-down functions
└── lambda/
    └── dashboard_metrics.py         # Lambda function (backend API)
```

### Deployment Files
```
monitoring/
├── deploy_to_s3.sh                  # Deploys dashboard to S3/CloudFront
└── README_DYNAMIC_DASHBOARD.md      # This file
```

## API Endpoints

The Lambda function (`dashboard_metrics.py`) exposes these metric types:

| Metric Type | Query Parameter | Returns |
|-------------|----------------|---------|
| `overview` | `?metric_type=overview` | High-level metrics: total records, active ponds, storage |
| `bronze_layer` | `?metric_type=bronze_layer` | Bronze storage, ingestion stats, Lambda configs, samples |
| `silver_layer` | `?metric_type=silver_layer` | Silver storage, Glue jobs, quality metrics, transformations |
| `gold_layer` | `?metric_type=gold_layer` | Gold storage, Athena tables, query performance |
| `pond_details` | `?metric_type=pond_details&pond_name=atmospheric` | Detailed pond metrics, endpoints, samples, schemas |
| `transformation_details` | `?metric_type=transformation_details&pond_name=atmospheric` | Before/after samples, transformation logic |
| `ai_metrics` | `?metric_type=ai_metrics` | AI query stats, Bedrock usage, costs |

## JavaScript Functions

### Modal Functions
```javascript
showBronzeDetails()              // Fetches Bronze layer metrics
showSilverDetails()              // Fetches Silver layer metrics
showGoldDetails()                // Fetches Gold layer metrics
showPondDetails(pondName)        // Fetches specific pond details
showAtmosphericTransformation()  // Shows atmospheric transformation pipeline
showOceanicTransformation()      // Shows oceanic transformation pipeline
showBuoyTransformation()         // Shows buoy transformation pipeline
showAIMetricsDetails()           // Fetches AI performance metrics
closeModal(modalId)              // Closes a modal
```

### Core API Function
```javascript
async function fetchMetrics(metricType, params = {})
// Makes API call to Lambda function
// Returns: Promise<Object> with metrics data
// Implements 5-minute client-side cache
```

## Deployment

### 1. Deploy Dashboard Files
```bash
cd monitoring
./deploy_to_s3.sh upload
```

This uploads:
- `dashboard_comprehensive.html`
- `dashboard-modals.css`
- `dashboard-dynamic.js`

### 2. Deploy Lambda Function (if not already deployed)

The Lambda function needs to be created with:
- **Function name**: `noaa-dashboard-metrics` (or similar)
- **Runtime**: Python 3.11+
- **Environment variables**:
  - `DATA_LAKE_BUCKET`: Your S3 bucket name
  - `ATHENA_DATABASE`: Your Athena database name
- **IAM Role permissions**:
  - S3: `s3:ListBucket`, `s3:GetObject`
  - Athena: `athena:StartQueryExecution`, `athena:GetQueryResults`, `athena:GetQueryExecution`
  - Glue: `glue:GetJobs`, `glue:GetJobRuns`, `glue:GetTables`, `glue:GetDatabase`
  - CloudWatch: `cloudwatch:GetMetricStatistics`
  - Lambda: `lambda:ListFunctions`, `lambda:GetFunction`
- **Lambda URL**: Enable function URL with CORS

### 3. Update API Endpoint in JavaScript

Edit `dashboard-dynamic.js`:
```javascript
const METRICS_API_ENDPOINT = 'https://YOUR_LAMBDA_URL.lambda-url.us-east-1.on.aws/metrics';
```

Replace with your actual Lambda function URL.

### 4. Invalidate CloudFront Cache
```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*" \
  --profile noaa-target
```

## Lambda Deployment Example

```bash
# Package Lambda function
cd monitoring/lambda
zip -r dashboard_metrics.zip dashboard_metrics.py

# Create/update Lambda function
aws lambda create-function \
  --function-name noaa-dashboard-metrics \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/LambdaExecutionRole \
  --handler dashboard_metrics.lambda_handler \
  --zip-file fileb://dashboard_metrics.zip \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables="{DATA_LAKE_BUCKET=noaa-federated-lake-899626030376-dev,ATHENA_DATABASE=noaa_data_lake}" \
  --profile noaa-target

# Create Lambda URL
aws lambda create-function-url-config \
  --function-name noaa-dashboard-metrics \
  --auth-type NONE \
  --cors AllowOrigins="*",AllowMethods="GET",MaxAge=3600 \
  --profile noaa-target
```

## Performance Considerations

### API Response Times
- **Bronze layer**: ~2-5 seconds (S3 list + Lambda metrics)
- **Silver layer**: ~3-7 seconds (Glue jobs + S3)
- **Gold layer**: ~4-8 seconds (Athena tables + query performance)
- **Pond details**: ~5-10 seconds (Multi-layer queries + samples)
- **AI metrics**: ~2-4 seconds (CloudWatch metrics)

### Cost Optimization

1. **Client-side caching** (5 min): Reduces API calls by ~90%
2. **Athena query limits**: Queries limited to recent data (24h-30d)
3. **S3 list pagination**: Limited to reasonable batch sizes
4. **CloudWatch metric periods**: 1-hour periods instead of 1-minute

**Estimated costs per 1000 dashboard views** (with caching):
- Lambda: ~$0.02
- Athena: ~$0.05
- S3 API calls: ~$0.01
- **Total**: ~$0.08

## Monitoring

### CloudWatch Logs
Lambda function logs are in:
```
/aws/lambda/noaa-dashboard-metrics
```

### Key Metrics to Monitor
- Lambda invocations
- Lambda errors
- Lambda duration
- API response times (in browser DevTools)

## Troubleshooting

### Issue: "Loading real-time data..." never completes
**Solution**: Check browser console for errors. Common causes:
1. Lambda function URL not set correctly in `dashboard-dynamic.js`
2. CORS not configured on Lambda URL
3. Lambda function timeout (increase to 60s)

### Issue: "Error Loading Data"
**Solution**: Check Lambda CloudWatch logs for errors. Common causes:
1. Missing IAM permissions
2. Athena database/table doesn't exist
3. S3 bucket name incorrect

### Issue: Data seems stale
**Solution**: 
1. Clear browser cache
2. Wait 5 minutes for cache to expire
3. Check Lambda function is actually querying AWS services (not returning cached data)

### Issue: Some metrics show "N/A"
**Solution**: This is normal if:
1. Tables don't exist yet (no data ingested)
2. Athena queries timeout
3. Specific data types not configured

## Development

### Local Testing

You can test the Lambda function locally:
```python
from dashboard_metrics import lambda_handler

# Test bronze layer
event = {
    'queryStringParameters': {
        'metric_type': 'bronze_layer'
    }
}
result = lambda_handler(event, None)
print(result)
```

### Adding New Metrics

1. Add new function in `dashboard_metrics.py`:
```python
def get_my_new_metric() -> Dict[str, Any]:
    # Query AWS services
    return {'metric': 'value'}
```

2. Add handler in `lambda_handler`:
```python
elif metric_type == 'my_new_metric':
    data = get_my_new_metric()
```

3. Add JavaScript function in `dashboard-dynamic.js`:
```javascript
async function showMyNewMetric() {
    const data = await fetchMetrics('my_new_metric');
    // Render data in modal
}
```

4. Add HTML modal and button to trigger it

## Next Steps

### Planned Enhancements
- [ ] Real-time WebSocket updates (eliminate polling)
- [ ] Historical trend charts (past 7/30 days)
- [ ] Export metrics to CSV/JSON
- [ ] Scheduled Lambda to pre-compute expensive queries
- [ ] DynamoDB cache layer for faster responses
- [ ] Alerting thresholds (email if error rate > 5%)

## Support

For issues or questions:
1. Check CloudWatch logs for Lambda function
2. Check browser DevTools console for JavaScript errors
3. Verify IAM permissions on Lambda execution role
4. Test Lambda function directly via AWS Console

---

**Last Updated**: December 10, 2024  
**Version**: 2.0 (Dynamic Data Architecture)  
**Dashboard URL**: https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html