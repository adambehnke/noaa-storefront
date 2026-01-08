#!/usr/bin/env python3
"""
NOAA Data Lake - Historical Data Backfill System
Fetches historical data from NOAA endpoints dating back one year
Processes data through Bronze → Silver → Gold medallion architecture

Usage:
    # Backfill all ponds for the last year
    AWS_PROFILE=noaa-target python3 historical_backfill_system.py --ponds all --days-back 365

    # Backfill specific pond for last 90 days
    AWS_PROFILE=noaa-target python3 historical_backfill_system.py --ponds atmospheric --days-back 90

    # Resume from checkpoint
    AWS_PROFILE=noaa-target python3 historical_backfill_system.py --resume

    # Test mode (1 week only)
    AWS_PROFILE=noaa-target python3 historical_backfill_system.py --ponds oceanic --days-back 7 --test
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("backfill.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "noaa-target")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")

# AWS Clients
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
lambda_client = session.client("lambda")
s3_client = session.client("s3")
glue_client = session.client("glue")
athena_client = session.client("athena")

# Account and bucket configuration
ACCOUNT_ID = session.client("sts").get_caller_identity()["Account"]
BUCKET_NAME = f"noaa-federated-lake-{ACCOUNT_ID}-{ENVIRONMENT}"
CHECKPOINT_FILE = "backfill_checkpoint.json"

# Data pond configurations with their Lambda functions
POND_CONFIGS = {
    "atmospheric": {
        "lambda_function": f"noaa-ingest-atmospheric-{ENVIRONMENT}",
        "description": "NWS weather, forecasts, and alerts",
        "api_rate_limit": 12,  # requests per minute
        "chunk_size_days": 7,
        "supports_historical": True,
        "bronze_prefix": "bronze/atmospheric/",
        "silver_prefix": "silver/atmospheric/",
        "gold_prefix": "gold/atmospheric/",
    },
    "oceanic": {
        "lambda_function": f"noaa-ingest-oceanic-{ENVIRONMENT}",
        "description": "CO-OPS tides, water levels, currents",
        "api_rate_limit": 12,
        "chunk_size_days": 7,
        "supports_historical": True,
        "bronze_prefix": "bronze/oceanic/",
        "silver_prefix": "silver/oceanic/",
        "gold_prefix": "gold/oceanic/",
    },
    "buoy": {
        "lambda_function": f"noaa-ingest-buoy-{ENVIRONMENT}",
        "description": "NDBC buoy observations",
        "api_rate_limit": 12,
        "chunk_size_days": 7,
        "supports_historical": True,
        "bronze_prefix": "bronze/buoy/",
        "silver_prefix": "silver/buoy/",
        "gold_prefix": "gold/buoy/",
    },
    "climate": {
        "lambda_function": f"noaa-ingest-climate-{ENVIRONMENT}",
        "description": "NCEI historical climate data",
        "api_rate_limit": 5,
        "chunk_size_days": 30,  # Climate data can do larger chunks
        "supports_historical": True,
        "bronze_prefix": "bronze/climate/",
        "silver_prefix": "silver/climate/",
        "gold_prefix": "gold/climate/",
    },
    "terrestrial": {
        "lambda_function": f"noaa-ingest-terrestrial-{ENVIRONMENT}",
        "description": "USGS stream gauges and land observations",
        "api_rate_limit": 10,
        "chunk_size_days": 7,
        "supports_historical": True,
        "bronze_prefix": "bronze/terrestrial/",
        "silver_prefix": "silver/terrestrial/",
        "gold_prefix": "gold/terrestrial/",
    },
    "spatial": {
        "lambda_function": f"noaa-ingest-spatial-{ENVIRONMENT}",
        "description": "Geographic reference data",
        "api_rate_limit": 5,
        "chunk_size_days": 365,  # Spatial is mostly static
        "supports_historical": False,  # Reference data doesn't need historical
        "bronze_prefix": "bronze/spatial/",
        "silver_prefix": "silver/spatial/",
        "gold_prefix": "gold/spatial/",
    },
}


class BackfillProgress:
    """Track backfill progress with checkpoint capability"""

    def __init__(self, checkpoint_file: str = CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file
        self.progress = self.load_checkpoint()

    def load_checkpoint(self) -> Dict:
        """Load progress from checkpoint file"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
                return self._init_progress()
        return self._init_progress()

    def _init_progress(self) -> Dict:
        """Initialize empty progress structure"""
        return {
            "started_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
            "ponds": {},
            "total_records": 0,
            "total_api_calls": 0,
            "errors": [],
        }

    def save_checkpoint(self):
        """Save current progress to file"""
        self.progress["last_updated"] = datetime.utcnow().isoformat()
        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(self.progress, f, indent=2)
            logger.debug(f"Checkpoint saved to {self.checkpoint_file}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")

    def update_pond_progress(
        self,
        pond: str,
        date_range: Tuple[str, str],
        status: str,
        records: int = 0,
        error: str = None,
    ):
        """Update progress for a specific pond and date range"""
        if pond not in self.progress["ponds"]:
            self.progress["ponds"][pond] = {
                "total_records": 0,
                "completed_ranges": [],
                "failed_ranges": [],
                "last_successful_date": None,
            }

        range_key = f"{date_range[0]}_{date_range[1]}"

        if status == "completed":
            self.progress["ponds"][pond]["completed_ranges"].append(
                {
                    "range": range_key,
                    "start": date_range[0],
                    "end": date_range[1],
                    "records": records,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            self.progress["ponds"][pond]["total_records"] += records
            self.progress["ponds"][pond]["last_successful_date"] = date_range[1]
            self.progress["total_records"] += records
        elif status == "failed":
            self.progress["ponds"][pond]["failed_ranges"].append(
                {
                    "range": range_key,
                    "start": date_range[0],
                    "end": date_range[1],
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            self.progress["errors"].append(
                {
                    "pond": pond,
                    "range": range_key,
                    "error": error,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        self.save_checkpoint()

    def is_range_completed(self, pond: str, date_range: Tuple[str, str]) -> bool:
        """Check if a date range has already been completed"""
        if pond not in self.progress["ponds"]:
            return False

        range_key = f"{date_range[0]}_{date_range[1]}"
        completed = [
            r["range"] for r in self.progress["ponds"][pond].get("completed_ranges", [])
        ]
        return range_key in completed

    def get_summary(self) -> str:
        """Get human-readable progress summary"""
        summary = ["\n" + "=" * 80]
        summary.append("BACKFILL PROGRESS SUMMARY")
        summary.append("=" * 80)
        summary.append(f"Started: {self.progress.get('started_at', 'N/A')}")
        summary.append(f"Last Updated: {self.progress.get('last_updated', 'N/A')}")
        summary.append(f"Total Records: {self.progress.get('total_records', 0):,}")
        summary.append(f"Total API Calls: {self.progress.get('total_api_calls', 0):,}")
        summary.append("")

        for pond, data in self.progress.get("ponds", {}).items():
            summary.append(f"\n{pond.upper()}:")
            summary.append(f"  Records: {data.get('total_records', 0):,}")
            summary.append(
                f"  Completed Ranges: {len(data.get('completed_ranges', []))}"
            )
            summary.append(f"  Failed Ranges: {len(data.get('failed_ranges', []))}")
            summary.append(f"  Last Success: {data.get('last_successful_date', 'N/A')}")

        if self.progress.get("errors"):
            summary.append(f"\nTotal Errors: {len(self.progress['errors'])}")

        summary.append("=" * 80)
        return "\n".join(summary)


class HistoricalBackfiller:
    """Main backfill orchestrator"""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.progress = BackfillProgress()
        self.verify_aws_setup()

    def verify_aws_setup(self):
        """Verify AWS configuration and permissions"""
        try:
            # Verify bucket access
            s3_client.head_bucket(Bucket=BUCKET_NAME)
            logger.info(f"✓ S3 bucket access verified: {BUCKET_NAME}")

            # Verify Lambda access
            lambda_client.list_functions(MaxItems=1)
            logger.info("✓ Lambda access verified")

        except ClientError as e:
            logger.error(f"AWS setup verification failed: {e}")
            raise

    def generate_date_ranges(
        self, days_back: int, chunk_size: int
    ) -> List[Tuple[datetime, datetime]]:
        """Generate date ranges for backfill (working backwards from today)"""
        ranges = []
        end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days_back)

        current_end = end_date
        while current_end > start_date:
            current_start = max(current_end - timedelta(days=chunk_size), start_date)
            ranges.append((current_start, current_end))
            current_end = current_start

        logger.info(f"Generated {len(ranges)} date ranges for backfill")
        return ranges

    def invoke_ingestion_lambda(
        self, pond: str, start_date: datetime, end_date: datetime
    ) -> Dict:
        """Invoke ingestion Lambda for a specific date range"""
        config = POND_CONFIGS[pond]
        lambda_name = config["lambda_function"]

        payload = {
            "env": ENVIRONMENT,
            "mode": "backfill",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

        try:
            logger.info(
                f"Invoking {lambda_name} for {start_date.date()} to {end_date.date()}"
            )

            response = lambda_client.invoke(
                FunctionName=lambda_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            result = json.loads(response["Payload"].read().decode("utf-8"))

            if response["StatusCode"] == 200:
                # Parse Lambda response
                if "body" in result:
                    body = (
                        json.loads(result["body"])
                        if isinstance(result["body"], str)
                        else result["body"]
                    )
                    return {
                        "success": True,
                        "records": body.get("stats", {}).get("bronze_records", 0),
                        "api_calls": body.get("stats", {}).get("apis_called", 0),
                        "response": body,
                    }
                return {"success": True, "records": 0, "api_calls": 1}
            else:
                return {
                    "success": False,
                    "error": result.get("errorMessage", "Unknown error"),
                }

        except Exception as e:
            logger.error(f"Error invoking {lambda_name}: {e}")
            return {"success": False, "error": str(e)}

    def verify_data_in_bronze(
        self, pond: str, start_date: datetime, end_date: datetime
    ) -> int:
        """Verify that data was written to Bronze layer"""
        config = POND_CONFIGS[pond]
        prefix = config["bronze_prefix"]

        # Check for files in the date range
        file_count = 0
        current_date = start_date

        while current_date <= end_date:
            year = current_date.strftime("%Y")
            month = current_date.strftime("%m")
            day = current_date.strftime("%d")

            # Try different path patterns
            patterns = [
                f"{prefix}year={year}/month={month}/day={day}/",
                f"{prefix}date={year}-{month}-{day}/",
            ]

            for pattern in patterns:
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=BUCKET_NAME, Prefix=pattern, MaxKeys=10
                    )
                    file_count += len(response.get("Contents", []))
                    if file_count > 0:
                        break
                except ClientError:
                    continue

            current_date += timedelta(days=1)

        logger.info(f"Found {file_count} files in Bronze layer for {pond}")
        return file_count

    def trigger_silver_transformation(
        self, pond: str, date_range: Tuple[datetime, datetime]
    ):
        """Trigger Glue ETL job for Silver layer transformation"""
        job_name = f"noaa-{pond}-bronze-to-silver-{ENVIRONMENT}"

        try:
            # Check if job exists
            glue_client.get_job(JobName=job_name)

            # Trigger job
            response = glue_client.start_job_run(
                JobName=job_name,
                Arguments={
                    "--start_date": date_range[0].strftime("%Y-%m-%d"),
                    "--end_date": date_range[1].strftime("%Y-%m-%d"),
                },
            )

            logger.info(
                f"Started Silver transformation job {job_name}: {response['JobRunId']}"
            )
            return response["JobRunId"]

        except glue_client.exceptions.EntityNotFoundException:
            logger.warning(
                f"Glue job {job_name} not found - Silver transformation skipped"
            )
            return None
        except Exception as e:
            logger.error(f"Error triggering Silver transformation: {e}")
            return None

    def trigger_gold_aggregation(
        self, pond: str, date_range: Tuple[datetime, datetime]
    ):
        """Trigger Glue ETL job for Gold layer aggregation"""
        job_name = f"noaa-{pond}-silver-to-gold-{ENVIRONMENT}"

        try:
            # Check if job exists
            glue_client.get_job(JobName=job_name)

            # Trigger job
            response = glue_client.start_job_run(
                JobName=job_name,
                Arguments={
                    "--start_date": date_range[0].strftime("%Y-%m-%d"),
                    "--end_date": date_range[1].strftime("%Y-%m-%d"),
                },
            )

            logger.info(
                f"Started Gold aggregation job {job_name}: {response['JobRunId']}"
            )
            return response["JobRunId"]

        except glue_client.exceptions.EntityNotFoundException:
            logger.warning(f"Glue job {job_name} not found - Gold aggregation skipped")
            return None
        except Exception as e:
            logger.error(f"Error triggering Gold aggregation: {e}")
            return None

    def backfill_pond(self, pond: str, days_back: int):
        """Backfill historical data for a single pond"""
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Starting backfill for {pond.upper()} pond")
        logger.info(f"{'=' * 80}")

        config = POND_CONFIGS[pond]

        if not config["supports_historical"]:
            logger.info(f"{pond} does not support historical backfill - skipping")
            return

        # Generate date ranges
        chunk_size = config["chunk_size_days"]
        date_ranges = self.generate_date_ranges(days_back, chunk_size)

        total_ranges = len(date_ranges)
        completed = 0
        failed = 0

        for idx, (start_date, end_date) in enumerate(date_ranges, 1):
            range_tuple = (
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            # Check if already completed
            if self.progress.is_range_completed(pond, range_tuple):
                logger.info(
                    f"[{idx}/{total_ranges}] Skipping {range_tuple} (already completed)"
                )
                completed += 1
                continue

            logger.info(
                f"\n[{idx}/{total_ranges}] Processing {pond}: {range_tuple[0]} to {range_tuple[1]}"
            )

            # Invoke ingestion Lambda
            result = self.invoke_ingestion_lambda(pond, start_date, end_date)

            if result["success"]:
                records = result.get("records", 0)
                api_calls = result.get("api_calls", 0)

                logger.info(
                    f"✓ Bronze ingestion successful: {records} records, {api_calls} API calls"
                )

                # Verify data in Bronze
                bronze_files = self.verify_data_in_bronze(pond, start_date, end_date)

                if bronze_files > 0:
                    # Trigger Silver transformation
                    silver_job = self.trigger_silver_transformation(
                        pond, (start_date, end_date)
                    )

                    # Trigger Gold aggregation
                    gold_job = self.trigger_gold_aggregation(
                        pond, (start_date, end_date)
                    )

                    # Update progress
                    self.progress.update_pond_progress(
                        pond, range_tuple, "completed", records=records
                    )
                    self.progress.progress["total_api_calls"] += api_calls

                    completed += 1
                    logger.info(f"✓ Range completed: {records} records ingested")
                else:
                    logger.warning(
                        f"No data found in Bronze layer - may be expected for this date range"
                    )
                    self.progress.update_pond_progress(
                        pond, range_tuple, "completed", records=0
                    )
                    completed += 1
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"✗ Bronze ingestion failed: {error}")
                self.progress.update_pond_progress(
                    pond, range_tuple, "failed", error=error
                )
                failed += 1

            # Rate limiting
            rate_limit = config["api_rate_limit"]
            sleep_time = 60.0 / rate_limit
            if idx < total_ranges:  # Don't sleep after last range
                logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)

            # Save progress periodically
            if idx % 5 == 0:
                logger.info(self.progress.get_summary())

        logger.info(f"\n{pond.upper()} backfill complete:")
        logger.info(f"  Completed: {completed}/{total_ranges}")
        logger.info(f"  Failed: {failed}/{total_ranges}")

    def backfill_all_ponds(self, ponds: List[str], days_back: int):
        """Backfill all specified ponds"""
        start_time = datetime.utcnow()

        logger.info(f"\n{'=' * 80}")
        logger.info(f"NOAA HISTORICAL DATA BACKFILL")
        logger.info(f"{'=' * 80}")
        logger.info(f"Account: {ACCOUNT_ID}")
        logger.info(f"Bucket: {BUCKET_NAME}")
        logger.info(f"Ponds: {', '.join(ponds)}")
        logger.info(f"Days back: {days_back}")
        logger.info(f"Test mode: {self.test_mode}")
        logger.info(f"{'=' * 80}\n")

        for pond in ponds:
            try:
                self.backfill_pond(pond, days_back)
            except Exception as e:
                logger.error(f"Error backfilling {pond}: {e}", exc_info=True)
                continue

        # Final summary
        end_time = datetime.utcnow()
        duration = end_time - start_time

        logger.info(f"\n{'=' * 80}")
        logger.info(f"BACKFILL COMPLETE")
        logger.info(f"{'=' * 80}")
        logger.info(f"Duration: {duration}")
        logger.info(self.progress.get_summary())

        # Save final checkpoint
        self.progress.save_checkpoint()

        return self.progress


def main():
    parser = argparse.ArgumentParser(
        description="NOAA Historical Data Backfill System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill all ponds for the last year
  python3 historical_backfill_system.py --ponds all --days-back 365

  # Backfill specific pond for last 90 days
  python3 historical_backfill_system.py --ponds atmospheric --days-back 90

  # Resume from checkpoint
  python3 historical_backfill_system.py --resume

  # Test mode (7 days only)
  python3 historical_backfill_system.py --ponds oceanic --days-back 7 --test
        """,
    )

    parser.add_argument(
        "--ponds",
        type=str,
        nargs="+",
        choices=list(POND_CONFIGS.keys()) + ["all"],
        default=["all"],
        help="Data ponds to backfill (default: all)",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="Number of days to backfill (default: 365)",
    )

    parser.add_argument(
        "--resume", action="store_true", help="Resume from previous checkpoint"
    )

    parser.add_argument(
        "--test", action="store_true", help="Test mode - only backfill 7 days"
    )

    parser.add_argument(
        "--checkpoint-file",
        type=str,
        default=CHECKPOINT_FILE,
        help=f"Checkpoint file path (default: {CHECKPOINT_FILE})",
    )

    args = parser.parse_args()

    # Resolve ponds
    if "all" in args.ponds:
        ponds = [
            p for p in POND_CONFIGS.keys() if POND_CONFIGS[p]["supports_historical"]
        ]
    else:
        ponds = args.ponds

    # Override days_back in test mode
    if args.test:
        args.days_back = 7
        logger.info("Test mode: limiting backfill to 7 days")

    # Create backfiller
    backfiller = HistoricalBackfiller(test_mode=args.test)

    # Run backfill
    try:
        backfiller.backfill_all_ponds(ponds, args.days_back)
    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        logger.info("Progress saved to checkpoint. Use --resume to continue.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
