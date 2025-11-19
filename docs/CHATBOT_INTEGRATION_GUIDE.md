# Federated API (Chatbot) Integration Guide

## Summary

All 6 data ponds are now complete with ingestion pipelines. The federated API needs to be updated to query all ponds.

## Changes Required

### 1. Add New Athena Query Functions

Add to `lambda-enhanced-handler/lambda_function.py`:

```python
def query_gold_buoy(location: Optional[str] = None, limit: int = 10) -> Dict:
    """Query buoy gold layer"""
    where_clause = f"WHERE station_name LIKE '%{location}%'" if location else ""
    
    sql = f"""
    SELECT station_id, station_name, state, region,
           avg_wave_height_m, max_wave_height_m,
           avg_wind_speed_mps, avg_water_temp_c,
           date
    FROM {ATHENA_DB}.buoy_aggregated
    {where_clause}
    ORDER BY date DESC
    LIMIT {limit}
    """
    results = query_athena(sql)
    return {
        "pond": "buoy",
        "service": "NDBC Buoy Data",
        "record_count": len(results),
        "data": results,
    }

def query_gold_climate(location: Optional[str] = None, limit: int = 30) -> Dict:
    """Query climate gold layer"""
    where_clause = f"WHERE city LIKE '%{location}%'" if location else ""
    
    sql = f"""
    SELECT station_name, city, state,
           avg_high_temp_f, avg_low_temp_f,
           total_precip_in, total_snow_in,
           date
    FROM {ATHENA_DB}.climate_aggregated
    {where_clause}
    ORDER BY date DESC
    LIMIT {limit}
    """
    results = query_athena(sql)
    return {
        "pond": "climate",
        "service": "Climate Data Online (CDO)",
        "record_count": len(results),
        "data": results,
    }

def query_gold_spatial(query_type: str = "stations", limit: int = 100) -> Dict:
    """Query spatial gold layer"""
    if query_type == "stations":
        sql = f"""
        SELECT timestamp, total_stations
        FROM {ATHENA_DB}.spatial_stations
        ORDER BY date DESC
        LIMIT 1
        """
    else:  # zones
        sql = f"""
        SELECT timestamp, zone_type, total_zones
        FROM {ATHENA_DB}.spatial_zones
        ORDER BY date DESC
        LIMIT {limit}
        """
    
    results = query_athena(sql)
    return {
        "pond": "spatial",
        "service": "NWS Spatial Metadata",
        "record_count": len(results),
        "data": results,
    }

def query_gold_terrestrial(limit: int = 10) -> Dict:
    """Query terrestrial gold layer (drought data)"""
    sql = f"""
    SELECT timestamp, total_drought_features,
           has_exceptional_drought, has_extreme_drought,
           average_severity_score, date
    FROM {ATHENA_DB}.terrestrial_drought
    ORDER BY date DESC
    LIMIT {limit}
    """
    results = query_athena(sql)
    return {
        "pond": "terrestrial",
        "service": "US Drought Monitor",
        "record_count": len(results),
        "data": results,
    }
```

### 2. Update Intent Recognition

Add keywords for new ponds:

```python
def detect_intent(query: str) -> str:
    """Detect user intent from query"""
    query_lower = query.lower()
    
    # Buoy queries
    if any(word in query_lower for word in ["buoy", "wave", "offshore", "marine conditions"]):
        return "buoy"
    
    # Climate queries
    if any(word in query_lower for word in ["climate", "historical weather", "past temperature", "precipitation history"]):
        return "climate"
    
    # Drought queries
    if any(word in query_lower for word in ["drought", "dry conditions", "water shortage"]):
        return "drought"
    
    # Existing intents...
    # weather, ocean, tide, etc.
```

### 3. Add Query Handlers

