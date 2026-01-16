#!/usr/bin/env python3
"""
Enhanced Query Handler with INDUS RAG Integration
NOAA Federated Data Lake - Production Version with NASA INDUS

Features:
- INDUS embeddings for semantic search
- Vector search with OpenSearch Serverless
- Enhanced Claude prompts with scientific context
- Backward compatible (feature flag controlled)
- Comprehensive error handling and fallbacks

Author: NOAA Federated Data Lake Team
Version: 4.0 - INDUS RAG Integration
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
from botocore.exceptions import ClientError

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
S3_BUCKET = os.environ.get("S3_BUCKET", "noaa-federated-lake-899626030376-dev")

# INDUS Configuration
INDUS_ENABLED = os.environ.get("INDUS_ENABLED", "true").lower() == "true"
INDUS_EMBEDDING_LAMBDA = os.environ.get(
    "INDUS_EMBEDDING_LAMBDA", f"noaa-indus-embedding-{ENV}"
)
INDUS_FALLBACK_ON_ERROR = (
    os.environ.get("INDUS_FALLBACK_ON_ERROR", "true").lower() == "true"
)

# Configuration
RELEVANCE_THRESHOLD = 0.3
MAX_PARALLEL_PONDS = 6
QUERY_TIMEOUT = 25.0

# =============================================================================
# POND METADATA REGISTRY
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
        ],
    },
    "oceanic": {
        "name": "Oceanic Pond",
        "description": "Ocean and coastal data from NOAA CO-OPS including tides, water levels, temperatures, and currents",
        "data_types": [
            "water levels",
            "tide predictions and observations",
            "water temperature",
            "salinity",
            "currents",
            "sea surface height",
            "coastal flooding",
        ],
        "relevance_keywords": [
            "ocean",
            "tide",
            "water level",
            "sea",
            "coastal",
            "marine",
            "current",
            "salinity",
        ],
    },
    "buoy": {
        "name": "Buoy Pond",
        "description": "Marine buoy observations from NDBC including wave heights, water temperature, and meteorological data",
        "data_types": [
            "wave height",
            "wave period",
            "wave direction",
            "sea surface temperature",
            "wind data from buoys",
            "air pressure at sea",
        ],
        "relevance_keywords": [
            "buoy",
            "wave",
            "offshore",
            "marine",
            "ndbc",
            "station",
        ],
    },
    "climate": {
        "name": "Climate Pond",
        "description": "Historical climate data from NOAA CDO including temperature, precipitation, and climate normals",
        "data_types": [
            "historical temperature",
            "historical precipitation",
            "climate normals",
            "extremes",
            "monthly/annual summaries",
        ],
        "relevance_keywords": [
            "climate",
            "historical",
            "past",
            "record",
            "normal",
            "average",
            "trend",
        ],
    },
    "terrestrial": {
        "name": "Terrestrial Pond",
        "description": "River and stream data from USGS including water levels, flow rates, and stage data",
        "data_types": [
            "river levels",
            "stream flow",
            "discharge",
            "gage height",
        ],
        "relevance_keywords": [
            "river",
            "stream",
            "flow",
            "usgs",
            "gage",
            "discharge",
        ],
    },
    "spatial": {
        "name": "Spatial Pond",
        "description": "Satellite and radar imagery from NOAA including GOES, NEXRAD",
        "data_types": [
            "satellite imagery",
            "radar data",
            "GOES",
            "NEXRAD",
        ],
        "relevance_keywords": [
            "satellite",
            "radar",
            "image",
            "nexrad",
            "goes",
            "imagery",
        ],
    },
}

# =============================================================================
# INDUS RAG FUNCTIONS
# =============================================================================


def call_indus_embedding(text: str) -> Optional[List[float]]:
    """
    Call INDUS embedding Lambda to generate semantic vector

    Returns:
        768-dimensional embedding vector or None on failure
    """
    if not INDUS_ENABLED:
        logger.info("INDUS disabled, skipping embedding")
        return None

    try:
        response = lambda_client.invoke(
            FunctionName=INDUS_EMBEDDING_LAMBDA,
            InvocationType="RequestResponse",
            Payload=json.dumps({"action": "embed", "text": text}),
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            body = json.loads(result["body"])
            embedding = body.get("embedding")

            if embedding and len(embedding) == 768:
                logger.info(f"✅ INDUS embedding generated (768 dimensions)")
                return embedding
            else:
                logger.warning(
                    f"Invalid embedding dimension: {len(embedding) if embedding else 0}"
                )
                return None
        else:
            logger.error(f"INDUS embedding failed: {result}")
            return None

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            logger.warning(f"INDUS Lambda not found: {INDUS_EMBEDDING_LAMBDA}")
        else:
            logger.error(f"AWS error calling INDUS: {e}")
        return None
    except Exception as e:
        logger.error(f"Error calling INDUS embedding: {e}")
        return None


def search_indus_vectors(
    query_embedding: List[float], ponds: List[str] = None, top_k: int = 5
) -> List[Dict]:
    """
    Search OpenSearch Serverless for similar vectors

    Returns:
        List of relevant contexts with metadata
    """
    if not query_embedding:
        return []

    if ponds is None:
        ponds = list(POND_METADATA.keys())

    all_contexts = []

    for pond in ponds:
        try:
            response = lambda_client.invoke(
                FunctionName=INDUS_EMBEDDING_LAMBDA,
                InvocationType="RequestResponse",
                Payload=json.dumps(
                    {
                        "action": "search",
                        "text": "",  # Not used, we provide embedding directly
                        "embedding": query_embedding,
                        "pond": pond,
                        "top_k": 3,
                    }
                ),
            )

            result = json.loads(response["Payload"].read())

            if result.get("statusCode") == 200:
                body = json.loads(result["body"])
                results = body.get("results", [])

                for r in results:
                    r["pond"] = pond
                    all_contexts.append(r)

        except Exception as e:
            logger.warning(f"Vector search failed for {pond}: {e}")
            continue

    # Sort by score and return top K
    all_contexts.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_contexts = all_contexts[:top_k]

    logger.info(
        f"✅ Retrieved {len(top_contexts)} INDUS contexts (from {len(all_contexts)} total)"
    )

    return top_contexts


def enhance_prompt_with_indus(query: str, contexts: List[Dict]) -> str:
    """
    Enhance Claude prompt with INDUS scientific context

    Returns:
        Enhanced prompt string with context
    """
    if not contexts:
        return query

    context_text = "\n\n".join(
        [
            f"Scientific Context {i + 1} (Pond: {ctx.get('pond', 'unknown')}, Relevance: {ctx.get('score', 0):.3f}):\n"
            f"{ctx.get('text', '')}"
            for i, ctx in enumerate(contexts[:5])
        ]
    )

    enhanced = f"""You are analyzing environmental data from NOAA with enhanced scientific context.

