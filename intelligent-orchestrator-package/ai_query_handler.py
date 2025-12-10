#!/usr/bin/env python3
"""
Pure AI-Driven NOAA Query Orchestrator
Version 4.0 - Dynamic AI with Real Data

NO HARDCODED TEMPLATES. AI decides:
- What data to retrieve
- How to present it
- What's relevant to show

Gets REAL data from NOAA APIs and lets AI interpret dynamically.
"""

import asyncio
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")

# Environment
BEDROCK_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"
S3_BUCKET = os.environ.get("S3_BUCKET", "noaa-federated-lake-899626030376-dev")

# NOAA API endpoints
NOAA_APIS = {
    "nws_weather": {
        "base_url": "https://api.weather.gov",
        "description": "National Weather Service - current conditions, forecasts, alerts",
        "endpoints": {
            "observations": "/stations/{station}/observations/latest",
            "forecast": "/points/{lat},{lon}/forecast",
            "alerts": "/alerts/active?area={area}",
            "stations": "/stations?state={state}",
        },
    },
    "tides": {
        "base_url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
        "description": "Tides and currents - water levels, predictions, temperatures",
        "params": "?product={product}&station={station}&date=latest&time_zone=gmt&format=json&units=metric",
    },
    "buoys": {
        "base_url": "https://www.ndbc.noaa.gov/data/realtime2",
        "description": "Buoy data - waves, wind, water temperature",
        "endpoints": {
            "latest": "/{buoy_id}.txt",
        },
    },
}