```python
def handle_buoy_query(query: str, location: Optional[Dict] = None) -> Dict:
    """Handle buoy/marine conditions queries"""
    try:
        buoy_data = query_gold_buoy(
            location=location.get("name") if location else None,
            limit=10
        )
        
        if buoy_data["record_count"] > 0:
            latest = buoy_data["data"][0]
            
            answer = f"""# 🌊 **MARINE CONDITIONS**

**Station:** {latest.get('station_name', 'N/A')}
**Location:** {latest.get('region', 'N/A')}

## Wave Conditions
- **Average Height:** {latest.get('avg_wave_height_m', 'N/A')} meters
- **Max Height:** {latest.get('max_wave_height_m', 'N/A')} meters

## Wind
- **Average Speed:** {latest.get('avg_wind_speed_mps', 'N/A')} m/s

## Water Temperature
- **Current:** {latest.get('avg_water_temp_c', 'N/A')}°C

**Last Updated:** {latest.get('date', 'N/A')}

---
**Data Source:** NOAA National Data Buoy Center (NDBC)
"""
            
            return {
                "success": True,
                "answer": answer,
                "data": buoy_data,
                "ponds_queried": ["buoy"],
            }
    except Exception as e:
        logger.error(f"Error handling buoy query: {e}")
        return {
            "success": False,
            "error": str(e),
        }

def handle_climate_query(query: str, location: Optional[Dict] = None) -> Dict:
    """Handle historical climate queries"""
    try:
        climate_data = query_gold_climate(
            location=location.get("name") if location else None,
            limit=30
        )
        
        if climate_data["record_count"] > 0:
            # Calculate averages from recent data
            data = climate_data["data"]
            
            avg_high = sum(d.get('avg_high_temp_f', 0) for d in data if d.get('avg_high_temp_f')) / len(data)
            avg_low = sum(d.get('avg_low_temp_f', 0) for d in data if d.get('avg_low_temp_f')) / len(data)
            total_precip = sum(d.get('total_precip_in', 0) for d in data if d.get('total_precip_in'))
            
            answer = f"""# 📊 **CLIMATE DATA**

**Location:** {data[0].get('city', 'N/A')}, {data[0].get('state', 'N/A')}
**Period:** Last 30 days

## Temperature
- **Average High:** {avg_high:.1f}°F
- **Average Low:** {avg_low:.1f}°F

## Precipitation
- **Total:** {total_precip:.2f} inches

**Data Source:** NOAA Climate Data Online (CDO)
"""
            
            return {
                "success": True,
                "answer": answer,
                "data": climate_data,
                "ponds_queried": ["climate"],
            }
    except Exception as e:
        logger.error(f"Error handling climate query: {e}")
        return {
            "success": False,
            "error": str(e),
        }

def handle_drought_query(query: str) -> Dict:
    """Handle drought condition queries"""
    try:
        drought_data = query_gold_terrestrial(limit=1)
        
        if drought_data["record_count"] > 0:
            latest = drought_data["data"][0]
            
            severity_score = latest.get('average_severity_score', 0)
            severity_text = "Minimal" if severity_score < 1 else \
                           "Moderate" if severity_score < 2 else \
                           "Severe" if severity_score < 3 else "Extreme"
            
            answer = f"""# 🌵 **DROUGHT CONDITIONS**

## Current Status

**Overall Severity:** {severity_text} ({severity_score:.2f}/4.0)

**Exceptional Drought:** {'Yes' if latest.get('has_exceptional_drought') else 'No'}
**Extreme Drought:** {'Yes' if latest.get('has_extreme_drought') else 'No'}

**Total Affected Areas:** {latest.get('total_drought_features', 'N/A')}

**Last Updated:** {latest.get('date', 'N/A')}

---
**Data Source:** US Drought Monitor
"""
            
            return {
                "success": True,
                "answer": answer,
                "data": drought_data,
                "ponds_queried": ["terrestrial"],
            }
    except Exception as e:
        logger.error(f"Error handling drought query: {e}")
        return {
            "success": False,
            "error": str(e),
        }
```

### 4. Update Main Query Handler

```python
def handle_query(query: str) -> Dict:
    """Main query handler - route to appropriate pond"""
    
    intent = detect_intent(query)
    location = extract_location(query)
    
    # Route to appropriate handler
    if intent == "buoy":
        return handle_buoy_query(query, location)
    elif intent == "climate":
        return handle_climate_query(query, location)
    elif intent == "drought":
        return handle_drought_query(query)
    elif intent == "ocean":
        return handle_ocean_query(query, location)
    elif intent == "weather":
        return get_current_weather(location)
    elif intent == "federated":
        return handle_federated_query(query, [location] if location else [])
    # ... existing handlers
```

## Testing Queries

After integration, test with:

```bash
# Buoy
curl -X POST "https://.../dev/ask" -d '{"query": "What are the wave heights offshore?"}'

# Climate
curl -X POST "https://.../dev/ask" -d '{"query": "What was the historical temperature in New York?"}'

# Drought
curl -X POST "https://.../dev/ask" -d '{"query": "What are the current drought conditions?"}'

# Multi-pond
curl -X POST "https://.../dev/ask" -d '{"query": "Give me weather, ocean temps, and drought conditions"}'
```

## Summary

1. Add 4 new query functions (buoy, climate, spatial, terrestrial)
2. Update intent detection with new keywords
3. Create handlers for each new pond type
4. Update main routing logic
5. Test all query types

All ingestion code is complete. Chatbot integration is the final step!

