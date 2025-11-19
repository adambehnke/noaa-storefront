# Maritime Route Planning - Quick Start Guide 🌊⛵

**Get started with NOAA Maritime Navigation Intelligence in 5 minutes**

---

## 🚀 Quick Start

### Test the System

```bash
# Run the complete test suite
python3 test-scripts/test_maritime_route_planning.py

# Expected output: 6/6 tests passing in ~15 seconds
```

### Example Queries

#### 1. Check Active Marine Alerts
```bash
aws lambda invoke --function-name noaa-intelligent-orchestrator-dev \
  --region us-east-1 \
  --payload '{"query": "What are the current marine weather alerts?"}' \
  response.json && cat response.json | jq '.answer' -r
```

#### 2. Plan a Maritime Route
```bash
aws lambda invoke --function-name noaa-intelligent-orchestrator-dev \
  --region us-east-1 \
  --payload '{"query": "Maritime route from San Francisco to Los Angeles - current conditions?"}' \
  response.json && cat response.json | jq '.answer' -r
```

#### 3. Find Nearest Stations
```bash
aws lambda invoke --function-name noaa-intelligent-orchestrator-dev \
  --region us-east-1 \
  --payload '{"query": "Find weather stations near Miami"}' \
  response.json && cat response.json | jq '.answer' -r
```

---

## 📊 Data Available

- **Alerts**: 11,180 active weather alerts and marine advisories
- **Stations**: 9,000 observation station locations
- **Atmospheric**: 17,007 weather observations
- **Oceanic**: 51,191 tide and current records
- **Buoy**: 2,042,516 offshore observations
- **Total**: 2.1M+ records updated in real-time

---

## 💬 Natural Language Queries

Ask questions naturally:

- "What are the wave conditions for sailing to Catalina Island?"
- "Are there any small craft advisories for the Florida Keys?"
- "Show me tide predictions for Boston Harbor"
- "What's the nearest buoy to 37°N 123°W?"
- "Is it safe to navigate from Seattle to Vancouver today?"

---

## 📍 Geographic Coverage

- ✅ All US coastal waters
- ✅ Offshore waters and exclusive economic zone
- ✅ Great Lakes
- ✅ US territories (Puerto Rico, Hawaii, Alaska, etc.)
- ✅ 9,000 observation stations nationwide

---

## 🎯 Use Cases

1. **Maritime Safety**: Check alerts before departure
2. **Route Planning**: Assess conditions along entire routes
3. **Fishing**: Find optimal conditions and locations
4. **Sailing**: Plan based on wind and wave forecasts
5. **Boating**: Check small craft advisories
6. **Research**: Access historical maritime data

---

## 📞 Need Help?

- **Documentation**: See `docs/MARITIME_ROUTE_PLANNING.md`
- **Test Results**: Run `python3 test-scripts/test_maritime_route_planning.py`
- **AWS Console**: Check CloudWatch logs for errors

---

**Status**: ✅ All Systems Operational  
**Last Updated**: November 18, 2025  
**Version**: 3.0  
