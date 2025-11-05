#!/usr/bin/env python3
"""
AI-Powered Query Orchestrator for NOAA Federated Data Lake

This orchestrator:
1. Accepts plain English queries
2. Uses AI to determine which data pond(s) to query
3. Constructs appropriate SQL queries for each pond
4. Executes queries across multiple ponds
5. Normalizes and combines results using AI
6. Returns cohesive, unified response

Author: NOAA Federated Data Lake Team
"""

import json
import os
import boto3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
athena = boto3.client("athena")
s3_client = boto3.client("s3")

# Environment Variables
GOLD_DB = os.environ.get("GOLD_DB", "noaa_gold_dev")
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT")
BEDROCK_MODEL = os.environ.get(
    "BEDROCK_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
)
ENV = os.environ.get("ENV", "dev")

# Redis client (lazy loaded)
redis_client = None

# =============================================================================
# DATA POND CONFIGURATION
# =============================================================================

POND_METADATA = {
    "atmospheric": {
        "description": "Weather data including alerts, forecasts, observations, radar, and atmospheric conditions",
        "keywords": [
            "weather",
            "alert",
            "warning",
            "forecast",
            "temperature",
            "precipitation",
            "storm",
            "hurricane",
            "tornado",
            "wind",
            "rain",
            "snow",
            "pressure",
            "humidity",
            "radar",
        ],
        "tables": {
            "bronze": "atmospheric_raw",
            "silver": "atmospheric_cleaned",
            "gold": "atmospheric_aggregated",
        },
        "schema": {
            "gold": [
                "region",
                "event_type",
                "severity",
                "alert_count",
                "avg_certainty",
                "date",
            ]
        },
        "sample_queries": [
            "Show me weather alerts in California",
            "What's the temperature forecast?",
            "Are there any storm warnings?",
            "Recent severe weather events",
        ],
    },
    "oceanic": {
        "description": "Ocean and coastal data including tides, currents, water levels, water temperature, and marine conditions",
        "keywords": [
            "tide",
            "ocean",
            "sea",
            "water level",
            "current",
            "coastal",
            "marine",
            "tsunami",
            "wave",
            "salinity",
            "beach",
            "port",
            "harbor",
        ],
        "tables": {
            "bronze": "oceanic_raw",
            "silver": "oceanic_cleaned",
            "gold": "oceanic_aggregated",
        },
        "schema": {
            "gold": [
                "station_id",
                "region",
                "avg_water_level",
                "avg_water_temp",
                "date",
            ]
        },
        "sample_queries": [
            "What are the tide predictions?",
            "Show me water levels in San Francisco",
            "Ocean temperature trends",
            "Coastal flooding risk",
        ],
    },
    "terrestrial": {
        "description": "Land-based environmental data including soil moisture, vegetation, drought, and land surface conditions",
        "keywords": [
            "soil",
            "drought",
            "vegetation",
            "land",
            "agriculture",
            "crop",
            "wildfire",
            "groundwater",
            "erosion",
        ],
        "tables": {
            "bronze": "terrestrial_raw",
            "silver": "terrestrial_cleaned",
            "gold": "terrestrial_aggregated",
        },
        "schema": {
            "gold": [
                "region",
                "soil_moisture",
                "vegetation_index",
                "drought_level",
                "date",
            ]
        },
        "sample_queries": [
            "Drought conditions in Texas",
            "Soil moisture levels",
            "Wildfire risk assessment",
        ],
    },
    "spatial": {
        "description": "Geographic and spatial data including boundaries, locations, regions, and GIS layers",
        "keywords": [
            "location",
            "map",
            "boundary",
            "coordinate",
            "latitude",
            "longitude",
            "region",
            "zone",
            "area",
            "geographic",
        ],
        "tables": {
            "bronze": "spatial_raw",
            "silver": "spatial_cleaned",
            "gold": "spatial_aggregated",
        },
        "schema": {
            "gold": ["feature_id", "feature_type", "geometry", "properties", "date"]
        },
        "sample_queries": [
            "Show me warning zones",
            "Geographic extent of alerts",
            "Map boundaries",
        ],
    },
    "climate": {
        "description": "Long-term climate data including historical trends, normals, extremes, and climate indices",
        "keywords": [
            "climate",
            "historical",
            "trend",
            "average",
            "normal",
            "extreme",
            "record",
            "annual",
            "seasonal",
            "decade",
        ],
        "tables": {
            "bronze": "climate_raw",
            "silver": "climate_cleaned",
            "gold": "climate_aggregated",
        },
        "schema": {
            "gold": [
                "region",
                "year",
                "avg_temp",
                "total_precip",
                "climate_metric",
                "date",
            ]
        },
        "sample_queries": [
            "Historical temperature trends",
            "Climate normals for New York",
            "Extreme weather records",
        ],
    },
    "multitype": {
        "description": "Cross-domain queries combining multiple data types for comprehensive analysis",
        "keywords": [
            "combined",
            "integrated",
            "correlation",
            "relationship",
            "impact",
            "analysis",
            "comprehensive",
        ],
        "tables": {
            "bronze": "multitype_raw",
            "silver": "multitype_cleaned",
            "gold": "multitype_aggregated",
        },
        "schema": {"gold": ["entity_id", "data_type", "metric", "value", "date"]},
        "sample_queries": [
            "How do tides affect coastal weather?",
            "Correlation between ocean temp and hurricanes",
            "Integrated environmental conditions",
        ],
    },
}

# =============================================================================
# AI FUNCTIONS
# =============================================================================


def invoke_bedrock(
    prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 2000
) -> str:
    """
    Invoke Amazon Bedrock Claude model

    Args:
        prompt: User prompt
        system_prompt: Optional system context
        max_tokens: Maximum tokens to generate

    Returns:
        Model response text
    """
    try:
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": 0.3,
        }

        if system_prompt:
            body["system"] = system_prompt

        response = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=json.dumps(body))

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    except Exception as e:
        logger.error(f"Bedrock invocation error: {e}")
        raise


def determine_relevant_ponds(query: str) -> List[Dict[str, Any]]:
    """
    Use AI to determine which data pond(s) are relevant for the query

    Args:
        query: User's natural language query

    Returns:
        List of relevant ponds with confidence scores
    """

    pond_descriptions = "\n\n".join(
        [
            f"**{name}**:\n- Description: {meta['description']}\n- Keywords: {', '.join(meta['keywords'][:10])}\n- Examples: {', '.join(meta['sample_queries'][:2])}"
            for name, meta in POND_METADATA.items()
        ]
    )

    prompt = f"""Analyze this user query and determine which NOAA data pond(s) are relevant:

Query: "{query}"

Available Data Ponds:
{pond_descriptions}

Respond with ONLY a JSON array of relevant ponds, ordered by relevance. Include confidence score (0-1).
Format: [{{"pond": "pond_name", "confidence": 0.95, "reasoning": "brief explanation"}}, ...]

If multiple ponds are relevant, include all. If query spans multiple domains, mark as multitype.
"""

    try:
        response = invoke_bedrock(prompt, max_tokens=1000)

        # Extract JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()

        ponds = json.loads(response)

        # Validate ponds
        valid_ponds = []
        for pond in ponds:
            if pond.get("pond") in POND_METADATA:
                valid_ponds.append(pond)

        logger.info(f"Determined relevant ponds: {[p['pond'] for p in valid_ponds]}")
        return (
            valid_ponds
            if valid_ponds
            else [
                {
                    "pond": "atmospheric",
                    "confidence": 0.5,
                    "reasoning": "default fallback",
                }
            ]
        )

    except Exception as e:
        logger.error(f"Error determining ponds: {e}")
        return [
            {"pond": "atmospheric", "confidence": 0.5, "reasoning": "error fallback"}
        ]


def generate_sql_for_pond(query: str, pond_name: str, pond_metadata: Dict) -> str:
    """
    Generate SQL query for specific pond using AI

    Args:
        query: User's natural language query
        pond_name: Name of the data pond
        pond_metadata: Metadata for the pond

    Returns:
        SQL query string
    """

    schema_info = json.dumps(pond_metadata.get("schema", {}), indent=2)

    prompt = f"""Generate an optimized SQL query for Amazon Athena to answer this question:

Question: "{query}"

Data Pond: {pond_name}
Description: {pond_metadata["description"]}

Available Table: {GOLD_DB}.{pond_metadata["tables"]["gold"]}
Schema: {schema_info}

Requirements:
1. Query the Gold layer table (already aggregated and optimized)
2. Use date filters for performance (last 30 days unless specified)
3. Limit results to 100 unless user specifies otherwise
4. Include relevant WHERE clauses
5. Order by date DESC for time-series data
6. Use appropriate aggregations if needed
7. IMPORTANT: Use Athena/Presto SQL syntax ONLY:
   - For date arithmetic: date_add('day', -30, current_date) NOT DATE_SUB
   - For date literals: DATE '2025-01-01' NOT '2025-01-01'
   - Use current_date NOT CURRENT_DATE or NOW()

Return ONLY the SQL query, no explanation or markdown.
"""

    try:
        sql = invoke_bedrock(prompt, max_tokens=500)

        # Clean SQL
        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("```")[1]
            if sql.lower().startswith("sql"):
                sql = sql[3:]
        sql = sql.strip()

        # Remove trailing semicolon if present
        if sql.endswith(";"):
            sql = sql[:-1]

        logger.info(f"Generated SQL for {pond_name}: {sql[:100]}...")
        return sql

    except Exception as e:
        logger.error(f"Error generating SQL for {pond_name}: {e}")
        # Fallback query
        table = f"{GOLD_DB}.{pond_metadata['tables']['gold']}"
        return f"SELECT * FROM {table} WHERE date >= date_add('day', -30, current_date) ORDER BY date DESC LIMIT 100"


