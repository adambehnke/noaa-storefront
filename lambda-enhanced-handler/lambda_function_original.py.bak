#!/usr/bin/env python3
"""
Intelligent Multi-Pond Query Handler for NOAA Federated Data Lake
Uses Amazon Bedrock (Claude) to semantically understand queries and route to relevant data ponds

Author: NOAA Federated Data Lake Team
Version: 3.0 - AI-Driven Pond Selection
"""

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
athena = boto3.client("athena", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")
s3_client = boto3.client("s3", region_name="us-east-1")

# Environment Variables
GOLD_DB = os.environ.get("GOLD_DB", "noaa_gold_dev")
ATHENA_OUTPUT = os.environ.get(
    "ATHENA_OUTPUT", "s3://noaa-athena-results-899626030376-dev/"
)
BEDROCK_MODEL = os.environ.get(
    "BEDROCK_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
)
ENV = os.environ.get("ENV", "dev")
ENHANCED_HANDLER = f"noaa-enhanced-handler-{ENV}"
S3_BUCKET = os.environ.get("S3_BUCKET", "noaa-federated-lake-899626030376-dev")

# Configuration
RELEVANCE_THRESHOLD = 0.3
MAX_PARALLEL_PONDS = 6
QUERY_TIMEOUT = 25.0

# =============================================================================
# POND METADATA REGISTRY - The AI uses this to understand what each pond contains
# =============================================================================

POND_METADATA = {
    "atmospheric": {
        "name": "Atmospheric Pond",
        "description": "Weather observations, forecasts, alerts, and warnings from NOAA National Weather Service",
        "data_types": [
            "current weather conditions",
            "temperature (air)",
            "wind speed and direction",
            "humidity and pressure",
            "visibility",
            "precipitation",
            "weather forecasts (7-day)",
            "severe weather alerts",
            "weather warnings",
            "storm predictions",
            "atmospheric advisories",
        ],
        "geographic_coverage": "United States, territories, coastal waters",
        "update_frequency": "Real-time (5-15 minute updates)",
        "relevance_keywords": [
            "weather",
            "temperature",
            "wind",
            "rain",
            "snow",
            "forecast",
            "alert",
            "warning",
            "storm",
            "atmospheric",
            "air",
            "visibility",
            "conditions",
            "advisory",
            "precipitation",
        ],
        "sample_use_cases": [
            "Current weather conditions in a city",
            "Weather forecasts for trip planning",
            "Active weather warnings and alerts",
            "Storm predictions and advisories",
        ],
    },
    "oceanic": {
        "name": "Oceanic Pond",
        "description": "Ocean and coastal data from NOAA CO-OPS including tides, water levels, temperatures, and currents",
        "data_types": [
            "water levels",
            "tide predictions and observations",
            "water temperature",
            "ocean currents",
            "sea surface temperature",
            "storm surge predictions",
            "coastal flooding risk",
            "high tide times",
        ],
        "geographic_coverage": "US coastal waters, bays, harbors, major rivers",
        "update_frequency": "Real-time (6-minute intervals)",
        "relevance_keywords": [
            "tide",
            "water",
            "ocean",
            "sea",
            "coastal",
            "marine",
            "current",
            "surge",
            "flooding",
            "water level",
            "water temperature",
            "high tide",
            "low tide",
            "sea level",
        ],
        "sample_use_cases": [
            "Tide predictions for fishing or boating",
            "Water temperature for swimming",
            "Storm surge predictions",
            "Coastal flooding risk assessment",
            "Ocean currents for navigation",
        ],
    },
    "buoy": {
        "name": "Buoy Pond",
        "description": "Offshore marine observations from NOAA buoys including waves, winds, and ocean conditions",
        "data_types": [
            "wave height and period",
            "wave direction",
            "offshore wind speed",
            "offshore wind direction",
            "sea surface temperature",
            "air temperature (offshore)",
            "barometric pressure",
            "water depth",
        ],
        "geographic_coverage": "Offshore waters, continental shelf, open ocean",
        "update_frequency": "Hourly observations",
        "relevance_keywords": [
            "wave",
            "buoy",
            "offshore",
            "swell",
            "marine",
            "sea state",
            "wave height",
            "maritime",
            "navigation",
            "boating",
            "sailing",
            "fishing",
        ],
        "sample_use_cases": [
            "Wave conditions for boating safety",
            "Offshore weather for maritime navigation",
            "Fishing conditions in offshore waters",
            "Sailing route planning",
        ],
    },
    "climate": {
        "name": "Climate Pond",
        "description": "Historical climate data, trends, and patterns from NOAA NCEI",
        "data_types": [
            "historical temperature records",
            "precipitation history",
            "climate trends",
            "seasonal patterns",
            "climate normals",
            "historical extremes",
            "long-term averages",
            "climate change indicators",
        ],
        "geographic_coverage": "United States, global datasets available",
        "update_frequency": "Monthly updates",
        "relevance_keywords": [
            "historical",
            "past",
            "history",
            "trend",
            "pattern",
            "climate",
            "average",
            "normal",
            "record",
            "previous",
            "long-term",
            "seasonal",
            "monthly",
            "yearly",
        ],
        "sample_use_cases": [
            "Historical flooding patterns",
            "Temperature trends over time",
            "Seasonal weather patterns",
            "Climate change analysis",
            "Comparing current conditions to historical averages",
        ],
    },
    "spatial": {
        "name": "Spatial Pond",
        "description": "Geographic and location-based data for route planning and distance calculations",
        "data_types": [
            "geographic coordinates",
            "coastal features",
            "navigation waypoints",
            "distance calculations",
            "route optimization",
            "geographic boundaries",
        ],
        "geographic_coverage": "United States and coastal waters",
        "update_frequency": "Static/reference data",
        "relevance_keywords": [
            "route",
            "from",
            "to",
            "between",
            "distance",
            "navigation",
            "path",
            "waypoint",
            "location",
            "geography",
        ],
        "sample_use_cases": [
            "Maritime route planning",
            "Distance calculations",
            "Navigation waypoints",
            "Geographic analysis",
        ],
    },
}


# =============================================================================
# METADATA COLLECTION
# =============================================================================


def collect_pond_metadata_dynamic(pond_name=None):
    """
    Dynamically collect fresh metadata from S3 for data ponds
    Returns current file counts, sizes, and freshness
    """
    logger.info(f"Collecting fresh metadata for ponds: {pond_name or 'all'}")

    ponds_to_check = (
        [pond_name]
        if pond_name
        else ["atmospheric", "oceanic", "buoy", "climate", "spatial", "terrestrial"]
    )
    layers = ["bronze", "silver", "gold"]

    metadata = {
        "collection_timestamp": datetime.utcnow().isoformat(),
        "bucket": S3_BUCKET,
        "ponds": {},
    }

    for pond in ponds_to_check:
        pond_data = {
            "pond_name": pond,
            "layers": {},
            "total_files": 0,
            "total_size_mb": 0,
            "latest_ingestion": None,
            "freshness_minutes": None,
            "status": "checking",
        }

        all_timestamps = []

        for layer in layers:
            prefix = f"{layer}/{pond}/"
            layer_stats = {"file_count": 0, "size_mb": 0, "latest_file": None}

            try:
                paginator = s3_client.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(
                    Bucket=S3_BUCKET,
                    Prefix=prefix,
                    PaginationConfig={"MaxItems": 1000},  # Limit for speed
                )

                for page in page_iterator:
                    if "Contents" not in page:
                        continue

                    for obj in page["Contents"]:
                        if obj["Key"].endswith("/"):
                            continue

                        layer_stats["file_count"] += 1
                        layer_stats["size_mb"] += obj["Size"] / (1024 * 1024)
                        all_timestamps.append(obj["LastModified"])

                if all_timestamps:
                    latest = max(all_timestamps)
                    layer_stats["latest_file"] = latest.isoformat()

                pond_data["layers"][layer] = layer_stats
                pond_data["total_files"] += layer_stats["file_count"]
                pond_data["total_size_mb"] += layer_stats["size_mb"]

            except Exception as e:
                logger.error(f"Error checking {layer}/{pond}: {e}")
                layer_stats["error"] = str(e)

        # Calculate freshness
        if all_timestamps:
            latest = max(all_timestamps)
            pond_data["latest_ingestion"] = latest.isoformat()

            now = datetime.now(timezone.utc)
            freshness_minutes = int((now - latest).total_seconds() / 60)
            pond_data["freshness_minutes"] = freshness_minutes

            if freshness_minutes < 30:
                pond_data["freshness_status"] = "excellent"
            elif freshness_minutes < 120:
                pond_data["freshness_status"] = "good"
            elif freshness_minutes < 360:
                pond_data["freshness_status"] = "moderate"
            else:
                pond_data["freshness_status"] = "stale"

            pond_data["status"] = "active"
        else:
            pond_data["status"] = "empty"
            pond_data["freshness_status"] = "no_data"

        pond_data["total_size_mb"] = round(pond_data["total_size_mb"], 2)
        pond_data["total_size_gb"] = round(pond_data["total_size_mb"] / 1024, 2)

        metadata["ponds"][pond] = pond_data

    # Calculate summary
    metadata["summary"] = {
        "total_ponds": len(ponds_to_check),
        "active_ponds": sum(
            1 for p in metadata["ponds"].values() if p["status"] == "active"
        ),
        "total_files": sum(p["total_files"] for p in metadata["ponds"].values()),
        "total_size_mb": round(
            sum(p["total_size_mb"] for p in metadata["ponds"].values()), 2
        ),
        "total_size_gb": round(
            sum(p.get("total_size_gb", 0) for p in metadata["ponds"].values()), 2
        ),
    }

    return metadata


# =============================================================================
# MAIN LAMBDA HANDLER
# =============================================================================


def lambda_handler(event, context):
    """
    Main entry point for AI-powered multi-pond queries
    """
    start_time = time.time()

    try:
        # Parse request
        if isinstance(event, str):
            event = json.loads(event)

        body = event.get("body")
        if body and isinstance(body, str):
            body = json.loads(body)
        else:
            body = event

        query = body.get("query") or body.get("question")
        include_raw_data = body.get("include_raw_data", False)
        max_results_per_pond = body.get("max_results_per_pond", 50)

        # Check for metadata request
        action = body.get("action")
        if action == "get_metadata":
            logger.info("Metadata request received")
            pond_filter = body.get("pond")
            metadata = collect_pond_metadata_dynamic(pond_filter)
            return respond(
                200, {"success": True, "action": "metadata", "data": metadata}
            )

        if not query:
            return respond(400, {"error": "Missing 'query' parameter"})

        logger.info(f"Processing query: {query}")

        # Step 1: Use AI to understand the query semantically
        query_understanding = understand_query_with_ai(query)
        logger.info(f"Query understanding: {json.dumps(query_understanding, indent=2)}")

        # Step 2: Use AI to select relevant ponds with reasoning
        pond_selections = select_ponds_with_ai(query, query_understanding)
        logger.info(
            f"Selected {len(pond_selections)} ponds: {[p['pond_name'] for p in pond_selections]}"
        )

        # Step 3: Query all selected ponds in parallel
        pond_results = query_ponds_parallel(pond_selections, query, query_understanding)

        # Step 4: Use AI to synthesize results and explain relationships
        final_response = synthesize_results_with_ai(
            query=query,
            query_understanding=query_understanding,
            pond_selections=pond_selections,
            pond_results=pond_results,
            include_raw_data=include_raw_data,
        )

        # Add metadata
        execution_time_ms = int((time.time() - start_time) * 1000)
        final_response["metadata"] = {
            "execution_time_ms": execution_time_ms,
            "ponds_queried": len([r for r in pond_results if r.get("success")]),
            "ponds_considered": len(pond_selections),
            "total_records": sum(r.get("record_count", 0) for r in pond_results),
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Query completed in {execution_time_ms}ms")

        return respond(200, final_response)

    except Exception as e:
        logger.exception("Error processing query")
        return respond(
            500,
            {
                "error": str(e),
                "message": "An error occurred while processing your query",
            },
        )


# =============================================================================
# AI-POWERED QUERY UNDERSTANDING
# =============================================================================


def understand_query_with_ai(query: str) -> Dict:
    """
    Use Bedrock/Claude to semantically understand what the user is asking
    """

    prompt = f"""Analyze this user query about environmental/weather/ocean data:

Query: "{query}"

Provide a semantic understanding of what the user is asking. Consider:
1. What is the primary intent? (observation, forecast, historical, comparison, risk_assessment, route_planning, etc.)
2. What specific information are they seeking?
3. What geographic location(s) are involved?
4. What time frame is relevant? (current, forecast, historical, etc.)
5. What are the implicit requirements? (e.g., "safe route" implies need for weather, waves, currents, visibility)
6. Is this a simple factual question or complex multi-domain analysis?

Respond with JSON only:
{{
    "primary_intent": "observation|forecast|historical|comparison|risk_assessment|route_planning|conditions_check",
    "information_sought": ["specific data points needed"],
    "locations": ["location1", "location2"],
    "time_frame": "current|forecast|historical|specific_date",
    "implicit_requirements": ["things the user needs but didn't explicitly mention"],
    "complexity": "simple|moderate|complex|multi-domain",
    "question_type": "factual|analytical|comparative|predictive|planning"
}}"""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Extract JSON
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            understanding = json.loads(json_match.group())
            return understanding
        else:
            logger.warning("Could not parse AI understanding, using fallback")
            return get_fallback_understanding(query)

    except Exception as e:
        logger.error(f"Error in AI understanding: {e}")
        return get_fallback_understanding(query)


def get_fallback_understanding(query: str) -> Dict:
    """Fallback understanding if AI fails"""
    query_lower = query.lower()

    # Simple heuristics
    intent = "observation"
    if any(
        w in query_lower for w in ["forecast", "will", "future", "tomorrow", "next"]
    ):
        intent = "forecast"
    elif any(
        w in query_lower for w in ["historical", "past", "was", "previous", "history"]
    ):
        intent = "historical"
    elif any(w in query_lower for w in ["route", "from", "to", "plan", "navigate"]):
        intent = "route_planning"
    elif any(w in query_lower for w in ["risk", "safe", "danger", "flooding"]):
        intent = "risk_assessment"

    return {
        "primary_intent": intent,
        "information_sought": ["general information"],
        "locations": ["location from query"],
        "time_frame": "current",
        "implicit_requirements": [],
        "complexity": "moderate",
        "question_type": "factual",
    }


# =============================================================================
# AI-POWERED POND SELECTION
# =============================================================================


def select_ponds_with_ai(query: str, understanding: Dict) -> List[Dict]:
    """
    Use Bedrock/Claude to intelligently determine which ponds are relevant
    """

    # Build pond descriptions for AI
    ponds_description = ""
    for pond_name, metadata in POND_METADATA.items():
        ponds_description += f"""
POND: {metadata["name"]} ({pond_name})
Description: {metadata["description"]}
Data Types: {", ".join(metadata["data_types"])}
Geographic Coverage: {metadata["geographic_coverage"]}
Update Frequency: {metadata["update_frequency"]}
Sample Use Cases:
{chr(10).join(f"  - {uc}" for uc in metadata["sample_use_cases"])}
---
"""

    prompt = f"""You are a data analyst for NOAA's Federated Data Lake. A user has asked a question and you need to determine which data ponds to query.

USER QUERY: "{query}"

QUERY ANALYSIS:
{json.dumps(understanding, indent=2)}

AVAILABLE DATA PONDS:
{ponds_description}

Your task: Determine which ponds should be queried and why. Be thorough - consider ALL ponds that might contribute relevant information.

SCORING GUIDELINES:
- 0.95-1.0: CRITICAL - Essential data, query cannot be properly answered without this pond
- 0.80-0.94: PRIMARY - Major data source for this query
- 0.60-0.79: IMPORTANT - Significant supporting data
- 0.40-0.59: RELEVANT - Provides useful context or supporting information
- 0.30-0.39: SUPPORTING - Minor supporting data, helps complete the picture
- Below 0.30: Not relevant (omit from response)

EXAMPLES:
- "What's the weather in Boston?" → atmospheric (1.0)
- "Plan a route from Boston to Portland" → atmospheric (0.90), oceanic (0.90), buoy (0.85), spatial (0.80)
- "Coastal flooding risk in Charleston considering storm surge, tides, rainfall, and historical patterns" → atmospheric (0.95), oceanic (0.95), climate (0.85)
- "Sailing conditions in San Francisco Bay" → atmospheric (0.90), oceanic (0.85), buoy (0.80)

For EACH relevant pond (score ≥ 0.30), provide:
{{
    "pond_name": "pond_identifier",
    "relevance_score": 0.30-1.0,
    "reasoning": "Specific explanation of why THIS pond matters for THIS query",
    "data_contribution": "What specific information this pond provides to answer the query",
    "priority": "critical|high|medium|low"
}}

Respond with a JSON array ordered by relevance_score (highest first). Include ALL ponds with score ≥ 0.30.
JSON array only, no other text."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2500,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Extract JSON array
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            selections = json.loads(json_match.group())
            # Filter by threshold and validate
            valid_selections = [
                s
                for s in selections
                if s.get("relevance_score", 0) >= RELEVANCE_THRESHOLD
                and s.get("pond_name") in POND_METADATA
            ]

            logger.info(
                f"AI selected {len(valid_selections)} ponds with scores: {[(s['pond_name'], s['relevance_score']) for s in valid_selections]}"
            )

            return valid_selections
        else:
            logger.warning("Could not parse pond selections, using fallback")
            return get_fallback_pond_selection(query, understanding)

    except Exception as e:
        logger.error(f"Error in pond selection: {e}")
        return get_fallback_pond_selection(query, understanding)


def get_fallback_pond_selection(query: str, understanding: Dict) -> List[Dict]:
    """Fallback pond selection using simple heuristics"""
    query_lower = query.lower()
    selections = []

    # Route planning queries need multiple ponds
    if understanding.get("primary_intent") == "route_planning":
        selections.extend(
            [
                {
                    "pond_name": "atmospheric",
                    "relevance_score": 0.90,
                    "reasoning": "Weather conditions along route",
                    "data_contribution": "Wind, visibility, storms",
                    "priority": "critical",
                },
                {
                    "pond_name": "oceanic",
                    "relevance_score": 0.90,
                    "reasoning": "Ocean conditions and currents",
                    "data_contribution": "Currents, water levels, tides",
                    "priority": "critical",
                },
                {
                    "pond_name": "buoy",
                    "relevance_score": 0.85,
                    "reasoning": "Offshore wave conditions",
                    "data_contribution": "Wave heights, sea state",
                    "priority": "high",
                },
            ]
        )

    # Flooding/risk queries need multiple ponds
    elif (
        understanding.get("primary_intent") == "risk_assessment"
        or "flood" in query_lower
    ):
        selections.extend(
            [
                {
                    "pond_name": "atmospheric",
                    "relevance_score": 0.95,
                    "reasoning": "Weather and storm data",
                    "data_contribution": "Rainfall, storm predictions",
                    "priority": "critical",
                },
                {
                    "pond_name": "oceanic",
                    "relevance_score": 0.95,
                    "reasoning": "Coastal water levels and surge",
                    "data_contribution": "Storm surge, high tide times",
                    "priority": "critical",
                },
                {
                    "pond_name": "climate",
                    "relevance_score": 0.80,
                    "reasoning": "Historical flooding patterns",
                    "data_contribution": "Past flooding events",
                    "priority": "high",
                },
            ]
        )

    # Marine/ocean queries
    elif any(
        w in query_lower for w in ["ocean", "tide", "water", "marine", "coastal", "sea"]
    ):
        selections.extend(
            [
                {
                    "pond_name": "oceanic",
                    "relevance_score": 0.95,
                    "reasoning": "Primary ocean data source",
                    "data_contribution": "Tides, water temp, currents",
                    "priority": "critical",
                },
                {
                    "pond_name": "atmospheric",
                    "relevance_score": 0.70,
                    "reasoning": "Weather affects ocean conditions",
                    "data_contribution": "Marine weather",
                    "priority": "medium",
                },
            ]
        )

    # Weather queries
    elif any(w in query_lower for w in ["weather", "temperature", "wind", "forecast"]):
        selections.append(
            {
                "pond_name": "atmospheric",
                "relevance_score": 0.95,
                "reasoning": "Primary weather data source",
                "data_contribution": "Weather conditions",
                "priority": "critical",
            }
        )

    # Default to atmospheric if nothing matches
    if not selections:
        selections.append(
            {
                "pond_name": "atmospheric",
                "relevance_score": 0.60,
                "reasoning": "Default general weather data",
                "data_contribution": "General conditions",
                "priority": "medium",
            }
        )

    return selections


# =============================================================================
# PARALLEL POND QUERYING
# =============================================================================


def query_ponds_parallel(
    pond_selections: List[Dict], query: str, understanding: Dict
) -> List[Dict]:
    """
    Query multiple ponds in parallel using ThreadPoolExecutor
    """
    results = []

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_PONDS) as executor:
        future_to_pond = {
            executor.submit(
                query_single_pond, selection, query, understanding
            ): selection
            for selection in pond_selections
        }

        for future in as_completed(future_to_pond, timeout=QUERY_TIMEOUT):
            pond_selection = future_to_pond[future]
            try:
                result = future.result(timeout=5.0)
                results.append(result)
            except Exception as e:
                logger.error(f"Error querying {pond_selection['pond_name']}: {e}")
                results.append(
                    {
                        "pond_name": pond_selection["pond_name"],
                        "success": False,
                        "error": str(e),
                        "record_count": 0,
                    }
                )

    return results


def query_single_pond(selection: Dict, query: str, understanding: Dict) -> Dict:
    """
    Query a single pond (both Gold layer and passthrough APIs)
    """
    pond_name = selection["pond_name"]
    start_time = time.time()

    logger.info(f"Querying {pond_name} pond...")

    try:
        # Try Gold layer first
        gold_results = query_gold_layer(pond_name, understanding)

        # Also try passthrough API for real-time data
        passthrough_results = query_passthrough(pond_name, query, understanding)

        # Combine results
        combined_data = []
        if gold_results.get("success"):
            combined_data.extend(gold_results.get("data", []))
        if passthrough_results.get("success"):
            combined_data.extend(passthrough_results.get("data", []))

        execution_time = int((time.time() - start_time) * 1000)

        return {
            "pond_name": pond_name,
            "success": True,
            "record_count": len(combined_data),
            "data": combined_data,
            "sources": {
                "gold_layer": gold_results.get("success", False),
                "passthrough_api": passthrough_results.get("success", False),
            },
            "execution_time_ms": execution_time,
            "relevance_score": selection["relevance_score"],
            "reasoning": selection["reasoning"],
        }

    except Exception as e:
        logger.error(f"Error querying {pond_name}: {e}")
        return {
            "pond_name": pond_name,
            "success": False,
            "error": str(e),
            "record_count": 0,
        }


def query_gold_layer(pond_name: str, understanding: Dict) -> Dict:
    """Query the Gold layer via Athena"""
    try:
        # Determine which table to query based on pond
        table_map = {
            "atmospheric": "atmospheric_aggregated",
            "oceanic": "oceanic_aggregated",
            "buoy": "buoy_aggregated",
            "climate": "climate_aggregated",
        }

        table = table_map.get(pond_name)
        if not table:
            return {"success": False, "error": "No Gold table for this pond"}

        # Simple query to get recent data
        sql = f"""
        SELECT * FROM {GOLD_DB}.{table}
        ORDER BY date DESC
        LIMIT 10
        """

        # Execute Athena query
        response = athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": GOLD_DB},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        )

        query_id = response["QueryExecutionId"]

        # Wait for completion (with timeout)
        max_wait = 10
        waited = 0
        while waited < max_wait:
            status = athena.get_query_execution(QueryExecutionId=query_id)
            state = status["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break
            elif state in ["FAILED", "CANCELLED"]:
                return {"success": False, "error": f"Query {state}"}

            time.sleep(1)
            waited += 1

        if waited >= max_wait:
            return {"success": False, "error": "Query timeout"}

        # Get results
        results = athena.get_query_results(QueryExecutionId=query_id)

        # Parse results
        data = []
        if len(results["ResultSet"]["Rows"]) > 1:
            headers = [
                col["VarCharValue"] for col in results["ResultSet"]["Rows"][0]["Data"]
            ]
            for row in results["ResultSet"]["Rows"][1:]:
                row_data = {
                    headers[i]: col.get("VarCharValue", "")
                    for i, col in enumerate(row["Data"])
                }
                data.append(row_data)

        return {"success": True, "data": data, "source": "gold_layer"}

    except Exception as e:
        logger.warning(f"Gold layer query failed for {pond_name}: {e}")
        return {"success": False, "error": str(e)}


def query_passthrough(pond_name: str, query: str, understanding: Dict) -> Dict:
    """Query real-time passthrough APIs via enhanced handler"""
    try:
        # Call the enhanced handler Lambda which has passthrough API logic
        response = lambda_client.invoke(
            FunctionName=ENHANCED_HANDLER,
            InvocationType="RequestResponse",
            Payload=json.dumps({"query": query, "pond_filter": pond_name}),
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            body = json.loads(result.get("body", "{}"))
            return {
                "success": True,
                "data": [body.get("data", {})],
                "source": "passthrough_api",
            }
        else:
            return {"success": False, "error": "Passthrough failed"}

    except Exception as e:
        logger.warning(f"Passthrough query failed for {pond_name}: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# AI-POWERED RESULT SYNTHESIS
# =============================================================================


def synthesize_results_with_ai(
    query: str,
    query_understanding: Dict,
    pond_selections: List[Dict],
    pond_results: List[Dict],
    include_raw_data: bool,
) -> Dict:
    """
    Use Bedrock/Claude to synthesize results and explain data relationships
    """

    # Build context about what we queried and found
    ponds_queried = []
    for selection in pond_selections:
        pond_name = selection["pond_name"]
        result = next((r for r in pond_results if r["pond_name"] == pond_name), None)

        ponds_queried.append(
            {
                "pond": POND_METADATA[pond_name]["name"],
                "relevance_score": selection["relevance_score"],
                "why_relevant": selection["reasoning"],
                "data_contribution": selection["data_contribution"],
                "records_found": result.get("record_count", 0) if result else 0,
                "success": result.get("success", False) if result else False,
            }
        )

    # Prepare data summary (not full data, too large for prompt)
    data_summary = []
    for result in pond_results:
        if result.get("success") and result.get("record_count", 0) > 0:
            data_summary.append(
                {
                    "pond": result["pond_name"],
                    "record_count": result["record_count"],
                    "sample": result["data"][0] if result["data"] else None,
                }
            )

    prompt = f"""You are answering a user's question about environmental/weather/ocean data using NOAA's Federated Data Lake.

USER QUERY: "{query}"

PONDS QUERIED AND WHY:
{json.dumps(ponds_queried, indent=2)}

DATA FOUND:
{json.dumps(data_summary, indent=2)}

Your task:
1. Answer the user's question directly and comprehensively
2. Explain which data ponds were queried and WHY they're relevant to this specific question
3. Explain HOW the data from different ponds relates to each other for this query
4. If some ponds returned no data, note that and explain what it means
5. Provide insights by correlating data across ponds

Format your response as:

## Answer to Your Question
[Direct answer to what they asked]

## Data Sources Consulted
[Explain which ponds were queried and why each is relevant to THIS question]

## How the Data Relates
[Explain the relationships between data from different ponds and why we need multiple sources for this query]

## Insights
[Key takeaways from analyzing the data across ponds]

If data is incomplete or unavailable, explain that clearly and suggest alternatives.

Use clear, helpful language. Be specific about what data came from which pond."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
            ),
        )

        result = json.loads(response["body"].read())
        answer = result["content"][0]["text"]

        # Build final response
        final_response = {
            "success": True,
            "query": query,
            "answer": answer,
            "ponds_queried": ponds_queried,
            "total_records": sum(r.get("record_count", 0) for r in pond_results),
        }

        if include_raw_data:
            final_response["raw_data"] = {
                r["pond_name"]: r.get("data", [])
                for r in pond_results
                if r.get("success")
            }

        return final_response

    except Exception as e:
        logger.error(f"Error synthesizing results: {e}")

        # Intelligent fallback - format actual data
        answer_parts = [f"# Analysis: {query}\n\n"]
        total_records = sum(r.get("record_count", 0) for r in pond_results)

        # Process each pond's data
        for result in pond_results:
            if not result.get("success") or not result.get("data"):
                continue

            pond_name = result.get("pond_name", "Unknown")
            data = result.get("data", [])

            if pond_name == "atmospheric" and data:
                answer_parts.append("## Weather Conditions\n\n")
                # Show actual alert/forecast data
                for record in data[:5]:
                    if record.get("event_type"):
                        answer_parts.append(
                            f"- **{record.get('event_type')}** ({record.get('region', 'Unknown')}): {record.get('severity', 'Unknown')} severity\n"
                        )
                answer_parts.append(f"\nTotal atmospheric records: {len(data)}\n\n")

            elif pond_name == "oceanic" and data:
                answer_parts.append("## Ocean Conditions\n\n")
                # Show actual tide/water data
                for record in data[:5]:
                    station = record.get(
                        "station_name", record.get("station_id", "Unknown")
                    )
                    if record.get("avg_water_temp"):
                        answer_parts.append(
                            f"- **{station}**: Water temp {record.get('avg_water_temp')}°C, "
                        )
                    if record.get("avg_water_level"):
                        answer_parts.append(
                            f"Water level {record.get('avg_water_level')}m\n"
                        )
                    else:
                        answer_parts.append("\n")
                answer_parts.append(f"\nTotal oceanic records: {len(data)}\n\n")

            elif pond_name == "buoy" and data:
                answer_parts.append("## Marine Conditions\n\n")
                # Show actual buoy data
                for record in data[:5]:
                    buoy = record.get("buoy_id", "Unknown")
                    if record.get("wave_height"):
                        answer_parts.append(
                            f"- **Buoy {buoy}**: Wave height {record.get('wave_height')}m\n"
                        )
                answer_parts.append(f"\nTotal buoy records: {len(data)}\n\n")

            elif pond_name == "climate" and data:
                answer_parts.append("## Climate Data\n\n")
                answer_parts.append(f"Historical records available: {len(data)}\n\n")

        # Data sources summary
        answer_parts.append("## Data Sources\n")
        for result in pond_results:
            if result.get("success") and result.get("record_count", 0) > 0:
                pond = result.get("pond_name", "Unknown")
                count = result.get("record_count", 0)
                answer_parts.append(f"- **{pond}**: {count} records\n")

        answer_parts.append(
            f"\n*Total: {total_records} records from {len([r for r in pond_results if r.get('success')])} data sources*"
        )

        return {
            "success": True,
            "query": query,
            "answer": "".join(answer_parts),
            "ponds_queried": ponds_queried,
            "total_records": total_records,
            "raw_data": {
                r["pond_name"]: r.get("data", [])
                for r in pond_results
                if r.get("success")
            },
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def respond(status_code: int, body: Dict) -> Dict:
    """
    Format Lambda response for API Gateway
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,cache-control",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }
