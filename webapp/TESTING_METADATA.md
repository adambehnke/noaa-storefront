# Testing the NOAA Data Lake Metadata Feature

## Quick Start

The metadata feature provides **real-time** information about all data ponds, including:
- How fresh the data is (last update time)
- Number of files ingested
- Storage size per pond
- Layer breakdown (Bronze, Silver, Gold)

## Where to Test

**Production URL**: https://d244ik6grpfthq.cloudfront.net/

## Testing Methods

### Method 1: Quick Actions Button (Recommended)

1. Open the chatbot URL
2. Look at the **left sidebar**
3. Find the **"Quick Actions"** section
4. Click the **"Data Lake Metrics"** button
5. Wait 2-4 seconds for the metadata to load
6. You should see:
   - Overall statistics (total ponds, files, size)
   - Individual pond cards showing:
     - Status badges (Active/Empty, Freshness)
     - File counts
     - Storage size
     - Last update time

**Expected Result**: A comprehensive overview of all 6 data ponds with current statistics.

### Method 2: Click on Endpoint Names

1. Open the chatbot URL
2. In the left sidebar, expand **"Endpoints & Services"**
3. Click the **"Endpoints & Services"** header to expand it
4. Click on any **pond name** (the underlined text, e.g., "Atmospheric", "Oceanic")
5. Wait 2-4 seconds
6. You should see:
   - Detailed metadata for that specific pond
   - Status and freshness badges
   - Summary statistics
   - Ingestion timeline
   - Layer-by-layer breakdown

**Expected Result**: Detailed metadata for the selected pond only.

### Method 3: Ask the Chatbot

Type any of these queries:
- "Show me data lake metrics"
- "What's the status of all ponds?"
- "How fresh is the atmospheric data?"
- "Show metadata for oceanic pond"

**Expected Result**: The bot should recognize the metadata request and display the information.

## What to Look For

### ✅ Success Indicators

1. **Status Badges**:
   - Green "ACTIVE" badge = pond is receiving data
   - Green "DATA: EXCELLENT" = updated < 30 min ago
   - Yellow badges = moderate freshness (< 6 hours)

2. **File Counts**:
   - Atmospheric: ~51,000 files
   - Oceanic: ~107,000 files
   - Buoy: ~51,000 files
   - Climate: ~1,400 files
   - Spatial: ~200 files
   - Terrestrial: ~5,700 files

3. **Total Size**: ~72-75 GB across all ponds

4. **Freshness**:
   - Most ponds: < 5 minutes (excellent)
   - Climate: < 60 minutes (good)
   - Spatial: May be hours/days old (expected)

5. **Layer Breakdown**:
   - Each pond should show Bronze, Silver, and Gold layers
   - Each layer should have file counts and sizes

### ❌ Error Indicators

1. "Could not fetch metadata" message
2. No response after 5+ seconds
3. Missing badges or statistics
4. Negative freshness values
5. Zero file counts for active ponds

## Troubleshooting

### Issue: Button does nothing when clicked

**Solution**: 
- Check browser console (F12) for errors
- Verify CloudFront cache has been invalidated
- Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)

### Issue: "Could not fetch metadata" error

**Solution**:
- Check that Lambda function `noaa-ai-query-dev` is deployed
- Verify Lambda has S3 read permissions
- Check CloudWatch logs: `/aws/lambda/noaa-ai-query-dev`

### Issue: Stale data showing

**Solution**:
- This is real-time data from S3, so "stale" might be accurate
- Check Lambda ingestion functions are running
- Review EventBridge schedules

### Issue: Very slow response (>10 seconds)

**Solution**:
- Lambda may be cold-starting (normal for first request)
- Large ponds take longer to scan
- Try again - subsequent requests should be faster

## API Testing (Advanced)

You can test the API directly using curl:

```bash
curl -X POST https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_metadata"
  }'
```

Or for a specific pond:

```bash
curl -X POST https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_metadata",
    "pond": "atmospheric"
  }'
```

## Expected Performance

- **First Request**: 3-5 seconds (Lambda cold start)
- **Subsequent Requests**: 2-3 seconds
- **Response Size**: 10-20 KB
- **Freshness**: Data is queried from S3 in real-time

## What Makes This Different

### Static Metadata (Old Approach)
- Pre-generated JSON file
- Manually updated
- Could be hours/days old

### Dynamic Metadata (New Approach)
- ✅ Fetched from S3 on-demand
- ✅ Always fresh
- ✅ Reflects current state
- ✅ Includes latest ingestion times

## Validation Checklist

- [ ] Quick Actions button loads metadata
- [ ] All 6 ponds show in overview
- [ ] File counts are reasonable (not zero)
- [ ] Freshness times make sense
- [ ] Status badges display correctly
- [ ] Layer breakdown shows Bronze/Silver/Gold
- [ ] Clicking pond names shows detailed view
- [ ] Response time is under 5 seconds
- [ ] No JavaScript errors in console
- [ ] Works on mobile/tablet

## Files Modified

- `lambda-enhanced-handler/lambda_function.py` - Added metadata collection
- `webapp/app.js` - Added metadata display functions
- `webapp/index.html` - Added Quick Actions button

## Deployment Status

✅ **Lambda**: Deployed (`noaa-ai-query-dev`)
✅ **Frontend**: Deployed to S3 (`noaa-chatbot-prod-899626030376`)
✅ **CloudFront**: Cache invalidated

Last Deployed: December 9, 2025

## Support

If you encounter issues:
1. Check browser console (F12 > Console tab)
2. Check Lambda logs in CloudWatch
3. Verify S3 bucket access
4. Test API endpoint directly with curl

---

**Quick Test Command**:
```
Open https://d244ik6grpfthq.cloudfront.net/ → Click "Data Lake Metrics" → See results in 2-3 seconds
```