User Query: {query}

Relevant Scientific Context (from NASA's INDUS model trained on Earth science literature):
{context_text}

Instructions:
1. Use the provided scientific context to inform your understanding
2. These contexts were retrieved using domain-specific embeddings trained on Earth science
3. Prioritize scientifically accurate terminology from the context
4. If context doesn't fully address the query, use your general knowledge
5. Cite which contexts informed your reasoning

Now, analyze the query and determine which NOAA data ponds are most relevant:"""

    return enhanced


# =============================================================================
# MAIN HANDLER
# =============================================================================


def lambda_handler(event, context):
    """
    Main entry point for AI-powered multi-pond queries with INDUS RAG
    """
    start_time = time.time()

    # Track INDUS usage
    indus_metrics = {
        "enabled": INDUS_ENABLED,
        "embedding_success": False,
        "contexts_retrieved": 0,
        "contexts_used": 0,
        "fallback_triggered": False,
    }

    try:
        # Parse request
        if isinstance(event, str):
            event = json.loads(event)

        query = event.get("query", "")
        if not query:
            return respond(400, {"error": "Missing 'query' parameter"})

        # Check if INDUS should be used for this request
        use_indus = event.get("use_indus", INDUS_ENABLED)

        logger.info(f"Query received: {query[:100]}...")
        logger.info(f"INDUS enabled: {use_indus}")

        # Step 1: INDUS RAG (if enabled)
        indus_contexts = []
        enhanced_query = query

        if use_indus:
            try:
                # Generate INDUS embedding
                query_embedding = call_indus_embedding(query)

                if query_embedding:
                    indus_metrics["embedding_success"] = True

                    # Search for relevant contexts
                    indus_contexts = search_indus_vectors(query_embedding, top_k=5)
                    indus_metrics["contexts_retrieved"] = len(indus_contexts)

                    if indus_contexts:
                        # Enhance prompt with INDUS context
                        enhanced_query = enhance_prompt_with_indus(
                            query, indus_contexts
                        )
                        indus_metrics["contexts_used"] = len(indus_contexts)

                        logger.info(
                            f"✅ INDUS RAG active: {len(indus_contexts)} contexts"
                        )
                    else:
                        logger.info("No INDUS contexts found, using standard query")
                else:
                    logger.warning(
                        "INDUS embedding failed, falling back to standard query"
                    )
                    indus_metrics["fallback_triggered"] = True

            except Exception as e:
                logger.error(f"INDUS RAG error: {e}")
                indus_metrics["fallback_triggered"] = True

                if not INDUS_FALLBACK_ON_ERROR:
                    return respond(
                        500, {"error": "INDUS processing failed", "details": str(e)}
                    )

        # Step 2: Understand query with AI (enhanced by INDUS if available)
        understanding = understand_query_with_ai(enhanced_query)

        # Step 3: Select relevant ponds
        pond_selection = select_ponds_with_ai(query, understanding, indus_contexts)

        # Step 4: Query ponds in parallel
        results = query_ponds_parallel(pond_selection)

        # Step 5: Synthesize results with Claude (with INDUS context)
        response = synthesize_results_with_ai(query, results, indus_contexts)

        # Add INDUS metrics to response
        response["indus_metrics"] = indus_metrics
        response["indus_contexts_count"] = len(indus_contexts)

        # Add timing
        elapsed = time.time() - start_time
        response["elapsed_time"] = round(elapsed, 3)

        logger.info(f"Query completed in {elapsed:.2f}s")
        logger.info(f"INDUS metrics: {indus_metrics}")

        return respond(200, response)

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return respond(500, {"error": str(e), "indus_metrics": indus_metrics})


# =============================================================================
# AI UNDERSTANDING FUNCTIONS
# =============================================================================


def understand_query_with_ai(query: str) -> Dict:
    """
    Use Bedrock/Claude to semantically understand what the user is asking
    Now enhanced with INDUS context if available
    """

    prompt = f"""Analyze this user query about environmental/weather/ocean data:

Query: "{query}"

Provide a semantic understanding of what the user is asking. Consider:
1. What is the primary intent? (observation, forecast, historical, comparison, risk_assessment, route_planning, etc.)
2. What specific information are they seeking?
3. What geographic location(s) are involved?
4. What time frame is relevant? (current, forecast, historical, etc.)
5. What are the implicit requirements?

Respond with JSON only:
{{
    "primary_intent": "observation|forecast|historical|comparison|risk_assessment|route_planning|conditions_check",
    "information_sought": ["specific data points needed"],
    "locations": ["location1", "location2"],
    "time_frame": "current|forecast|historical|specific_date",
    "implicit_requirements": ["things needed but not explicitly mentioned"],
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

    intent = "observation"
    if any(w in query_lower for w in ["forecast", "will", "future", "tomorrow"]):
        intent = "forecast"
    elif any(w in query_lower for w in ["historical", "past", "was", "history"]):
        intent = "historical"

    return {
        "primary_intent": intent,
        "information_sought": ["general information"],
        "locations": [],
        "time_frame": "current",
        "implicit_requirements": [],
        "complexity": "moderate",
        "question_type": "factual",
    }


def select_ponds_with_ai(
    query: str, understanding: Dict, indus_contexts: List[Dict] = None
) -> List[Dict]:
    """
    Select relevant ponds using AI, enhanced by INDUS context
    """

    # Build context from INDUS if available
    indus_context_text = ""
    if indus_contexts:
        indus_context_text = "\n\nScientific Context from INDUS:\n" + "\n".join(
            [
                f"- {ctx.get('pond', 'unknown')}: {ctx.get('text', '')[:100]}..."
                for ctx in indus_contexts[:3]
            ]
        )

    prompt = f"""Based on this query and understanding, select the most relevant NOAA data ponds.

Query: "{query}"

Understanding:
{json.dumps(understanding, indent=2)}
{indus_context_text}

Available Data Ponds:
{json.dumps(POND_METADATA, indent=2)}

Return JSON array of selected ponds with relevance scores:
[
  {{"pond": "pond_name", "relevance": 0.0-1.0, "reasoning": "why relevant"}}
]

Only include ponds with relevance > 0.3."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                }
            ),
        )

        result = json.loads(response["body"].read())
        content = result["content"][0]["text"]

        # Extract JSON array
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            selections = json.loads(json_match.group())

            # Filter and validate
            valid_selections = [
                s
                for s in selections
                if s.get("pond") in POND_METADATA
                and s.get("relevance", 0) > RELEVANCE_THRESHOLD
            ]

            logger.info(
                f"Selected {len(valid_selections)} ponds: {[s['pond'] for s in valid_selections]}"
            )
            return valid_selections
        else:
            logger.warning("Could not parse pond selection, using fallback")
            return get_fallback_pond_selection(query)

    except Exception as e:
        logger.error(f"Error in pond selection: {e}")
        return get_fallback_pond_selection(query)


def get_fallback_pond_selection(query: str) -> List[Dict]:
    """Fallback pond selection using keywords"""
    query_lower = query.lower()
    selections = []

    for pond_name, pond_data in POND_METADATA.items():
        keywords = pond_data.get("relevance_keywords", [])
        matches = sum(1 for kw in keywords if kw in query_lower)

        if matches > 0:
            relevance = min(matches / 3, 1.0)
            selections.append(
                {
                    "pond": pond_name,
                    "relevance": relevance,
                    "reasoning": f"Keyword matches: {matches}",
                }
            )

    # Sort by relevance and filter
    selections.sort(key=lambda x: x["relevance"], reverse=True)
    return [s for s in selections if s["relevance"] > RELEVANCE_THRESHOLD]


# =============================================================================
# QUERY EXECUTION
# =============================================================================


def query_ponds_parallel(pond_selections: List[Dict]) -> Dict[str, Any]:
    """Query multiple ponds in parallel"""

    if not pond_selections:
        logger.warning("No ponds selected for query")
        return {}

    results = {}

    with ThreadPoolExecutor(
        max_workers=min(len(pond_selections), MAX_PARALLEL_PONDS)
    ) as executor:
        future_to_pond = {
            executor.submit(query_single_pond, selection): selection["pond"]
            for selection in pond_selections
        }

        for future in as_completed(future_to_pond, timeout=QUERY_TIMEOUT):
            pond_name = future_to_pond[future]
            try:
                pond_result = future.result()
                results[pond_name] = pond_result
            except Exception as e:
                logger.error(f"Error querying {pond_name}: {e}")
                results[pond_name] = {"error": str(e), "data": []}

    return results


def query_single_pond(selection: Dict) -> Dict:
    """Query a single pond (simplified for demo)"""

    pond_name = selection["pond"]

    # For now, return metadata
    # In production, this would query Athena
    return {
        "pond": pond_name,
        "relevance": selection["relevance"],
        "data": [],
        "message": f"Query execution for {pond_name} (Athena integration required)",
    }


# =============================================================================
# RESULT SYNTHESIS
# =============================================================================


def synthesize_results_with_ai(
    query: str, results: Dict, indus_contexts: List[Dict] = None
) -> Dict:
    """
    Synthesize results with Claude, enhanced by INDUS context
    """

    # Build context from INDUS
    indus_context_section = ""
    if indus_contexts:
        indus_context_section = "\n\nScientific Context (INDUS):\n" + "\n".join(
            [f"- {ctx.get('text', '')[:150]}..." for ctx in indus_contexts[:3]]
        )

    results_summary = json.dumps(results, indent=2)

    prompt = f"""Synthesize a comprehensive response to this query using the retrieved data.

User Query: "{query}"
{indus_context_section}

Retrieved Data:
{results_summary}

Provide a clear, accurate response that:
1. Directly answers the user's question
2. Uses scientific terminology correctly (aided by INDUS context if available)
3. Cites specific data sources
4. Notes any limitations or gaps

Response:"""

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
        answer = result["content"][0]["text"]

        return {
            "query": query,
            "answer": answer,
            "ponds_queried": list(results.keys()),
            "data": results,
            "indus_enhanced": len(indus_contexts) > 0 if indus_contexts else False,
        }

    except Exception as e:
        logger.error(f"Error synthesizing results: {e}")
        return {
            "query": query,
            "answer": f"Error synthesizing response: {str(e)}",
            "ponds_queried": list(results.keys()),
            "data": results,
        }


# =============================================================================
# UTILITIES
# =============================================================================


def respond(status_code: int, body: Any) -> Dict:
    """Format Lambda response"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body, default=str),
    }