def call_nws_api(endpoint: str, **kwargs) -> Dict:
    """Call National Weather Service API"""
    try:
        url = f"https://api.weather.gov{endpoint.format(**kwargs)}"
        req = urllib.request.Request(url, headers={"User-Agent": "NOAA-DataLake/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"NWS API error: {e}")
        return {}


def call_tides_api(station: str, product: str = "water_level") -> Dict:
    """Call Tides and Currents API"""
    try:
        url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product={product}&station={station}&date=latest&time_zone=gmt&format=json&units=metric"
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Tides API error: {e}")
        return {}


def get_nearby_stations(location: str) -> List[str]:
    """Get weather stations for a location - simple mapping"""
    station_map = {
        "seattle": ["KSEA", "KBFI", "KPAE"],
        "new york": ["KJFK", "KLGA", "KEWR", "KTEB"],
        "nyc": ["KJFK", "KLGA", "KEWR"],
        "boston": ["KBOS", "KBED", "KOWD"],
        "portland": ["KPWM", "KPOM"],
        "miami": ["KMIA", "KOPF", "KTMB"],
        "los angeles": ["KLAX", "KBUR", "KLGB"],
        "san francisco": ["KSFO", "KOAK", "KSJC"],
        "chicago": ["KORD", "KMDW", "KPWK"],
    }

    location_lower = location.lower()
    for key, stations in station_map.items():
        if key in location_lower:
            return stations

    return ["KJFK"]  # Default


def get_tide_stations(location: str) -> List[str]:
    """Get tide stations for a location"""
    tide_map = {
        "boston": ["8443970"],
        "portland": ["8418150"],
        "new york": ["8518750"],
        "seattle": ["9447130"],
        "miami": ["8723214"],
        "san francisco": ["9414290"],
    }

    location_lower = location.lower()
    for key, stations in tide_map.items():
        if key in location_lower:
            return stations

    return []


def understand_query_with_ai(query: str) -> Dict:
    """Use AI to understand what the user wants"""

    prompt = f"""Analyze this query about weather/ocean/climate data:

"{query}"

Determine:
1. What is the user asking for? (intent: temperature, forecast, historical, route_planning, conditions, alerts, etc.)
2. What location(s) are mentioned?
3. What time frame? (current, forecast, historical)
4. What specific data types are needed? (temperature, wind, waves, tides, alerts, etc.)

Respond with JSON only:
{{
    "intent": "temperature|forecast|historical|route_planning|conditions|alerts|climate_analysis",
    "locations": ["location1", "location2"],
    "timeframe": "current|forecast|historical",
    "data_needed": ["temperature", "wind", "waves", "tides", "alerts"],
    "context": "brief summary of what user wants"
}}"""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.error(f"AI understanding error: {e}")

    # Fallback
    return {
        "intent": "conditions",
        "locations": ["general"],
        "timeframe": "current",
        "data_needed": ["temperature", "wind"],
        "context": query,
    }


def fetch_from_s3_pond(
    pond: str, data_type: str, lookback_hours: int = 24
) -> List[Dict]:
    """Fetch data from S3 data lake for a specific pond"""
    try:
        now = datetime.utcnow()
        results = []

        # Check last 24 hours of data
        for hours_ago in range(lookback_hours):
            check_time = now - timedelta(hours=hours_ago)
            prefix = f"gold/{pond}/{data_type}/year={check_time.year}/month={check_time.month:02d}/day={check_time.day:02d}/"

            try:
                response = s3.list_objects_v2(
                    Bucket=S3_BUCKET, Prefix=prefix, MaxKeys=10
                )

                if "Contents" in response:
                    # Get the most recent file
                    files = sorted(
                        response["Contents"],
                        key=lambda x: x["LastModified"],
                        reverse=True,
                    )
                    for file_obj in files[:3]:  # Get up to 3 most recent files
                        try:
                            obj = s3.get_object(Bucket=S3_BUCKET, Key=file_obj["Key"])
                            data = json.loads(obj["Body"].read().decode("utf-8"))
                            if isinstance(data, list):
                                results.extend(data)
                            else:
                                results.append(data)

                            if len(results) >= 50:  # Limit results
                                return results[:50]
                        except Exception as e:
                            logger.debug(f"Error reading {file_obj['Key']}: {e}")
                            continue

            except Exception as e:
                logger.debug(f"Error listing S3 for {prefix}: {e}")
                continue

        return results
    except Exception as e:
        logger.error(f"S3 fetch error for {pond}/{data_type}: {e}")
        return []


def fetch_real_data(understanding: Dict) -> Dict:
    """Fetch actual data from S3 data lake across all relevant ponds"""

    data = {
        "atmospheric": [],
        "oceanic": [],
        "buoy": [],
        "climate": [],
        "terrestrial": [],
        "alerts": [],
        "metadata": {
            "ponds_queried": [],
            "sources": [],
            "record_count": 0,
        },
    }

    data_needed = understanding.get("data_needed", [])
    intent = understanding.get("intent", "conditions")

    # Query atmospheric pond
    if any(
        d in data_needed
        for d in ["temperature", "wind", "conditions", "weather", "alerts"]
    ):
        logger.info("Querying atmospheric pond")

        # Get weather observations
        obs = fetch_from_s3_pond("atmospheric", "observations", lookback_hours=6)
        if obs:
            data["atmospheric"] = obs
            data["metadata"]["ponds_queried"].append("atmospheric")
            data["metadata"]["sources"].append("Atmospheric Observations")
            data["metadata"]["record_count"] += len(obs)
            logger.info(f"Found {len(obs)} atmospheric observations")

        # Get alerts
        alerts = fetch_from_s3_pond("atmospheric", "alerts", lookback_hours=2)
        if alerts:
            data["alerts"] = alerts[:20]  # Limit alerts
            data["metadata"]["sources"].append("Weather Alerts")
            logger.info(f"Found {len(alerts)} weather alerts")

    # Query oceanic pond
    if any(
        d in data_needed
        for d in ["tides", "water", "ocean", "coastal", "wind", "waves"]
    ):
        logger.info("Querying oceanic pond")

        # Get water level data
        water = fetch_from_s3_pond("oceanic", "water_level", lookback_hours=6)
        if water:
            data["oceanic"].extend(water)
            data["metadata"]["ponds_queried"].append("oceanic")
            data["metadata"]["sources"].append("Oceanic Water Levels")
            data["metadata"]["record_count"] += len(water)
            logger.info(f"Found {len(water)} oceanic water level records")

        # Get wind data
        wind = fetch_from_s3_pond("oceanic", "wind", lookback_hours=6)
        if wind:
            data["oceanic"].extend(wind)
            if "oceanic" not in data["metadata"]["ponds_queried"]:
                data["metadata"]["ponds_queried"].append("oceanic")
            data["metadata"]["sources"].append("Oceanic Wind")
            data["metadata"]["record_count"] += len(wind)
            logger.info(f"Found {len(wind)} oceanic wind records")

    # Query buoy pond
    if any(d in data_needed for d in ["waves", "buoy", "ocean", "marine"]):
        logger.info("Querying buoy pond")
        buoy_data = fetch_from_s3_pond("buoy", "metadata", lookback_hours=6)
        if buoy_data:
            data["buoy"] = buoy_data
            data["metadata"]["ponds_queried"].append("buoy")
            data["metadata"]["sources"].append("Buoy Data")
            data["metadata"]["record_count"] += len(buoy_data)
            logger.info(f"Found {len(buoy_data)} buoy records")

    # Query climate pond for historical/climate queries
    if intent in ["historical", "climate_analysis", "climate"] or any(
        d in data_needed for d in ["climate", "historical"]
    ):
        logger.info("Querying climate pond")
        climate_data = fetch_from_s3_pond(
            "climate", "daily", lookback_hours=168
        )  # 7 days
        if climate_data:
            data["climate"] = climate_data[:30]  # Limit climate data
            data["metadata"]["ponds_queried"].append("climate")
            data["metadata"]["sources"].append("Climate Data")
            data["metadata"]["record_count"] += len(data["climate"])
            logger.info(f"Found {len(data['climate'])} climate records")

    # Query terrestrial pond for land-based data
    if any(d in data_needed for d in ["terrestrial", "land", "river", "stream"]):
        logger.info("Querying terrestrial pond")
        terrestrial_data = fetch_from_s3_pond("terrestrial", "flow", lookback_hours=12)
        if terrestrial_data:
            data["terrestrial"] = terrestrial_data
            data["metadata"]["ponds_queried"].append("terrestrial")
            data["metadata"]["sources"].append("Terrestrial/River Data")
            data["metadata"]["record_count"] += len(terrestrial_data)
            logger.info(f"Found {len(terrestrial_data)} terrestrial records")

    logger.info(
        f"Total records fetched: {data['metadata']['record_count']} from {len(data['metadata']['ponds_queried'])} ponds"
    )

    return data


def synthesize_with_ai(query: str, understanding: Dict, data: Dict) -> str:
    """Let AI dynamically create response based on query and actual data"""

    # Count actual data from all ponds
    atmospheric_count = len(data.get("atmospheric", []))
    oceanic_count = len(data.get("oceanic", []))
    buoy_count = len(data.get("buoy", []))
    climate_count = len(data.get("climate", []))
    terrestrial_count = len(data.get("terrestrial", []))
    alert_count = len(data.get("alerts", []))
    total_count = (
        atmospheric_count
        + oceanic_count
        + buoy_count
        + climate_count
        + terrestrial_count
        + alert_count
    )

    prompt = f"""You are an expert NOAA data analyst. Answer this user's question using the REAL data provided.

User Question: "{query}"

What the user wants: {understanding.get("context")}

Real Data Retrieved from Multiple NOAA Data Ponds:
- Atmospheric: {atmospheric_count} records
- Oceanic: {oceanic_count} records
- Buoy: {buoy_count} records
- Climate: {climate_count} records
- Terrestrial: {terrestrial_count} records
- Alerts: {alert_count} records

Data Ponds Queried: {data.get("metadata", {}).get("ponds_queried", [])}
Sources: {data.get("metadata", {}).get("sources", [])}

ACTUAL DATA:
{json.dumps(data, indent=2, default=str)[:8000]}

Instructions:
1. **Answer ONLY what the user asked** - don't add irrelevant sections
2. **Use the ACTUAL DATA** - cite real measurements, station IDs, timestamps
3. **Be specific and comprehensive**:
   - Include relevant data from ALL ponds queried
   - Show temperature, wind, water levels, alerts as relevant
   - Include station IDs and exact measurements
   - Show trends if multiple records available
4. **Format appropriately**:
   - Current conditions → Latest readings from atmospheric/oceanic ponds
   - Weather query → Atmospheric observations + alerts
   - Ocean/coastal → Oceanic + buoy data with water levels, wind, waves
   - Climate/historical → Climate pond data with trends
   - Comprehensive query → Synthesize data from multiple ponds
5. **Use clear Markdown formatting** with sections based on what user asked
6. **If alerts exist, ALWAYS mention them** - safety is critical
6. **Include a data summary** at the end showing:
   - What data sources were used
   - How many stations/measurements
   - Actual ranges (e.g., "Temps: 12-16°C | Winds: 5-15 knots | 5 stations")

Examples of good responses:

For "What's the temperature in Seattle?":
# Temperature Analysis: Seattle

**Current Temperature: 14.2°C (57.6°F)**

Based on observations from Seattle-Tacoma International Airport (KSEA) at 2:53 PM local time.

## Data Sources
- Atmospheric: 14.2°C from 1 station (KSEA)

For "Plan route Boston to Portland":
# Maritime Route Analysis: Boston to Portland, Maine

## Current Conditions

**Wind**: 15-18 knots from NW
**Visibility**: Good (10+ miles)
**Water Temperature**: 12°C

### Weather Stations
- Boston Logan (KBOS): 15kt winds, clear
- Portland Intl (KPWM): 18kt winds, clear

## Navigation Recommendations
- Favorable conditions for transit
- Monitor wind shifts in Casco Bay
- Current wind speeds suitable for small craft

## Data Sources
- Atmospheric: Temps: 12-14°C | Winds: 15-18 knots | 2 stations

CRITICAL: Do NOT include sections for data types not requested:
- Don't show ocean/tide data unless query mentions water/ocean/tides
- Don't show wind advisories unless query is about routes/navigation or specifically asks
- Don't show wave data unless query mentions waves/buoys/maritime

Respond with ONLY the formatted markdown answer. Be concise and relevant."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 3000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                }
            ),
        )

        result = json.loads(response["body"].read())
        answer = result["content"][0]["text"].strip()
        return answer

    except Exception as e:
        logger.error(f"AI synthesis error: {e}")

        # Comprehensive fallback with multi-pond data
        response = f"# Analysis: {query}\n\n"

        # Show atmospheric data
        if atmospheric_count > 0:
            response += "## Weather Conditions\n\n"
            stations = set(o.get("station_id") for o in data["atmospheric"])
            temps = [
                o.get("avg_temperature")
                for o in data["atmospheric"]
                if o.get("avg_temperature")
            ]
            winds = [
                o.get("avg_wind_speed")
                for o in data["atmospheric"]
                if o.get("avg_wind_speed")
            ]

            if temps:
                avg_temp = sum(temps) / len(temps)
                response += f"**Temperature**: {avg_temp:.1f}°C ({avg_temp * 9 / 5 + 32:.1f}°F) - Range: {min(temps):.1f}°C to {max(temps):.1f}°C\n"
            if winds:
                avg_wind = sum(winds) / len(winds)
                response += f"**Wind**: {avg_wind:.1f} knots - Range: {min(winds):.1f} to {max(winds):.1f} knots\n"
            response += f"**Stations**: {len(stations)} stations reporting\n\n"

        # Show oceanic data
        if oceanic_count > 0:
            response += "## Ocean/Coastal Conditions\n\n"
            water_levels = [
                o.get("avg_value")
                for o in data["oceanic"]
                if o.get("product") == "water_level" and o.get("avg_value")
            ]
            ocean_winds = [
                o.get("avg_wind_speed")
                for o in data["oceanic"]
                if o.get("avg_wind_speed")
            ]

            if water_levels:
                response += f"**Water Levels**: {len(water_levels)} station(s) - Range: {min(water_levels):.2f}m to {max(water_levels):.2f}m\n"
            if ocean_winds:
                avg_ocean_wind = sum(ocean_winds) / len(ocean_winds)
                response += f"**Ocean Wind**: {avg_ocean_wind:.1f} knots average\n"

            stations = set(o.get("station_id") for o in data["oceanic"])
            response += f"**Stations**: {len(stations)} coastal stations\n\n"

        # Show alerts
        if alert_count > 0:
            response += "## Active Weather Alerts\n\n"
            alert_types = {}
            for alert in data["alerts"][:10]:  # Show first 10 alerts
                event = alert.get("event", "Unknown")
                alert_types[event] = alert_types.get(event, 0) + 1

            for event, count in sorted(alert_types.items()):
                response += f"- **{event}**: {count} alert(s)\n"
            response += "\n"

        # Show buoy data
        if buoy_count > 0:
            response += "## Buoy Data\n\n"
            response += f"**Active Buoys**: {buoy_count} buoys reporting metadata\n\n"

        # Show climate data
        if climate_count > 0:
            response += "## Climate Records\n\n"
            response += (
                f"**Historical Data**: {climate_count} climate records available\n\n"
            )

        # Show terrestrial data
        if terrestrial_count > 0:
            response += "## River/Stream Data\n\n"
            response += (
                f"**Stations**: {terrestrial_count} terrestrial monitoring stations\n\n"
            )

        # Data summary
        response += "## Data Sources\n\n"
        ponds_queried = data.get("metadata", {}).get("ponds_queried", [])
        sources = data.get("metadata", {}).get("sources", [])

        for pond in ponds_queried:
            count = len(data.get(pond, []))
            response += f"- **{pond.capitalize()}**: {count} records\n"

        response += f"\n**Total Records**: {total_count} from {len(ponds_queried)} data pond(s)\n"
        response += f"**Sources**: {', '.join(set(sources))}\n"

        if total_count == 0:
            return (
                f"# Analysis: {query}\n\nNo data currently available. Please try again."
            )

        return response


def lambda_handler(event, context):
    """Main handler"""

    start_time = time.time()
    query_id = str(uuid.uuid4())

    try:
        # Parse request
        if isinstance(event, dict):
            if "body" in event:
                body = (
                    json.loads(event["body"])
                    if isinstance(event["body"], str)
                    else event["body"]
                )
            else:
                body = event
        else:
            body = json.loads(event)

        query = body.get("query", "")

        if not query:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,cache-control,pragma",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
                "body": json.dumps({"error": "Query parameter required"}),
            }

        logger.info(f"[{query_id}] Query: {query}")

        # Step 1: Understand what user wants
        understanding = understand_query_with_ai(query)
        logger.info(
            f"[{query_id}] Intent: {understanding.get('intent')}, Locations: {understanding.get('locations')}"
        )

        # Step 2: Fetch real data from S3 data lake
        data = fetch_real_data(understanding)
        total_records = data.get("metadata", {}).get("record_count", 0)
        ponds_queried = data.get("metadata", {}).get("ponds_queried", [])
        logger.info(
            f"[{query_id}] Retrieved {total_records} records from ponds: {', '.join(ponds_queried)}"
        )

        # Step 3: Let AI synthesize answer dynamically
        answer = synthesize_with_ai(query, understanding, data)

        execution_time = int((time.time() - start_time) * 1000)

        # Build response
        response_body = {
            "query_id": query_id,
            "query": query,
            "answer": answer,
            "ponds_queried": [
                {
                    "pond": pond,
                    "records_found": len(data.get(pond, [])),
                    "relevance_score": 0.9 if len(data.get(pond, [])) > 0 else 0,
                }
                for pond in ["atmospheric", "oceanic", "buoy", "climate", "terrestrial"]
                if len(data.get(pond, [])) > 0
            ],
            "total_records": total_records,
            "execution_time_ms": execution_time,
            "timestamp": datetime.utcnow().isoformat(),
            "query_intent": understanding.get("intent"),
            "ai_powered": True,
        }

        logger.info(f"[{query_id}] ✓ Complete in {execution_time}ms")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,cache-control,pragma",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "body": json.dumps(response_body),
        }

    except Exception as e:
        logger.error(f"[{query_id}] Error: {e}", exc_info=True)

        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,cache-control,pragma",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "body": json.dumps(
                {
                    "error": str(e),
                    "query_id": query_id,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }
            ),
        }
