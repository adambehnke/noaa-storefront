#!/usr/bin/env python3
"""
AI-Powered Bronze to Silver Transformation
Normalizes raw NOAA data across all ponds using AI

This script:
1. Reads raw JSON data from Bronze layer
2. Uses AI to detect schema and normalize fields
3. Applies data quality rules
4. Standardizes units and formats
5. Writes cleaned data to Silver layer in Parquet format

Author: NOAA Federated Data Lake Team
"""

import sys
import json
import boto3
from datetime import datetime
from typing import Dict, List, Any, Optional
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, Row
from pyspark.sql.functions import col, when, lit, udf, to_timestamp, current_timestamp
from pyspark.sql.types import (
    StringType,
    DoubleType,
    IntegerType,
    TimestampType,
    StructType,
    StructField,
)
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from awsglue.dynamicframe import DynamicFrame

# Parse arguments
args = getResolvedOptions(sys.argv, ["JOB_NAME", "LAKE_BUCKET", "ENV", "POND"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Configuration
lake_bucket = args["LAKE_BUCKET"]
env = args["ENV"]
pond_name = args.get("POND", "atmospheric")

# AWS clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
s3_client = boto3.client("s3")

# Bedrock model
BEDROCK_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"

print(f"Starting Bronze to Silver transformation for pond: {pond_name}")
print(f"Environment: {env}")
print(f"Bucket: {lake_bucket}")


# =============================================================================
# AI FUNCTIONS
# =============================================================================


def invoke_bedrock_for_schema(sample_data: Dict, pond_type: str) -> Dict:
    """
    Use AI to analyze data and suggest normalized schema

    Args:
        sample_data: Sample records from Bronze layer
        pond_type: Type of data pond (atmospheric, oceanic, etc.)

    Returns:
        Schema mapping and transformation rules
    """
    try:
        prompt = f"""Analyze this sample NOAA data from the {pond_type} pond and create a normalized schema.

Sample Data (first 3 records):
{json.dumps(sample_data, indent=2, default=str)[:2000]}

Create a normalized schema with:
1. Consistent field names (snake_case)
2. Appropriate data types (string, double, integer, timestamp)
3. Unit standardization (metric preferred)
4. Field mappings from source to target

Respond in JSON format:
{{
  "normalized_fields": [
    {{"source": "original_field", "target": "normalized_field", "type": "double", "unit": "celsius", "transformation": "keep_as_is|convert|parse"}},
    ...
  ],
  "quality_rules": [
    {{"field": "temperature", "rule": "range", "min": -100, "max": 100, "unit": "celsius"}},
    ...
  ],
  "key_fields": ["timestamp", "location", "station_id"]
}}

Keep it concise and focus on the most important fields."""

        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,
            "messages": messages,
            "temperature": 0.3,
        }

        response = bedrock.invoke_model(modelId=BEDROCK_MODEL, body=json.dumps(body))

        response_body = json.loads(response["body"].read())
        schema_text = response_body["content"][0]["text"]

        # Extract JSON from response
        schema_text = schema_text.strip()
        if schema_text.startswith("```"):
            schema_text = schema_text.split("```")[1]
            if schema_text.lower().startswith("json"):
                schema_text = schema_text[4:]
        schema_text = schema_text.strip()

        schema = json.loads(schema_text)
        print(f"AI-generated schema: {len(schema.get('normalized_fields', []))} fields")

        return schema

    except Exception as e:
        print(f"Error invoking Bedrock for schema: {e}")
        return get_default_schema(pond_type)


def get_default_schema(pond_type: str) -> Dict:
    """Fallback schema if AI fails"""

    schemas = {
        "atmospheric": {
            "normalized_fields": [
                {
                    "source": "id",
                    "target": "record_id",
                    "type": "string",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "event",
                    "target": "event_type",
                    "type": "string",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "severity",
                    "target": "severity",
                    "type": "string",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "timestamp",
                    "target": "timestamp",
                    "type": "timestamp",
                    "transformation": "parse",
                },
                {
                    "source": "station_id",
                    "target": "station_id",
                    "type": "string",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "temperature",
                    "target": "temp_celsius",
                    "type": "double",
                    "transformation": "keep_as_is",
                },
            ],
            "quality_rules": [],
            "key_fields": ["timestamp", "station_id"],
        },
        "oceanic": {
            "normalized_fields": [
                {
                    "source": "station_id",
                    "target": "station_id",
                    "type": "string",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "timestamp",
                    "target": "timestamp",
                    "type": "timestamp",
                    "transformation": "parse",
                },
                {
                    "source": "water_level",
                    "target": "water_level_meters",
                    "type": "double",
                    "transformation": "keep_as_is",
                },
                {
                    "source": "water_temp_celsius",
                    "target": "water_temp_celsius",
                    "type": "double",
                    "transformation": "keep_as_is",
                },
            ],
            "quality_rules": [],
            "key_fields": ["timestamp", "station_id"],
        },
    }

    return schemas.get(pond_type, schemas["atmospheric"])


# =============================================================================
# DATA TRANSFORMATION
# =============================================================================


def normalize_dataframe(
    df: DataFrame, schema_mapping: Dict, pond_type: str
) -> DataFrame:
    """
    Apply normalization rules to DataFrame

    Args:
        df: Input DataFrame from Bronze
        schema_mapping: AI-generated schema mappings
        pond_type: Type of pond

    Returns:
        Normalized DataFrame
    """

    print(f"Normalizing DataFrame with {df.count()} records")

    # Build select expression based on schema mapping
    select_exprs = []

    for field_map in schema_mapping.get("normalized_fields", []):
        source = field_map["source"]
        target = field_map["target"]
        field_type = field_map.get("type", "string")
        transformation = field_map.get("transformation", "keep_as_is")

        # Check if source field exists
        if source not in df.columns:
            print(f"Warning: Source field '{source}' not found, skipping")
            continue

        # Apply transformation
        if transformation == "parse" and field_type == "timestamp":
            # Parse timestamp
            select_exprs.append(to_timestamp(col(source)).alias(target))
        elif transformation == "convert":
            # Type conversion
            if field_type == "double":
                select_exprs.append(col(source).cast(DoubleType()).alias(target))
            elif field_type == "integer":
                select_exprs.append(col(source).cast(IntegerType()).alias(target))
            else:
                select_exprs.append(col(source).cast(StringType()).alias(target))
        else:
            # Keep as is, just rename
            select_exprs.append(col(source).alias(target))

    # Add metadata fields
    select_exprs.extend(
        [
            lit(pond_type).alias("data_pond"),
            current_timestamp().alias("processed_timestamp"),
            lit(env).alias("environment"),
        ]
    )

    # Apply transformations
    normalized_df = df.select(*select_exprs)

    # Apply quality rules
    for rule in schema_mapping.get("quality_rules", []):
        field = rule["field"]
        if field in normalized_df.columns:
            if rule["rule"] == "range":
                min_val = rule.get("min", float("-inf"))
                max_val = rule.get("max", float("inf"))

                normalized_df = normalized_df.withColumn(
                    field,
                    when(
                        (col(field) >= min_val) & (col(field) <= max_val), col(field)
                    ).otherwise(None),
                )
                print(f"Applied range rule to {field}: [{min_val}, {max_val}]")

    # Remove null rows for key fields
    key_fields = schema_mapping.get("key_fields", [])
    for key_field in key_fields:
        if key_field in normalized_df.columns:
            normalized_df = normalized_df.filter(col(key_field).isNotNull())

    print(
        f"Normalization complete: {normalized_df.count()} records after quality checks"
    )

    return normalized_df


def deduplicate_data(df: DataFrame, key_fields: List[str]) -> DataFrame:
    """Remove duplicate records based on key fields"""

    if not key_fields:
        return df

    # Check which key fields exist
    existing_keys = [k for k in key_fields if k in df.columns]

    if not existing_keys:
        print("Warning: No key fields found for deduplication")
        return df

    print(f"Deduplicating on fields: {existing_keys}")

    before_count = df.count()
    df_dedup = df.dropDuplicates(existing_keys)
    after_count = df_dedup.count()

    print(f"Removed {before_count - after_count} duplicate records")

    return df_dedup


def add_data_quality_metrics(df: DataFrame) -> DataFrame:
    """Add data quality score to each record"""

    # Calculate completeness score (% of non-null fields)
    total_fields = len(df.columns)

    # This is a simplified quality score
    # In production, you'd have more sophisticated metrics

    quality_expr = lit(1.0)  # Default quality score

    df_with_quality = df.withColumn("data_quality_score", quality_expr)

    return df_with_quality


# =============================================================================
# MAIN TRANSFORMATION LOGIC
# =============================================================================


def transform_pond_data(pond: str):
    """Transform data for a specific pond"""

    bronze_path = f"s3://{lake_bucket}/bronze/{pond}/"
    silver_path = f"s3://{lake_bucket}/silver/{pond}_cleaned/"

    print(f"\n{'=' * 60}")
    print(f"Transforming {pond} pond")
    print(f"Source: {bronze_path}")
    print(f"Destination: {silver_path}")
    print(f"{'=' * 60}\n")

    try:
        # Read Bronze data
        print("Reading Bronze layer data...")
        df = spark.read.json(bronze_path)

        if df.count() == 0:
            print(f"No data found in {bronze_path}")
            return

        print(f"Loaded {df.count()} records from Bronze")
        print(f"Schema: {df.schema}")

        # Get sample data for AI analysis
        sample_data = df.limit(3).toJSON().collect()
        sample_data = [json.loads(record) for record in sample_data]

        # Use AI to generate schema
        print("\nInvoking AI to analyze schema...")
        schema_mapping = invoke_bedrock_for_schema(sample_data, pond)

        # Normalize data
        print("\nNormalizing data...")
        normalized_df = normalize_dataframe(df, schema_mapping, pond)

        # Deduplicate
        print("\nDeduplicating records...")
        key_fields = schema_mapping.get("key_fields", [])
        deduped_df = deduplicate_data(normalized_df, key_fields)

        # Add quality metrics
        print("\nAdding quality metrics...")
        final_df = add_data_quality_metrics(deduped_df)

        # Write to Silver layer
        print(f"\nWriting to Silver layer: {silver_path}")
        final_df.write.mode("overwrite").parquet(silver_path)

        final_count = final_df.count()
        print(f"✓ Successfully wrote {final_count} records to Silver layer")

        # Store transformation metadata
        metadata = {
            "pond": pond,
            "bronze_records": df.count(),
            "silver_records": final_count,
            "schema_mapping": schema_mapping,
            "transformation_timestamp": datetime.utcnow().isoformat(),
            "environment": env,
        }

        metadata_key = f"silver/{pond}_cleaned/_metadata/transformation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        s3_client.put_object(
            Bucket=lake_bucket,
            Key=metadata_key,
            Body=json.dumps(metadata, indent=2, default=str),
            ContentType="application/json",
        )

        print(f"✓ Transformation metadata saved")

    except Exception as e:
        print(f"✗ Error transforming {pond} pond: {e}")
        import traceback

        traceback.print_exc()
        raise


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def main():
    """Main entry point"""

    print("=" * 60)
    print("AI-Powered Bronze to Silver Transformation")
    print("=" * 60)

    start_time = datetime.utcnow()

    stats = {
        "start_time": start_time.isoformat(),
        "pond": pond_name,
        "status": "RUNNING",
    }

    try:
        # Transform specified pond
        transform_pond_data(pond_name)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = duration
        stats["status"] = "SUCCESS"

        print("\n" + "=" * 60)
        print("Transformation Complete!")
        print(f"Duration: {duration:.2f} seconds")
        print("=" * 60)

        job.commit()

    except Exception as e:
        print(f"\n✗ Fatal error in transformation: {e}")
        stats["status"] = "FAILED"
        stats["error"] = str(e)
        raise


if __name__ == "__main__":
    main()