def execute_athena_query(sql: str, pond_name: str) -> List[Dict[str, Any]]:
    """
    Execute SQL query in Athena and return results

    Args:
        sql: SQL query string
        pond_name: Name of pond for logging

    Returns:
        List of result rows as dictionaries
    """
    try:
        logger.info(f"Executing query for {pond_name}")

        response = athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": GOLD_DB},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
            WorkGroup="primary",
        )

        query_id = response["QueryExecutionId"]

        # Wait for completion
        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_response = athena.get_query_execution(QueryExecutionId=query_id)
            state = status_response["QueryExecution"]["Status"]["State"]

            if state == "SUCCEEDED":
                break
            elif state in ["FAILED", "CANCELLED"]:
                reason = status_response["QueryExecution"]["Status"].get(
                    "StateChangeReason", "Unknown"
                )
                logger.error(f"Query failed for {pond_name}: {reason}")
                return []

            time.sleep(1)
        else:
            logger.warning(f"Query timeout for {pond_name}")
            return []

        # Get results
        result_response = athena.get_query_results(
            QueryExecutionId=query_id, MaxResults=1000
        )

        rows = result_response["ResultSet"]["Rows"]

        if not rows or len(rows) < 2:
            logger.info(
                f"No data found in Gold layer for {pond_name}, trying passthrough"
            )
            return try_passthrough(pond_name)

        # Parse results
        headers = [col.get("VarCharValue", "") for col in rows[0]["Data"]]

        results = []
        for row in rows[1:]:
            row_dict = {}
            for i, col in enumerate(row["Data"]):
                value = col.get("VarCharValue")
                row_dict[headers[i]] = value
            results.append(row_dict)

        logger.info(f"Retrieved {len(results)} rows from {pond_name}")
        return results

    except Exception as e:
        logger.error(f"Error executing query for {pond_name}: {e}")
        logger.info(f"Falling back to passthrough for {pond_name}")
        return try_passthrough(pond_name)


