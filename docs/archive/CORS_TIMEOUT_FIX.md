# CORS Timeout Issue - Root Cause & Fix

## Problem
Browser shows: "No 'Access-Control-Allow-Origin' header is present"  
Actual issue: **Lambda timing out** (30+ seconds), API Gateway returns error without CORS headers

## Root Cause
When I added:
1. Athena pagination (to get ALL data instead of 1000 rows)
2. Detailed summary extraction
3. Multiple pond queries in parallel

The Lambda now takes **33+ seconds** but API Gateway timeout is **29 seconds**

## Immediate Fix (Applied)
Switched API Gateway back to fast Lambda (`noaa-enhanced-handler-dev`)

## Permanent Solution Options

### Option 1: Reduce Data Volume (Quick)
```python
# In query_gold_layer(), limit records BEFORE processing
MAX_RECORDS = 1000  # Down from 5000
results = athena.get_query_results(QueryExecutionId=query_id, MaxResults=1000)
# Don't paginate - just use first 1000 rows
```

### Option 2: Async Processing (Better)
1. Lambda returns immediately with request ID
2. Starts background processing
3. Frontend polls for results
4. Works for long-running queries

### Option 3: Caching (Best for production)
1. Cache results in DynamoDB/ElastiCache
2. Return cached data for similar queries
3. Background refresh every 15 minutes

### Option 4: Streaming Response
Use Lambda Response Streaming (new AWS feature)
- Stream data as it's ready
- No timeout issues
- Frontend gets partial results immediately

## Current Status
✅ Web UI working again (using old Lambda)  
⚠️ No meaningful summaries yet (need to update old Lambda OR fix new Lambda speed)

## Recommended Next Step
Update the FAST Lambda with JUST the meaningful summary code (no pagination):
1. Keep 1000 record limit
2. Add extract_pond_summary() function
3. Update display logic
4. Deploy to noaa-enhanced-handler-dev

This gives us: Fast response + Meaningful data ✅
