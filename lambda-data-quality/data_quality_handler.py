"""
NOAA Federated Data Lake - Data Quality Handler for Silver Layer

This Lambda function validates and transforms data from the Bronze layer
into the Silver layer with comprehensive data quality checks.

Quality Checks Performed:
- Completeness: Required fields present and non-null
- Accuracy: Values within expected ranges
- Consistency: Data types and formats correct
- Timeliness: Timestamps recent and valid
- Uniqueness: Duplicate detection and removal
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

# Environment variables
DATA_LAKE_BUCKET = os.environ.get(
    "DATA_LAKE_BUCKET", "noaa-federated-lake-899626030376-dev"
)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# Quality thresholds
COMPLETENESS_THRESHOLD = 0.95  # 95% of required fields must be present
ACCURACY_THRESHOLD = 0.98  # 98% of values must be within valid ranges
TIMELINESS_MAX_AGE_HOURS = 24  # Data must be less than 24 hours old


class DataQualityMetrics:
    """Track data quality metrics"""

    def __init__(self, pond: str, layer: str):
        self.pond = pond
        self.layer = layer
        self.total_records = 0
        self.valid_records = 0
        self.invalid_records = 0
        self.duplicate_records = 0
        self.null_field_count = 0
        self.out_of_range_count = 0
        self.type_error_count = 0
        self.timestamp_error_count = 0

    def calculate_quality_score(self) -> float:
        """Calculate overall quality score (0-100)"""
        if self.total_records == 0:
            return 0.0

        completeness = (self.total_records - self.null_field_count) / self.total_records
        accuracy = (self.total_records - self.out_of_range_count) / self.total_records
        validity = self.valid_records / self.total_records

        # Weighted average
        quality_score = (completeness * 0.3 + accuracy * 0.4 + validity * 0.3) * 100

        return round(quality_score, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "pond": self.pond,
            "layer": self.layer,
            "timestamp": datetime.utcnow().isoformat(),
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "duplicate_records": self.duplicate_records,
            "null_field_count": self.null_field_count,
            "out_of_range_count": self.out_of_range_count,
            "type_error_count": self.type_error_count,
            "timestamp_error_count": self.timestamp_error_count,
            "quality_score": self.calculate_quality_score(),
        }


class DataQualityValidator:
    """Data quality validation rules"""

    def __init__(self, pond: str):
        self.pond = pond
        self.seen_hashes = set()

    def check_completeness(
        self, record: Dict, required_fields: List[str]
    ) -> Tuple[bool, List[str]]:
        """Check if all required fields are present and non-null"""
        missing_fields = []

        for field in required_fields:
            if field not in record or record[field] is None or record[field] == "":
                missing_fields.append(field)

        is_complete = len(missing_fields) == 0
        return is_complete, missing_fields

    def check_accuracy(
        self, record: Dict, validation_rules: Dict
    ) -> Tuple[bool, List[str]]:
        """Check if values are within expected ranges"""
        violations = []

        for field, rules in validation_rules.items():
            if field not in record:
                continue

            value = record[field]

            # Check numeric ranges
            if "min" in rules and isinstance(value, (int, float)):
                if value < rules["min"]:
                    violations.append(
                        f"{field} below minimum: {value} < {rules['min']}"
                    )

            if "max" in rules and isinstance(value, (int, float)):
                if value > rules["max"]:
                    violations.append(
                        f"{field} above maximum: {value} > {rules['max']}"
                    )

            # Check string patterns
            if "pattern" in rules and isinstance(value, str):
                import re

                if not re.match(rules["pattern"], value):
                    violations.append(f"{field} doesn't match pattern: {value}")

            # Check enum values
            if "enum" in rules:
                if value not in rules["enum"]:
                    violations.append(f"{field} not in allowed values: {value}")

        is_accurate = len(violations) == 0
        return is_accurate, violations

    def check_timeliness(self, record: Dict, timestamp_field: str) -> Tuple[bool, str]:
        """Check if data is recent enough"""
        if timestamp_field not in record:
            return False, f"Missing timestamp field: {timestamp_field}"

        try:
            # Parse timestamp
            timestamp_str = record[timestamp_field]

            # Try different timestamp formats
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    timestamp = datetime.strptime(timestamp_str.split(".")[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return False, f"Invalid timestamp format: {timestamp_str}"

            # Check if data is recent
            age = datetime.utcnow() - timestamp
            if age > timedelta(hours=TIMELINESS_MAX_AGE_HOURS):
                return False, f"Data too old: {age.total_seconds() / 3600:.1f} hours"

            return True, ""

        except Exception as e:
            return False, f"Timestamp validation error: {str(e)}"

    def check_uniqueness(self, record: Dict, unique_fields: List[str]) -> bool:
        """Check if record is unique based on specified fields"""
        # Create hash of unique field values
        unique_str = "|".join(str(record.get(field, "")) for field in unique_fields)
        record_hash = hashlib.md5(unique_str.encode()).hexdigest()

        if record_hash in self.seen_hashes:
            return False  # Duplicate

        self.seen_hashes.add(record_hash)
        return True  # Unique

    def validate_types(self, record: Dict, type_schema: Dict) -> Tuple[bool, List[str]]:
        """Validate data types match schema"""
        type_errors = []

        for field, expected_type in type_schema.items():
            if field not in record:
                continue

            value = record[field]

            if expected_type == "string" and not isinstance(value, str):
                type_errors.append(
                    f"{field} should be string, got {type(value).__name__}"
                )
            elif expected_type == "number" and not isinstance(
                value, (int, float, Decimal)
            ):
                type_errors.append(
                    f"{field} should be number, got {type(value).__name__}"
                )
            elif expected_type == "boolean" and not isinstance(value, bool):
                type_errors.append(
                    f"{field} should be boolean, got {type(value).__name__}"
                )

        is_valid = len(type_errors) == 0
        return is_valid, type_errors


def get_validation_rules(pond: str) -> Dict:
    """Get validation rules for each pond"""

    rules = {
        "atmospheric": {
            "required_fields": ["station_id", "timestamp", "temperature"],
            "validation_rules": {
                "temperature": {"min": -100, "max": 150},  # Fahrenheit
                "wind_speed": {"min": 0, "max": 300},
                "barometric_pressure": {"min": 800, "max": 1100},
                "relative_humidity": {"min": 0, "max": 100},
            },
            "timestamp_field": "timestamp",
            "unique_fields": ["station_id", "timestamp"],
            "type_schema": {
                "station_id": "string",
                "timestamp": "string",
                "temperature": "number",
                "wind_speed": "number",
            },
        },
        "oceanic": {
            "required_fields": ["station_id", "timestamp"],
            "validation_rules": {
                "water_temperature": {"min": -5, "max": 120},  # Fahrenheit
                "wave_height": {"min": 0, "max": 100},
                "water_level": {"min": -50, "max": 50},
            },
            "timestamp_field": "timestamp",
            "unique_fields": ["station_id", "timestamp"],
            "type_schema": {"station_id": "string", "timestamp": "string"},
        },
        "buoy": {
            "required_fields": ["buoy_id", "timestamp"],
            "validation_rules": {
                "wave_height": {"min": 0, "max": 100},
                "wave_period": {"min": 0, "max": 30},
                "wind_speed": {"min": 0, "max": 300},
            },
            "timestamp_field": "timestamp",
            "unique_fields": ["buoy_id", "timestamp"],
            "type_schema": {"buoy_id": "string", "timestamp": "string"},
        },
        "climate": {
            "required_fields": ["station_id", "date"],
            "validation_rules": {
                "temperature_avg": {"min": -100, "max": 150},
                "precipitation": {"min": 0, "max": 100},
            },
            "timestamp_field": "date",
            "unique_fields": ["station_id", "date"],
            "type_schema": {"station_id": "string", "date": "string"},
        },
        "terrestrial": {
            "required_fields": ["site_id", "timestamp"],
            "validation_rules": {
                "flow_rate": {"min": 0, "max": 1000000},
                "gage_height": {"min": -50, "max": 100},
            },
            "timestamp_field": "timestamp",
            "unique_fields": ["site_id", "timestamp"],
            "type_schema": {"site_id": "string", "timestamp": "string"},
        },
        "spatial": {
            "required_fields": ["id", "timestamp"],
            "validation_rules": {},
            "timestamp_field": "timestamp",
            "unique_fields": ["id", "timestamp"],
            "type_schema": {"id": "string", "timestamp": "string"},
        },
    }

    return rules.get(pond, rules["atmospheric"])  # Default to atmospheric


def process_records(
    records: List[Dict], pond: str
) -> Tuple[List[Dict], DataQualityMetrics]:
    """Process and validate records"""

    validator = DataQualityValidator(pond)
    metrics = DataQualityMetrics(pond, "silver")
    rules = get_validation_rules(pond)

    valid_records = []

    for record in records:
        metrics.total_records += 1
        is_valid = True
        validation_issues = []

        # Check completeness
        complete, missing = validator.check_completeness(
            record, rules["required_fields"]
        )
        if not complete:
            is_valid = False
            metrics.null_field_count += 1
            validation_issues.append(f"Missing fields: {missing}")

        # Check accuracy
        accurate, violations = validator.check_accuracy(
            record, rules["validation_rules"]
        )
        if not accurate:
            is_valid = False
            metrics.out_of_range_count += 1
            validation_issues.extend(violations)

        # Check types
        types_valid, type_errors = validator.validate_types(
            record, rules["type_schema"]
        )
        if not types_valid:
            is_valid = False
            metrics.type_error_count += 1
            validation_issues.extend(type_errors)

        # Check timeliness
        timely, time_error = validator.check_timeliness(
            record, rules["timestamp_field"]
        )
        if not timely:
            # Don't fail on timeliness for historical data, just log
            logger.warning(f"Timeliness issue: {time_error}")
            metrics.timestamp_error_count += 1

        # Check uniqueness
        unique = validator.check_uniqueness(record, rules["unique_fields"])
        if not unique:
            is_valid = False
            metrics.duplicate_records += 1
            validation_issues.append("Duplicate record")

        # Add validation metadata
        record["_data_quality"] = {
            "validated_at": datetime.utcnow().isoformat(),
            "is_valid": is_valid,
            "validation_issues": validation_issues if not is_valid else [],
            "pond": pond,
            "layer": "silver",
        }

        if is_valid:
            metrics.valid_records += 1
            valid_records.append(record)
        else:
            metrics.invalid_records += 1
            logger.warning(f"Invalid record: {validation_issues}")

    return valid_records, metrics


def publish_metrics(metrics: DataQualityMetrics):
    """Publish quality metrics to CloudWatch"""

    try:
        namespace = "NOAA/DataQuality"
        dimensions = [
            {"Name": "Pond", "Value": metrics.pond},
            {"Name": "Layer", "Value": metrics.layer},
            {"Name": "Environment", "Value": ENVIRONMENT},
        ]

        metric_data = [
            {
                "MetricName": "QualityScore",
                "Value": metrics.calculate_quality_score(),
                "Unit": "Percent",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "TotalRecords",
                "Value": metrics.total_records,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "ValidRecords",
                "Value": metrics.valid_records,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "InvalidRecords",
                "Value": metrics.invalid_records,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
            {
                "MetricName": "DuplicateRecords",
                "Value": metrics.duplicate_records,
                "Unit": "Count",
                "Dimensions": dimensions,
            },
        ]

        cloudwatch.put_metric_data(Namespace=namespace, MetricData=metric_data)

        logger.info(f"Published {len(metric_data)} metrics to CloudWatch")

    except Exception as e:
        logger.error(f"Error publishing metrics: {str(e)}")


def lambda_handler(event, context):
    """
    Main Lambda handler for data quality processing

    Event format:
    {
        "pond": "atmospheric",
        "bronze_key": "bronze/atmospheric/...",
        "silver_key": "silver/atmospheric/..."
    }
    """

    try:
        logger.info(f"Data Quality Handler invoked with event: {json.dumps(event)}")

        # Extract parameters
        pond = event.get("pond", "atmospheric")
        bronze_key = event.get("bronze_key")
        silver_key = event.get("silver_key")

        if not bronze_key:
            raise ValueError("bronze_key is required")

        # Generate silver key if not provided
        if not silver_key:
            silver_key = bronze_key.replace("/bronze/", "/silver/")

        # Read Bronze data
        logger.info(f"Reading from Bronze: s3://{DATA_LAKE_BUCKET}/{bronze_key}")

        try:
            response = s3_client.get_object(Bucket=DATA_LAKE_BUCKET, Key=bronze_key)
            bronze_data = json.loads(response["Body"].read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Error reading Bronze data: {str(e)}")
            raise

        # Handle both single record and array of records
        if isinstance(bronze_data, dict):
            records = [bronze_data]
        elif isinstance(bronze_data, list):
            records = bronze_data
        else:
            raise ValueError(f"Unexpected data format: {type(bronze_data)}")

        logger.info(f"Processing {len(records)} records from {pond} pond")

        # Process and validate records
        valid_records, metrics = process_records(records, pond)

        # Log quality metrics
        quality_score = metrics.calculate_quality_score()
        logger.info(f"Data Quality Score: {quality_score}%")
        logger.info(f"Valid: {metrics.valid_records}/{metrics.total_records} records")
        logger.info(f"Duplicates removed: {metrics.duplicate_records}")

        # Check if quality meets threshold
        if quality_score < (COMPLETENESS_THRESHOLD * 100):
            logger.warning(
                f"Quality score {quality_score}% below threshold {COMPLETENESS_THRESHOLD * 100}%"
            )

        # Write to Silver layer
        if valid_records:
            logger.info(
                f"Writing {len(valid_records)} records to Silver: s3://{DATA_LAKE_BUCKET}/{silver_key}"
            )

            s3_client.put_object(
                Bucket=DATA_LAKE_BUCKET,
                Key=silver_key,
                Body=json.dumps(valid_records, indent=2, default=str),
                ContentType="application/json",
                Metadata={
                    "pond": pond,
                    "layer": "silver",
                    "quality_score": str(quality_score),
                    "validated_at": datetime.utcnow().isoformat(),
                },
            )

            logger.info("Successfully wrote to Silver layer")
        else:
            logger.warning("No valid records to write to Silver layer")

        # Publish metrics to CloudWatch
        publish_metrics(metrics)

        # Write quality report
        quality_report_key = silver_key.replace(".json", "_quality_report.json")
        s3_client.put_object(
            Bucket=DATA_LAKE_BUCKET,
            Key=quality_report_key,
            Body=json.dumps(metrics.to_dict(), indent=2),
            ContentType="application/json",
        )

        # Return summary
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Data quality processing completed",
                    "pond": pond,
                    "bronze_key": bronze_key,
                    "silver_key": silver_key,
                    "quality_report_key": quality_report_key,
                    "metrics": metrics.to_dict(),
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in data quality handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(e), "message": "Data quality processing failed"}
            ),
        }
