#!/usr/bin/env python3
"""
Pure AI-Driven Query Orchestrator for NOAA Federated Data Lake
Version 3.0 - Fully Dynamic AI Synthesis

NO HARDCODED TEMPLATES. Everything determined by AI based on:
- Query intent
- Data available
- User's actual question

Author: NOAA Federated Data Lake Team
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
athena = boto3.client("athena", region_name="us-east-1")
lambda_client = boto3.client("lambda", region_name="us-east-1")

# Environment Variables
GOLD_DB = os.environ.get("GOLD_DB", "noaa_gold_dev")
ATHENA_OUTPUT = os.environ.get(
    "ATHENA_OUTPUT", "s3://noaa-athena-results-899626030376-dev/"
)
BEDROCK_MODEL = os.environ.get(
    "BEDROCK_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"
)
ENV = os.environ.get("ENV", "dev")

# Configuration
RELEVANCE_THRESHOLD = 0.3
MAX_PARALLEL_PONDS = 6
QUERY_TIMEOUT = 15.0


@dataclass
class QueryUnderstanding:
    """Semantic understanding of user query"""

    primary_intent: str
    entities: Dict[str, Any]
    complexity: str
    requires_correlation: bool
    semantic_context: str
    implicit_requirements: List[str]
    question_type: str
    original_query: str


@dataclass
class PondSelection:
    """AI-determined pond selection with reasoning"""

    pond_name: str
    relevance_score: float
    reasoning: str
    query_priority: str
    expected_contribution: str
    data_fields_needed: List[str]


# =============================================================================
# POND METADATA
# =============================================================================

POND_METADATA = {
    "atmospheric": {
        "description": "Weather alerts, forecasts, observations, temperature, wind, precipitation",
        "data_types": [
            "weather",
            "alerts",
            "forecasts",
            "temperature",
            "wind",
            "precipitation",
        ],
        "update_frequency": "15 minutes",
        "example_queries": [
            "weather conditions",
            "temperature",
            "wind speed",
            "weather alerts",
        ],
    },
    "oceanic": {
        "description": "Tides, water levels, currents, coastal conditions, sea surface temperature",
        "data_types": [
            "tides",
            "water_levels",
            "currents",
            "coastal",
            "sea_temperature",
        ],
        "update_frequency": "15 minutes",
        "example_queries": [
            "tide predictions",
            "water levels",
            "ocean currents",
            "coastal conditions",
        ],
    },
    "buoy": {
        "description": "Marine buoy observations including wave height, wind, water temperature",
        "data_types": ["waves", "marine", "offshore", "buoy", "sea_state"],
        "update_frequency": "15 minutes",
        "example_queries": [
            "wave height",
            "offshore conditions",
            "buoy data",
            "sea state",
        ],
    },
    "climate": {
        "description": "Historical climate data, temperature trends, precipitation patterns",
        "data_types": ["historical", "climate", "trends", "long_term"],
        "update_frequency": "60 minutes",
        "example_queries": [
            "historical temperature",
            "climate trends",
            "past weather patterns",
        ],
    },
}


# =============================================================================
# AI FUNCTIONS
# =============================================================================


async def understand_query(query: str) -> QueryUnderstanding:
    """Use AI to understand what the user is asking"""

    prompt = f"""Analyze this user query about environmental/weather/ocean data:

Query: "{query}"

Determine:
1. Primary intent (observation, forecast, historical, comparison, route_planning, conditions_check)
2. What entities/locations are mentioned
3. Complexity level (simple, moderate, complex)
4. Whether cross-pond correlation is needed
5. Question type (factual, analytical, comparative, predictive)

