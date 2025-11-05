# 🚀 NOAA Data Lake - Quick Reference

## 📡 Your Endpoints

```
Base URL: https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev
```

### 1. Plain English Queries (AI)
```bash
curl -X POST 'https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/ask' \
  -H 'Content-Type: application/json' \
  -d '{"query":"YOUR QUESTION"}'
```

### 2. Traditional Data API
```bash
curl 'https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/data?ping=true'
```

### 3. Passthrough to Live NOAA (✅ WORKING!)
```bash
# Weather alerts
curl 'https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/passthrough?service=nws&endpoint=alerts/active'

# Alerts by state
curl 'https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/passthrough?service=nws&endpoint=alerts/active&area=CA'

# Tide data
curl 'https://z0rld53i7a.execute-api.us-east-1.amazonaws.com/dev/passthrough?service=tides&station=9414290&hours_back=24'
```

## 📊 Test Results

✅ **Passthrough Working:** 466 live weather alerts  
✅ **Tides Working:** 60 data points from San Francisco  
⚠️ **AI Queries:** Need Gold layer population

## ⏭️ Next Step

Populate Gold layer (5 min):
```sql
-- Run in AWS Athena console
CREATE TABLE noaa_gold_dev.atmospheric_aggregated AS
SELECT 
  CASE 
    WHEN properties.areaDesc LIKE '%CA%' THEN 'CA'
    WHEN properties.areaDesc LIKE '%TX%' THEN 'TX'
    ELSE 'Other'
  END as region,
  properties.event as event_type,
  COUNT(*) as alert_count,
  CAST(SUBSTR(properties.onset, 1, 10) AS DATE) as date
FROM noaa_bronze_dev.atmospheric_raw
WHERE properties.onset IS NOT NULL
GROUP BY 
  CASE 
    WHEN properties.areaDesc LIKE '%CA%' THEN 'CA'
    WHEN properties.areaDesc LIKE '%TX%' THEN 'TX'
    ELSE 'Other'
  END,
  properties.event,
  CAST(SUBSTR(properties.onset, 1, 10) AS DATE);
```

## 📚 Documentation

- `DEPLOYMENT_COMPLETE.md` - What just happened
- `START_HERE.md` - Quick start guide
- `QUICK_FIX_GUIDE.md` - Detailed fixes
- `ACTION_PLAN.md` - Full roadmap

## 🎉 Status

**Deployment:** ✅ SUCCESSFUL  
**Passthrough:** ✅ LIVE DATA  
**Remaining:** Populate Gold layer (5 min)