def try_passthrough(pond_name: str) -> List[Dict[str, Any]]:
    """
    Try to get data via passthrough Lambda when Gold layer is empty

    Args:
        pond_name: Name of the data pond

    Returns:
        List of results from passthrough API
    """
    try:
        lambda_client = boto3.client("lambda")

        # Map pond names to passthrough services
        service_mapping = {
            "atmospheric": {"service": "nws", "endpoint": "alerts/active"},
            "oceanic": {"service": "tides", "station": "9414290", "hours_back": "24"},
            "climate": {"service": "cdo", "dataset": "GHCND"},
        }

        if pond_name not in service_mapping:
            logger.warning(f"No passthrough mapping for pond: {pond_name}")
            return []

        params = service_mapping[pond_name]
        payload = {"queryStringParameters": params}

        logger.info(
            f"Invoking passthrough Lambda for {pond_name} with params: {params}"
        )

        response = lambda_client.invoke(
            FunctionName=f"noaa-passthrough-{ENV}",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            body = json.loads(result.get("body", "{}"))
            data = body.get("data", [])

            # Flatten the data structure for consistency
            if isinstance(data, list) and len(data) > 0:
                # Limit to 100 results to match Athena behavior
                limited_data = data[:100]
                logger.info(
                    f"Passthrough returned {len(limited_data)} records for {pond_name}"
                )
                return limited_data
            else:
                logger.warning(f"Passthrough returned no data for {pond_name}")
                return []
        else:
            logger.error(f"Passthrough failed with status {result.get('statusCode')}")
            return []

    except Exception as e:
        logger.error(f"Error in passthrough for {pond_name}: {e}")
        return []


def synthesize_results(
    query: str, pond_results: Dict[str, List[Dict]]
) -> Dict[str, Any]:
    """
    Use AI to synthesize results from multiple ponds into cohesive response

    Args:
        query: Original user query
        pond_results: Dictionary mapping pond names to their results

    Returns:
        Synthesized response with insights
    """

    # Prepare results summary
    results_summary = {}
    total_records = 0

    for pond_name, results in pond_results.items():
        if results:
            total_records += len(results)
            results_summary[pond_name] = {
                "count": len(results),
                "sample": results[:3] if len(results) > 3 else results,
                "fields": list(results[0].keys()) if results else [],
            }

    if total_records == 0:
        return {
            "answer": "No data found matching your query. The data ponds may not have recent data for this request.",
            "insights": [
                "No relevant data available",
                "Try a different query or date range",
            ],
            "data_sources": list(pond_results.keys()),
            "record_count": 0,
        }

    prompt = f"""Analyze these query results from NOAA data ponds and provide a cohesive, informative response.

User Query: "{query}"

Results from Data Ponds:
{json.dumps(results_summary, indent=2, default=str)}

Create a response with:
1. **answer**: Clear, concise answer to the user's question (2-3 sentences)
2. **insights**: Array of 3-5 key insights or findings from the data
3. **summary**: Brief statistical summary of the data
4. **recommendations**: Actionable recommendations based on findings (if applicable)
5. **data_quality**: Assessment of data completeness and reliability

Respond in JSON format ONLY:
{{
  "answer": "...",
  "insights": ["...", "..."],
  "summary": "...",
  "recommendations": ["...", "..."],
  "data_quality": "good|moderate|limited"
}}
"""

    try:
        response = invoke_bedrock(prompt, max_tokens=1500)

        # Extract JSON
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.lower().startswith("json"):
                response = response[4:]
        response = response.strip()

        synthesis = json.loads(response)

        # Add metadata
        synthesis["data_sources"] = list(pond_results.keys())
        synthesis["record_count"] = total_records
        synthesis["query_timestamp"] = datetime.utcnow().isoformat()

        return synthesis

    except Exception as e:
        logger.error(f"Error synthesizing results: {e}")
        return {
            "answer": f"Found {total_records} records across {len(pond_results)} data pond(s).",
            "insights": [f"Data retrieved from: {', '.join(pond_results.keys())}"],
            "data_sources": list(pond_results.keys()),
            "record_count": total_records,
            "error": str(e),
        }


# =============================================================================
# MAIN ORCHESTRATOR
# =============================================================================


def lambda_handler(event, context):
    """
    Main Lambda handler for AI-powered query orchestration

    Expected event format:
    {
        "query": "Show me weather alerts in California",
        "include_raw_data": false,
        "max_results_per_pond": 100
    }
    """

    try:
        # Parse event
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

        query = body.get("query")
        if not query:
            return respond(400, {"error": "Missing 'query' parameter"})

        include_raw_data = body.get("include_raw_data", False)
        max_results = body.get("max_results_per_pond", 100)

        logger.info(f"Processing query: {query}")

        # Step 1: Determine relevant ponds
        relevant_ponds = determine_relevant_ponds(query)
        logger.info(f"Relevant ponds: {[p['pond'] for p in relevant_ponds]}")

        # Step 2: Generate and execute queries for each pond
        pond_results = {}
        pond_queries = {}

        for pond_info in relevant_ponds[:3]:  # Limit to top 3 ponds
            pond_name = pond_info["pond"]

            if pond_name not in POND_METADATA:
                continue

            pond_meta = POND_METADATA[pond_name]

            # Generate SQL
            sql = generate_sql_for_pond(query, pond_name, pond_meta)
            pond_queries[pond_name] = sql

            # Execute query
            results = execute_athena_query(sql, pond_name)

            if results:
                pond_results[pond_name] = results[:max_results]

        # Step 3: Synthesize results across ponds
        synthesis = synthesize_results(query, pond_results)

        # Step 4: Build response
        response_data = {
            "query": query,
            "synthesis": synthesis,
            "ponds_queried": [
                {
                    "pond": p["pond"],
                    "confidence": p["confidence"],
                    "reasoning": p["reasoning"],
                    "record_count": len(pond_results.get(p["pond"], [])),
                }
                for p in relevant_ponds[:3]
            ],
            "execution_time_ms": int(
                (time.time() - context.get_remaining_time_in_millis()) if context else 0
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Optionally include raw data
        if include_raw_data:
            response_data["raw_data"] = pond_results
            response_data["sql_queries"] = pond_queries

        logger.info(
            f"Query completed successfully. Records: {synthesis.get('record_count', 0)}"
        )

        return respond(200, response_data)

    except Exception as e:
        logger.exception("Unhandled exception in orchestrator")
        return respond(
            500,
            {
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


def respond(status_code: int, body: Dict) -> Dict:
    """Format Lambda response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


# =============================================================================
# LOCAL TESTING
# =============================================================================

if __name__ == "__main__":
    # Test event
    test_event = {
        "query": "Show me severe weather alerts in California from the last week",
        "include_raw_data": True,
    }

    class MockContext:
        def get_remaining_time_in_millis(self):
            return 30000

    result = lambda_handler(test_event, MockContext())
    print(json.dumps(json.loads(result["body"]), indent=2))