Respond with JSON only:
{{
    "primary_intent": "observation|forecast|historical|comparison|route_planning|conditions_check",
    "entities": {{"locations": [], "time_references": [], "data_types": []}},
    "complexity": "simple|moderate|complex",
    "requires_correlation": true|false,
    "semantic_context": "brief description of what user wants",
    "implicit_requirements": ["what data is needed"],
    "question_type": "factual|analytical|comparative|predictive"
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
            understanding = json.loads(json_match.group())
            return QueryUnderstanding(
                primary_intent=understanding.get("primary_intent", "observation"),
                entities=understanding.get("entities", {}),
                complexity=understanding.get("complexity", "moderate"),
                requires_correlation=understanding.get("requires_correlation", False),
                semantic_context=understanding.get("semantic_context", ""),
                implicit_requirements=understanding.get("implicit_requirements", []),
                question_type=understanding.get("question_type", "factual"),
                original_query=query,
            )
    except Exception as e:
        logger.error(f"Error understanding query: {e}")

    # Fallback
    return QueryUnderstanding(
        primary_intent="observation",
        entities={},
        complexity="moderate",
        requires_correlation=False,
        semantic_context=query,
        implicit_requirements=[],
        question_type="factual",
        original_query=query,
    )


async def select_relevant_ponds(
    understanding: QueryUnderstanding,
) -> List[PondSelection]:
    """Use AI to intelligently select which data ponds are relevant"""

    prompt = f"""Given this query understanding, determine which NOAA data ponds are relevant.

Query: "{understanding.original_query}"
Intent: {understanding.primary_intent}
Context: {understanding.semantic_context}

Available Ponds:
{json.dumps(POND_METADATA, indent=2)}

For EACH pond, decide if it's relevant and provide:
- Relevance score (0.0-1.0)
- Reasoning for selection
- Priority (high/medium/low)
- What data you expect to get from it

Respond with JSON array:
[
    {{
        "pond_name": "atmospheric",
        "relevance_score": 0.95,
        "reasoning": "why this pond is relevant",
        "query_priority": "high",
        "expected_contribution": "what data this will provide",
        "data_fields_needed": ["field1", "field2"]
    }}
]

Only include ponds with relevance_score >= 0.3"""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            selections_data = json.loads(json_match.group())
            selections = []
            for s in selections_data:
                if s.get("relevance_score", 0) >= RELEVANCE_THRESHOLD:
                    selections.append(
                        PondSelection(
                            pond_name=s["pond_name"],
                            relevance_score=s["relevance_score"],
                            reasoning=s["reasoning"],
                            query_priority=s["query_priority"],
                            expected_contribution=s["expected_contribution"],
                            data_fields_needed=s.get("data_fields_needed", []),
                        )
                    )
            return selections[:MAX_PARALLEL_PONDS]
    except Exception as e:
        logger.error(f"Error selecting ponds: {e}")

    # Fallback: select atmospheric pond
    return [
        PondSelection(
            pond_name="atmospheric",
            relevance_score=0.8,
            reasoning="Default selection for weather queries",
            query_priority="high",
            expected_contribution="Current weather conditions",
            data_fields_needed=["temperature", "wind_speed"],
        )
    ]


async def query_pond(pond_name: str, understanding: QueryUnderstanding) -> Dict:
    """Query a specific pond via passthrough API"""

    try:
        # Call passthrough Lambda for real-time data
        response = lambda_client.invoke(
            FunctionName=f"noaa-passthrough-{ENV}",
            InvocationType="RequestResponse",
            Payload=json.dumps(
                {
                    "queryStringParameters": {
                        "service": pond_name,
                        "query": understanding.original_query,
                    }
                }
            ),
        )

        result = json.loads(response["Payload"].read())
        if result.get("statusCode") == 200:
            body = json.loads(result.get("body", "{}"))
            return {
                "success": True,
                "data": body.get("data", []),
                "record_count": len(body.get("data", [])),
                "source": "passthrough_api",
            }
    except Exception as e:
        logger.error(f"Error querying {pond_name}: {e}")

    return {"success": False, "error": str(e), "record_count": 0}


async def execute_multi_pond_query(
    selections: List[PondSelection], understanding: QueryUnderstanding
) -> Dict[str, Dict]:
    """Execute queries across multiple ponds in parallel"""

    tasks = []
    for selection in selections:
        tasks.append(query_pond(selection.pond_name, understanding))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    pond_results = {}
    for i, selection in enumerate(selections):
        if isinstance(results[i], Exception):
            pond_results[selection.pond_name] = {
                "success": False,
                "error": str(results[i]),
            }
        else:
            pond_results[selection.pond_name] = results[i]

    return pond_results


async def synthesize_with_ai(
    query_understanding: QueryUnderstanding,
    pond_results: Dict[str, Dict],
    pond_selections: List[PondSelection],
) -> str:
    """
    Pure AI synthesis - NO TEMPLATES
    AI decides what to show based on query and data
    """

    # Build data summary for AI
    data_summary = {}
    total_records = 0

    for pond_name, result in pond_results.items():
        if result.get("success") and result.get("record_count", 0) > 0:
            data = result.get("data", [])
            total_records += len(data)

            # Provide actual data samples
            data_summary[pond_name] = {
                "record_count": len(data),
                "sample_records": data[:5],  # First 5 records
                "available_fields": list(data[0].keys()) if data else [],
            }

    prompt = f"""You are an expert NOAA data analyst. The user asked: "{query_understanding.original_query}"

Query Analysis:
- Intent: {query_understanding.primary_intent}
- Context: {query_understanding.semantic_context}
- Question Type: {query_understanding.question_type}

Available Data:
{json.dumps(data_summary, indent=2, default=str)}

Total Records Available: {total_records}

Your task:
1. **Answer the user's ACTUAL question** - don't add irrelevant sections
2. **Show RELEVANT data only** - if they asked about temperature, focus on temperature
3. **Use real measurements** - not "999 records", show actual temps, winds, etc.
4. **Format appropriately** for the query type:
   - Temperature query → show temperature data
   - Historical query → show trends/comparisons
   - Route planning → show conditions affecting navigation
   - Forecast → show predictions
5. **Be concise** but informative

Format your response in Markdown with:
- A relevant title (NOT "Maritime Route Analysis" unless it's about routes)
- Sections that make sense for THIS query
- Specific numbers and measurements
- Data sources at the end (with meaningful details, not record counts)

Example for "What's the temperature in Seattle?":
# Temperature Analysis: Seattle

## Current Conditions
Temperature: 14.2°C
Based on data from 12 weather stations in the Seattle area

## Data Sources
- Atmospheric Pond: Temps: 12-16°C | 12 stations

Do NOT include:
- Ocean conditions (unless query mentions ocean/water)
- Wave data (unless query mentions waves/buoys/maritime)
- Route recommendations (unless query is about navigation/routes)
- Wind advisories (unless query mentions wind or is route planning)

Respond with ONLY the formatted markdown answer."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
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

        # Simple fallback
        return f"""# Analysis: {query_understanding.original_query}

Found {total_records} records from {len([r for r in pond_results.values() if r.get("success")])} data sources.

{json.dumps(data_summary, indent=2, default=str)}
"""


# =============================================================================
# MAIN HANDLER
# =============================================================================


def lambda_handler(event, context):
    """Main handler for intelligent orchestrator"""

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
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Query parameter required"}),
            }

        logger.info(f"[{query_id}] Processing: {query}")

        # Run async workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # STAGE 1: Understand query
        query_understanding = loop.run_until_complete(understand_query(query))
        logger.info(f"[{query_id}] Intent: {query_understanding.primary_intent}")

        # STAGE 2: Select ponds
        pond_selections = loop.run_until_complete(
            select_relevant_ponds(query_understanding)
        )
        logger.info(f"[{query_id}] Selected {len(pond_selections)} ponds")

        if not pond_selections:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps(
                    {
                        "query": query,
                        "answer": "I couldn't determine which data sources are relevant. Please try rephrasing.",
                        "ponds_queried": [],
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                    }
                ),
            }

        # STAGE 3: Execute queries
        pond_results = loop.run_until_complete(
            execute_multi_pond_query(pond_selections, query_understanding)
        )

        # STAGE 4: AI Synthesis
        answer = loop.run_until_complete(
            synthesize_with_ai(query_understanding, pond_results, pond_selections)
        )

        loop.close()

        # Build response
        execution_time = int((time.time() - start_time) * 1000)

        ponds_queried = []
        total_records = 0
        for selection in pond_selections:
            result = pond_results.get(selection.pond_name, {})
            record_count = result.get("record_count", 0)
            total_records += record_count

            ponds_queried.append(
                {
                    "pond": selection.pond_name,
                    "relevance_score": selection.relevance_score,
                    "reasoning": selection.reasoning,
                    "records_found": record_count,
                    "status": "success" if result.get("success") else "error",
                }
            )

        response_body = {
            "query_id": query_id,
            "query": query,
            "answer": answer,
            "ponds_queried": ponds_queried,
            "total_records": total_records,
            "execution_time_ms": execution_time,
            "timestamp": datetime.utcnow().isoformat(),
            "query_intent": query_understanding.primary_intent,
            "ai_powered": True,
        }

        logger.info(
            f"[{query_id}] ✓ Complete in {execution_time}ms - {total_records} records"
        )

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
