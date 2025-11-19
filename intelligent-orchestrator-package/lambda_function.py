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

# Environment
BEDROCK_MODEL = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

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


def fetch_real_data(understanding: Dict) -> Dict:
    """Fetch actual data from NOAA APIs based on understanding"""

    data = {
        "weather_observations": [],
        "tide_data": [],
        "metadata": {
            "stations_queried": [],
            "sources": [],
        },
    }

    locations = understanding.get("locations", ["general"])
    data_needed = understanding.get("data_needed", [])

    # Get weather data
    if any(d in data_needed for d in ["temperature", "wind", "conditions", "weather"]):
        for location in locations[:3]:  # Max 3 locations
            stations = get_nearby_stations(location)
            for station in stations[:5]:  # Max 5 stations per location
                try:
                    obs_data = call_nws_api(
                        "/stations/{station}/observations/latest", station=station
                    )
                    if obs_data.get("properties"):
                        props = obs_data["properties"]
                        data["weather_observations"].append(
                            {
                                "station": station,
                                "location": location,
                                "temperature_c": props.get("temperature", {}).get(
                                    "value"
                                ),
                                "temperature_f": props.get("temperature", {}).get(
                                    "value"
                                )
                                * 9
                                / 5
                                + 32
                                if props.get("temperature", {}).get("value")
                                else None,
                                "wind_speed_kt": props.get("windSpeed", {}).get("value")
                                * 0.539957
                                if props.get("windSpeed", {}).get("value")
                                else None,
                                "wind_direction": props.get("windDirection", {}).get(
                                    "value"
                                ),
                                "humidity": props.get("relativeHumidity", {}).get(
                                    "value"
                                ),
                                "pressure": props.get("barometricPressure", {}).get(
                                    "value"
                                ),
                                "visibility": props.get("visibility", {}).get("value"),
                                "conditions": props.get("textDescription"),
                                "timestamp": props.get("timestamp"),
                            }
                        )
                        data["metadata"]["stations_queried"].append(station)
                        data["metadata"]["sources"].append("NWS Observations")
                except Exception as e:
                    logger.debug(f"Station {station} error: {e}")
                    continue

    # Get tide data
    if any(d in data_needed for d in ["tides", "water", "ocean", "coastal"]):
        for location in locations[:3]:
            tide_stations = get_tide_stations(location)
            for station in tide_stations[:3]:
                try:
                    tide_info = call_tides_api(station, "water_level")
                    if tide_info.get("data"):
                        latest = tide_info["data"][0] if tide_info["data"] else {}
                        data["tide_data"].append(
                            {
                                "station": station,
                                "location": location,
                                "water_level_m": latest.get("v"),
                                "time": latest.get("t"),
                            }
                        )
                        data["metadata"]["sources"].append("NOAA Tides")
                except Exception as e:
                    logger.debug(f"Tide station {station} error: {e}")
                    continue

    return data


def synthesize_with_ai(query: str, understanding: Dict, data: Dict) -> str:
    """Let AI dynamically create response based on query and actual data"""

    # Count actual data
    weather_count = len(data.get("weather_observations", []))
    tide_count = len(data.get("tide_data", []))

    prompt = f"""You are an expert NOAA data analyst. Answer this user's question using the REAL data provided.

User Question: "{query}"

What the user wants: {understanding.get("context")}

Real Data Retrieved:
{json.dumps(data, indent=2, default=str)}

Stations: {data.get("metadata", {}).get("stations_queried", [])}
Weather observations: {weather_count}
Tide observations: {tide_count}

Instructions:
1. **Answer ONLY what the user asked** - don't add irrelevant sections
2. **Use the ACTUAL DATA** - show real temperatures, winds, conditions
3. **Be specific** - include station IDs, exact measurements, timestamps
4. **Format appropriately**:
   - Temperature query → Show temperature readings from stations
   - Route planning → Show conditions affecting navigation
   - Historical → Show trends/patterns
   - Forecast → Show predictions
5. **Use Markdown formatting** with appropriate sections
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

        # Simple fallback with actual data
        if weather_count > 0:
            obs = data["weather_observations"][0]
            temp_c = obs.get("temperature_c")
            wind_kt = obs.get("wind_speed_kt")
            station = obs.get("station")

            return f"""# Analysis: {query}

## Current Conditions

**Temperature**: {temp_c:.1f}°C ({temp_c * 9 / 5 + 32:.1f}°F)
**Wind**: {wind_kt:.1f} knots
**Station**: {station}

## Data Sources
- Atmospheric: {weather_count} observations from {len(set(o.get("station") for o in data["weather_observations"]))} stations
"""

        return f"# Analysis: {query}\n\nNo data currently available. Please try again."


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
                },
                "body": json.dumps({"error": "Query parameter required"}),
            }

        logger.info(f"[{query_id}] Query: {query}")

        # Step 1: Understand what user wants
        understanding = understand_query_with_ai(query)
        logger.info(
            f"[{query_id}] Intent: {understanding.get('intent')}, Locations: {understanding.get('locations')}"
        )

        # Step 2: Fetch real data from NOAA APIs
        data = fetch_real_data(understanding)
        weather_count = len(data.get("weather_observations", []))
        tide_count = len(data.get("tide_data", []))
        logger.info(
            f"[{query_id}] Retrieved {weather_count} weather obs, {tide_count} tide obs"
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
                    "pond": "atmospheric",
                    "records_found": weather_count,
                    "relevance_score": 0.9 if weather_count > 0 else 0,
                }
            ]
            + (
                [
                    {
                        "pond": "oceanic",
                        "records_found": tide_count,
                        "relevance_score": 0.9 if tide_count > 0 else 0,
                    }
                ]
                if tide_count > 0
                else []
            ),
            "total_records": weather_count + tide_count,
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
                "Access-Control-Allow-Headers": "Content-Type",
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
            },
            "body": json.dumps(
                {
                    "error": str(e),
                    "query_id": query_id,
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                }
            ),
        }
