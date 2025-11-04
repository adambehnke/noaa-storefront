import json
import os
import time
import boto3
import logging

# --- Logging setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- AWS Clients ---
athena = boto3.client("athena")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# --- Environment Variables ---
ATHENA_OUTPUT = os.environ.get("ATHENA_OUTPUT")
BRONZE_DB = os.environ.get("BRONZE_DB", "noaa_bronze_dev")
SILVER_DB = os.environ.get("SILVER_DB", "noaa_silver_dev")
GOLD_DB = os.environ.get("GOLD_DB", "noaa_gold_dev")
ENV = os.environ.get("ENV", "dev")

# =============================================================
# Core Lambda Handler
# =============================================================
def lambda_handler(event, context):
    """Entry point for Lambda"""

    try:
        body = event if isinstance(event, dict) else json.loads(event)
        action = body.get("action", "query")

        if action == "ping":
            return respond(200, {"status": "ok", "env": ENV})

        elif action == "query":
            sql = body.get("sql")
            if not sql:
                return respond(400, {"error": "Missing SQL statement."})
            query_id = start_athena_query(sql)
            rows = get_results(query_id)
            return respond(200, {"query_id": query_id, "rows": rows})

        elif action == "ai_query":
            question = body.get("question")
            if not question:
                return respond(400, {"error": "Missing natural language question."})
            sql = generate_sql_with_bedrock(question)
            query_id = start_athena_query(sql)
            rows = get_results(query_id)
            return respond(200, {"sql": sql, "rows": rows})

        else:
            return respond(400, {"error": f"Unknown action '{action}'"})

    except Exception as e:
        logger.exception("Unhandled exception in ai_query_handler")
        return respond(500, {"error": str(e)})

# =============================================================
# Athena Utilities
# =============================================================
def start_athena_query(sql):
    """Start Athena query execution and return query ID"""
    logger.info(f"Starting Athena query: {sql}")

    resp = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": GOLD_DB},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        WorkGroup="primary"
    )
    return resp["QueryExecutionId"]


def get_results(query_id):
    """Wait for Athena query to finish and return rows"""
    logger.info(f"Fetching results for Athena query: {query_id}")

    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        elif state in ["FAILED", "CANCELLED"]:
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            raise Exception(f"Athena query {query_id} failed: {reason}")
        time.sleep(2)

    results = athena.get_query_results(QueryExecutionId=query_id)
    rows = []

    # Skip the header row
    for row in results["ResultSet"]["Rows"][1:]:
        row_values = [d.get("VarCharValue", None) for d in row["Data"]]
        rows.append(row_values)

    return rows

# =============================================================
# Bedrock SQL Generator
# =============================================================
def generate_sql_with_bedrock(question):
    """Translate natural-language question → Athena SQL"""
    logger.info(f"Generating SQL for question: {question}")

    prompt = f"""
You are an assistant that converts plain English into valid SQL for Amazon Athena.

Available databases:
  - {BRONZE_DB}: Raw ingestion (API pulls)
  - {SILVER_DB}: Cleaned intermediate data
  - {GOLD_DB}: Analytics-ready curated data (preferred)

Each table follows standard weather schema patterns:
  - station (STRING)
  - temp (DOUBLE)
  - humidity (DOUBLE)
  - timestamp (STRING)
  - alert_level (STRING, optional)

Return a single valid Athena SQL statement only — no commentary.
User question: "{question}"
"""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "prompt": prompt,
            "max_tokens": 200,
            "temperature": 0.3
        })
    )

    body = json.loads(response["body"].read())
    sql = body.get("completion") or body.get("output_text") or ""
    sql = sql.strip().strip("```sql").strip("```").strip()
    logger.info(f"Generated SQL: {sql}")
    return sql

# =============================================================
# Helper: Lambda HTTP-style response
# =============================================================
def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }

