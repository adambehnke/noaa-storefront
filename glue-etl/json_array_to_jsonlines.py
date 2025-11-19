#!/usr/bin/env python3
"""
Glue ETL: JSON Array to JSON Lines Converter
Converts NOAA Gold layer JSON arrays to JSON Lines format for Athena compatibility

This script reads JSON array files from S3, explodes them into individual records,
and writes them as newline-delimited JSON (JSON Lines) format that Athena can read.

Author: NOAA Federated Data Lake Team
Version: 1.0
"""

import json
import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    explode,
    from_json,
    input_file_name,
    regexp_extract,
    struct,
    to_json,
)
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Get job parameters
args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "SOURCE_BUCKET",
        "SOURCE_PREFIX",
        "TARGET_BUCKET",
        "TARGET_PREFIX",
        "POND_NAME",
        "DATA_TYPE",
    ],
)

SOURCE_BUCKET = args["SOURCE_BUCKET"]
SOURCE_PREFIX = args["SOURCE_PREFIX"]
TARGET_BUCKET = args["TARGET_BUCKET"]
TARGET_PREFIX = args["TARGET_PREFIX"]
POND_NAME = args["POND_NAME"]
DATA_TYPE = args["DATA_TYPE"]

# Construct S3 paths
source_path = f"s3://{SOURCE_BUCKET}/{SOURCE_PREFIX}"
target_path = f"s3://{TARGET_BUCKET}/{TARGET_PREFIX}"

print(f"=" * 80)
print(f"JSON Array to JSON Lines Converter")
print(f"=" * 80)
print(f"Pond: {POND_NAME}")
print(f"Data Type: {DATA_TYPE}")
print(f"Source: {source_path}")
print(f"Target: {target_path}")
print(f"=" * 80)

# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

# Define schemas for different data types
SCHEMAS = {
    "atmospheric_observations": StructType(
        [
            StructField("station_id", StringType(), True),
            StructField("hour", StringType(), True),
            StructField("observation_count", IntegerType(), True),
            StructField("avg_temperature", DoubleType(), True),
            StructField("max_temperature", DoubleType(), True),
            StructField("min_temperature", DoubleType(), True),
            StructField("avg_wind_speed", DoubleType(), True),
            StructField("max_wind_speed", DoubleType(), True),
            StructField("data_quality_score", DoubleType(), True),
            StructField("ingestion_timestamp", StringType(), True),
        ]
    ),
    "atmospheric_stations": StructType(
        [
            StructField("station_id", StringType(), True),
            StructField("name", StringType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("elevation", DoubleType(), True),
            StructField("timezone", StringType(), True),
            StructField("county", StringType(), True),
            StructField("state", StringType(), True),
            StructField("ingestion_timestamp", StringType(), True),
        ]
    ),
    "atmospheric_alerts": StructType(
        [
            StructField("alert_id", StringType(), True),
            StructField("event", StringType(), True),
            StructField("headline", StringType(), True),
            StructField("severity", StringType(), True),
            StructField("certainty", StringType(), True),
            StructField("urgency", StringType(), True),
            StructField("areas", StringType(), True),
            StructField("onset", StringType(), True),
            StructField("expires", StringType(), True),
            StructField("description", StringType(), True),
            StructField("instruction", StringType(), True),
            StructField("ingestion_timestamp", StringType(), True),
        ]
    ),
    "oceanic": StructType(
        [
            StructField("station_id", StringType(), True),
            StructField("product", StringType(), True),
            StructField("hour", StringType(), True),
            StructField("observation_count", IntegerType(), True),
            StructField("avg_value", DoubleType(), True),
            StructField("max_value", DoubleType(), True),
            StructField("min_value", DoubleType(), True),
            StructField("verified_count", IntegerType(), True),
            StructField("data_quality_score", DoubleType(), True),
            StructField("ingestion_timestamp", StringType(), True),
        ]
    ),
    "buoy": StructType(
        [
            StructField("buoy_id", StringType(), True),
            StructField("hour", StringType(), True),
            StructField("observation_count", IntegerType(), True),
            StructField("avg_wave_height", DoubleType(), True),
            StructField("max_wave_height", DoubleType(), True),
            StructField("dominant_wave_period", DoubleType(), True),
            StructField("avg_wind_speed", DoubleType(), True),
            StructField("max_wind_speed", DoubleType(), True),
            StructField("avg_water_temp", DoubleType(), True),
            StructField("avg_air_temp", DoubleType(), True),
            StructField("avg_pressure", DoubleType(), True),
            StructField("data_quality_score", DoubleType(), True),
            StructField("ingestion_timestamp", StringType(), True),
        ]
    ),
    "generic": StructType(
        [
            StructField("data", StringType(), True),
        ]
    ),
}


def get_schema(data_type):
    """Get schema for data type, fallback to generic"""
    schema_key = data_type.replace("-", "_")
    return SCHEMAS.get(schema_key, SCHEMAS["generic"])


# =============================================================================
# SPARK INITIALIZATION
# =============================================================================

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Configure Spark for better JSON handling
spark.conf.set("spark.sql.files.ignoreCorruptFiles", "true")
spark.conf.set("spark.sql.files.ignoreMissingFiles", "true")

# =============================================================================
# DATA PROCESSING
# =============================================================================

print("Reading JSON array files from source...")

try:
    # Read raw text files first
    raw_df = spark.read.text(source_path)

    print(f"Found {raw_df.count()} files to process")

    if raw_df.count() == 0:
        print("WARNING: No files found at source path")
        job.commit()
        sys.exit(0)

    # Add metadata columns from file path
    df_with_path = raw_df.withColumn("source_file", input_file_name())

    # Extract partition information from file path
    df_with_partitions = (
        df_with_path.withColumn(
            "year", regexp_extract(col("source_file"), r"year=(\d+)", 1).cast("int")
        )
        .withColumn(
            "month", regexp_extract(col("source_file"), r"month=(\d+)", 1).cast("int")
        )
        .withColumn(
            "day", regexp_extract(col("source_file"), r"day=(\d+)", 1).cast("int")
        )
    )

    print("Parsing JSON arrays and exploding into individual records...")

    # Get appropriate schema
    schema = get_schema(DATA_TYPE)
    array_schema = ArrayType(schema)

    # Parse JSON arrays
    parsed_df = df_with_partitions.withColumn(
        "json_array", from_json(col("value"), array_schema)
    )

    # Explode array into individual records
    exploded_df = parsed_df.select(
        explode(col("json_array")).alias("record"),
        col("year"),
        col("month"),
        col("day"),
    )

    # Expand record struct into columns
    final_df = exploded_df.select("record.*", "year", "month", "day")

    record_count = final_df.count()
    print(f"Exploded into {record_count} individual records")

    if record_count == 0:
        print("WARNING: No records after explosion - possible schema mismatch")
        print("Sample raw data:")
        raw_df.show(5, truncate=False)
        job.commit()
        sys.exit(0)

    # Show sample data
    print("\nSample converted data:")
    final_df.show(5, truncate=False)
    print(f"\nSchema:")
    final_df.printSchema()

    print(f"\nWriting {record_count} records as JSON Lines to target...")

    # Write as JSON Lines (newline-delimited JSON)
    # Partition by year/month/day for Athena compatibility
    final_df.write.mode("overwrite").partitionBy("year", "month", "day").json(
        target_path
    )

    print("✅ Conversion complete!")
    print(f"   Records processed: {record_count}")
    print(f"   Output location: {target_path}")

    # Commit the job
    job.commit()

except Exception as e:
    print(f"❌ ERROR during processing: {str(e)}")
    import traceback

    traceback.print_exc()
    raise


# =============================================================================
# SUMMARY
# =============================================================================

print(f"\n" + "=" * 80)
print(f"JSON CONVERSION SUMMARY")
print(f"=" * 80)
print(f"Source Path:      {source_path}")
print(f"Target Path:      {target_path}")
print(f"Pond:             {POND_NAME}")
print(f"Data Type:        {DATA_TYPE}")
print(f"Records Converted: {record_count if 'record_count' in locals() else 'N/A'}")
print(f"Status:           ✅ SUCCESS")
print(f"=" * 80)
