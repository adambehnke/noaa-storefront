import json
import os
import time
import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# --- Logging setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- AWS Clients ---
athena = boto3.client("athena")

# --- Redis client (lazy loaded) ---
redis_client = None

# --- Environment Variables ---
GOLD_DB = os.environ.get("GOLD_DB", "noaa_gold_dev")
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT")
REDIS_ENDPOINT = os.environ.get("REDIS_ENDPOINT")
ENV = os.environ.get("ENV", "dev")
CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))  # 1 hour default


# =============================================================
# Redis Connection (Lazy Load)
# =============================================================
def get_redis_client():
    """Lazy load Redis client to avoid connection issues during cold start"""
    global redis_client

    if redis_client is None and REDIS_ENDPOINT:
        try:
            import redis

            redis_client = redis.Redis(
                host=REDIS_ENDPOINT,
                port=6379,
                db=0,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            redis_client.ping()
            logger.info(f"Connected to Redis at {REDIS_ENDPOINT}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Proceeding without cache.")
            redis_client = None

    return redis_client


# =============================================================
# Core Lambda Handler
# =============================================================
def lambda_handler(event, context):
    """
    Entry point for Lambda - handles data queries with caching

    Query parameters:
    - service: nws, tides, cdo, oceanic, atmospheric, terrestrial, spatial
    - region: state code or region name (e.g., CA, Northeast)
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - limit: max records to return (default 100)
    - fields: comma-separated fields to return
    """

    try:
        # Parse event (API Gateway format or direct invocation)
        if isinstance(event, dict) and "queryStringParameters" in event:
            params = event.get("queryStringParameters") or {}
            http_method = event.get("httpMethod", "GET")
            path = event.get("path", "/data")
        else:
            params = event if isinstance(event, dict) else {}
            http_method = "GET"
            path = "/data"

        logger.info(f"Request: {http_method} {path} with params: {params}")

        # Handle health check
        if params.get("ping") == "true":
            return respond(
                200,
                {
                    "status": "healthy",
                    "env": ENV,
                    "timestamp": datetime.utcnow().isoformat(),
                    "redis_enabled": REDIS_ENDPOINT is not None,
                },
            )

        # Extract query parameters
        service = params.get("service", "atmospheric")
        region = params.get("region")
        start_date = params.get(
            "start_date", (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        )
        end_date = params.get("end_date", datetime.utcnow().strftime("%Y-%m-%d"))
        limit = int(params.get("limit", 100))
        fields = params.get("fields", "*")

        # Validate service
        valid_services = [
            "nws",
            "atmospheric",
            "oceanic",
            "tides",
            "cdo",
            "terrestrial",
            "spatial",
            "multitype",
        ]
        if service not in valid_services:
            return respond(
                400,
                {
                    "error": f"Invalid service '{service}'. Valid options: {', '.join(valid_services)}"
                },
            )

        # Generate cache key
        cache_key = (
            f"data:{service}:{region or 'all'}:{start_date}:{end_date}:{limit}:{fields}"
        )

        # Try to get from cache
        cached_data = get_from_cache(cache_key)
        if cached_data:
            logger.info(f"Cache hit for key: {cache_key}")
            return respond(
                200,
                {
                    "source": "cache",
                    "service": service,
                    "data": cached_data,
                    "count": len(cached_data) if isinstance(cached_data, list) else 1,
                },
            )

        # Build SQL query based on service
        sql_query = build_query(service, region, start_date, end_date, limit, fields)

        logger.info(f"Executing Athena query: {sql_query}")

        # Execute Athena query
        query_id = start_athena_query(sql_query)
        results = get_query_results(query_id)

        # Cache results
        set_in_cache(cache_key, results, CACHE_TTL)

        return respond(
            200,
            {
                "source": "athena",
                "service": service,
                "query_id": query_id,
                "data": results,
                "count": len(results),
                "parameters": {
                    "service": service,
                    "region": region,
                    "start_date": start_date,
                    "end_date": end_date,
                    "limit": limit,
                },
            },
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return respond(400, {"error": str(e)})

    except Exception as e:
        logger.exception("Unhandled exception in data_api_handler")
        return respond(500, {"error": str(e), "type": type(e).__name__})


# =============================================================
# Query Builder
# =============================================================
def build_query(
    service: str,
    region: Optional[str],
    start_date: str,
    end_date: str,
    limit: int,
    fields: str,
) -> str:
    """Build Athena SQL query based on service type and parameters"""

    # Map service to table
    table_mapping = {
        "nws": "atmospheric_aggregated",
        "atmospheric": "atmospheric_aggregated",
        "oceanic": "oceanic_aggregated",
        "tides": "oceanic_aggregated",
        "cdo": "atmospheric_aggregated",
        "terrestrial": "terrestrial_aggregated",
        "spatial": "spatial_aggregated",
        "multitype": "multitype_aggregated",
    }

    table_name = table_mapping.get(service, "atmospheric_aggregated")

    # Build SELECT clause
    if fields == "*":
        select_clause = "*"
    else:
        select_clause = fields.replace(",", ", ")

    # Build WHERE clause
    where_conditions = []

    if region:
        where_conditions.append(f"region = '{region}'")

    # Add date filter
    where_conditions.append(f"date >= DATE '{start_date}'")
    where_conditions.append(f"date <= DATE '{end_date}'")

    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

    # Construct full query
    query = f"""
    SELECT {select_clause}
    FROM {GOLD_DB}.{table_name}
    WHERE {where_clause}
    ORDER BY date DESC
    LIMIT {limit}
    """

    return query.strip()


# =============================================================
# Athena Query Execution
# =============================================================
def start_athena_query(sql: str) -> str:
    """Start Athena query execution and return query ID"""

    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": GOLD_DB},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        WorkGroup="primary",
    )

    return response["QueryExecutionId"]


def get_query_results(query_id: str, max_wait: int = 30) -> List[Dict[str, Any]]:
    """
    Wait for Athena query to complete and return results as list of dicts

    Args:
        query_id: Athena query execution ID
        max_wait: Maximum seconds to wait for query completion

    Returns:
        List of dictionaries with column names as keys
    """

    start_time = time.time()

    while time.time() - start_time < max_wait:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        elif state in ["FAILED", "CANCELLED"]:
            reason = response["QueryExecution"]["Status"].get(
                "StateChangeReason", "Unknown"
            )
            raise Exception(f"Athena query failed: {reason}")

        time.sleep(1)
    else:
        raise TimeoutError(
            f"Athena query {query_id} did not complete within {max_wait} seconds"
        )

    # Get results
    result_response = athena.get_query_results(
        QueryExecutionId=query_id, MaxResults=1000
    )

    # Parse results into list of dicts
    rows = result_response["ResultSet"]["Rows"]

    if not rows:
        return []

    # First row is header
    headers = [col["VarCharValue"] for col in rows[0]["Data"]]

    # Convert remaining rows to dicts
    results = []
    for row in rows[1:]:
        row_dict = {}
        for i, col in enumerate(row["Data"]):
            value = col.get("VarCharValue")
            row_dict[headers[i]] = value
        results.append(row_dict)

    return results


# =============================================================
# Cache Functions
# =============================================================
def get_from_cache(key: str) -> Optional[Any]:
    """Get value from Redis cache"""
    try:
        client = get_redis_client()
        if client:
            cached = client.get(key)
            if cached:
                return json.loads(cached)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")

    return None


def set_in_cache(key: str, value: Any, ttl: int):
    """Set value in Redis cache with TTL"""
    try:
        client = get_redis_client()
        if client:
            client.setex(key, ttl, json.dumps(value))
            logger.info(f"Cached data with key: {key} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


# =============================================================
# Response Helper
# =============================================================
def respond(status_code: int, body: Dict) -> Dict:
    """Format Lambda response for API Gateway"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


# =============================================================
# For local testing
# =============================================================
if __name__ == "__main__":
    # Test event
    test_event = {
        "queryStringParameters": {
            "service": "atmospheric",
            "region": "CA",
            "limit": "10",
        }
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
