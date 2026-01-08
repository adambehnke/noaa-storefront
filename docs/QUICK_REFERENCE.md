# NOAA Data Lake - Quick Reference

## 🎯 Test the Chatbot
```
https://d244ik6grpfthq.cloudfront.net/?v=1763591583
```

## 📊 System Status
```bash
bash scripts/verify_system.sh
```

## 🔍 Monitor Ingestion
```bash
# Watch live logs
AWS_PROFILE=noaa-target aws logs tail /aws/lambda/noaa-ingest-oceanic-dev --follow

# Check data volume
AWS_PROFILE=noaa-target aws s3 ls s3://noaa-federated-lake-899626030376-dev/ \
  --recursive --summarize
```

## 🧪 Test API Directly
```bash
curl -X POST "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/query" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"Charleston flooding risk\", \"timestamp\": $(date +%s)}" | jq .
```

## 📋 Active Schedules
- Oceanic: Every 5 minutes
- Atmospheric: Every 5 minutes  
- Buoy: Every 5 minutes
- Climate: Every hour
- Spatial: Daily
- Terrestrial: Every 30 minutes

## 📁 File Locations
- Documentation: `docs/`
- Scripts: `scripts/`
- Backups: `backups/`
- Deployment logs: `deployment/`
- Status: `docs/DATA_LAKE_STATUS.md`

## ✅ Verification Checklist
- [x] All 6 ponds ingesting
- [x] 398+ files in data lake
- [x] Chatbot querying live data
- [x] Cache busting working
- [x] CORS configured
- [x] Files organized

## 🚀 Current Status
**Data Lake:** 175 MB | 398 files  
**Ponds:** 6/6 active  
**Ingestion:** Real-time (5min intervals)  
**Chatbot:** Querying live data ✅  
**Cache:** Busted ✅

