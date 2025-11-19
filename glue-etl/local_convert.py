#!/usr/bin/env python3
"""
Local JSON Array to JSON Lines Converter for NOAA Data Lake

This script converts JSON array files to JSON Lines format for Athena compatibility.
Runs locally without requiring AWS Glue infrastructure.

Usage:
    python local_convert.py --pond atmospheric --data-type observations
    python local_convert.py --pond oceanic --data-type all
    python local_convert.py --help

Author: NOAA Federated Data Lake Team
Version: 1.0
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Configuration
DEFAULT_ENV = "dev"
DEFAULT_REGION = "us-east-1"


class JSONArrayConverter:
    """Converts JSON arrays to JSON Lines format"""

    def __init__(self, environment="dev", region="us-east-1", dry_run=False):
        self.environment = environment
        self.region = region
        self.dry_run = dry_run
        self.s3_client = boto3.client("s3", region_name=region)
        self.bucket = f"noaa-data-lake-{environment}"

        self.stats = {
            "files_processed": 0,
            "files_failed": 0,
            "records_converted": 0,
            "bytes_written": 0,
        }

    def list_source_files(self, pond, data_type=None):
        """List all JSON files in the Gold layer for conversion"""
        if data_type and data_type != "all":
            prefix = f"gold/{pond}/{data_type}/"
        else:
            prefix = f"gold/{pond}/"

        print(f"📂 Scanning: s3://{self.bucket}/{prefix}")

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)

            files = []
            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.endswith(".json") and "/data_" in key:
                        files.append(key)

            print(f"   Found {len(files)} JSON files to convert")
            return files

        except ClientError as e:
            print(f"❌ Error listing files: {e}")
            return []

    def download_and_parse(self, key):
        """Download JSON file and parse as array"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")

            # Parse JSON array
            data = json.loads(content)

            if isinstance(data, list):
                return data
            else:
                print(f"   ⚠ File is not a JSON array: {key}")
                return []

        except json.JSONDecodeError as e:
            print(f"   ⚠ JSON parse error in {key}: {e}")
            return []
        except ClientError as e:
            print(f"   ⚠ S3 download error for {key}: {e}")
            return []

    def extract_partition_info(self, key):
        """Extract year/month/day from S3 key path"""
        parts = {}

        # Extract from path like: gold/pond/type/year=2025/month=11/day=17/file.json
        if "year=" in key:
            parts["year"] = key.split("year=")[1].split("/")[0]
        if "month=" in key:
            parts["month"] = key.split("month=")[1].split("/")[0]
        if "day=" in key:
            parts["day"] = key.split("day=")[1].split("/")[0]

        return parts

    def convert_to_jsonlines(self, records):
        """Convert list of records to JSON Lines format"""
        lines = []
        for record in records:
            line = json.dumps(record, separators=(",", ":"))
            lines.append(line)

        return "\n".join(lines) + "\n"

    def build_target_key(self, source_key, partition_info):
        """Build target S3 key for queryable data"""
        # Extract pond and data type from source path
        # Format: gold/pond/type/year=.../data_*.json
        parts = source_key.split("/")

        pond = parts[1]  # atmospheric, oceanic, etc.

        # Handle different path structures
        if "year=" in source_key:
            # Has partitions: gold/pond/type/year=.../
            data_type = parts[2]
        else:
            # No partitions: gold/pond/data_*.json
            data_type = "data"

        # Build target key with partitions
        target_key = f"queryable/{pond}/{data_type}/"

        if partition_info:
            if "year" in partition_info:
                target_key += f"year={partition_info['year']}/"
            if "month" in partition_info:
                target_key += f"month={partition_info['month']}/"
            if "day" in partition_info:
                target_key += f"day={partition_info['day']}/"

        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target_key += f"part-{timestamp}.json"

        return target_key

    def upload_jsonlines(self, content, target_key):
        """Upload JSON Lines content to S3"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=target_key,
                Body=content.encode("utf-8"),
                ContentType="application/json",
            )
            return True
        except ClientError as e:
            print(f"   ❌ Upload failed: {e}")
            return False

    def convert_file(self, source_key):
        """Convert a single file from JSON array to JSON Lines"""
        print(f"   📄 {source_key}")

        # Download and parse
        records = self.download_and_parse(source_key)

        if not records:
            self.stats["files_failed"] += 1
            return False

        # Extract partition info
        partition_info = self.extract_partition_info(source_key)

        # Convert to JSON Lines
        jsonlines_content = self.convert_to_jsonlines(records)

        # Build target key
        target_key = self.build_target_key(source_key, partition_info)

        if self.dry_run:
            print(
                f"      [DRY RUN] Would write {len(records)} records to: {target_key}"
            )
            self.stats["files_processed"] += 1
            self.stats["records_converted"] += len(records)
            return True

        # Upload
        if self.upload_jsonlines(jsonlines_content, target_key):
            bytes_written = len(jsonlines_content.encode("utf-8"))
            self.stats["files_processed"] += 1
            self.stats["records_converted"] += len(records)
            self.stats["bytes_written"] += bytes_written

            print(
                f"      ✓ Converted {len(records)} records → {target_key} ({bytes_written:,} bytes)"
            )
            return True
        else:
            self.stats["files_failed"] += 1
            return False

    def convert_pond(self, pond, data_type=None, max_files=None):
        """Convert all files in a pond"""
        print(f"\n{'=' * 70}")
        print(f"Converting: {pond.upper()} Pond")
        if data_type:
            print(f"Data Type:  {data_type}")
        print(f"{'=' * 70}\n")

        # List source files
        source_files = self.list_source_files(pond, data_type)

        if not source_files:
            print("⚠ No files found to convert")
            return

        # Limit files if specified
        if max_files:
            source_files = source_files[:max_files]
            print(f"   (Limited to first {max_files} files)")

        print(f"\n🔄 Converting {len(source_files)} files...\n")

        # Convert each file
        for i, source_key in enumerate(source_files, 1):
            print(f"[{i}/{len(source_files)}]", end=" ")
            self.convert_file(source_key)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print conversion summary"""
        print(f"\n{'=' * 70}")
        print(f"CONVERSION SUMMARY")
        print(f"{'=' * 70}")
        print(f"Files Processed:    {self.stats['files_processed']}")
        print(f"Files Failed:       {self.stats['files_failed']}")
        print(f"Records Converted:  {self.stats['records_converted']:,}")
        print(f"Bytes Written:      {self.stats['bytes_written']:,}")
        print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert NOAA JSON arrays to JSON Lines format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert atmospheric observations
  python local_convert.py --pond atmospheric --data-type observations

  # Convert all oceanic data
  python local_convert.py --pond oceanic --data-type all

  # Dry run (don't upload)
  python local_convert.py --pond atmospheric --dry-run

  # Convert only first 10 files (for testing)
  python local_convert.py --pond atmospheric --max-files 10

  # Convert multiple ponds
  python local_convert.py --pond atmospheric --pond oceanic --data-type all
        """,
    )

    parser.add_argument(
        "--pond",
        action="append",
        required=True,
        choices=["atmospheric", "oceanic", "buoy", "climate", "spatial", "terrestrial"],
        help="Pond(s) to convert (can specify multiple)",
    )

    parser.add_argument(
        "--data-type",
        default="all",
        help="Specific data type to convert (e.g., observations, stations, alerts) or 'all'",
    )

    parser.add_argument(
        "--environment",
        "--env",
        default=DEFAULT_ENV,
        help=f"Environment (default: {DEFAULT_ENV})",
    )

    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region (default: {DEFAULT_REGION})",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum number of files to convert (for testing)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without uploading",
    )

    args = parser.parse_args()

    # Print header
    print("\n" + "=" * 70)
    print(" NOAA JSON Array → JSON Lines Converter")
    print("=" * 70)
    print(f"Environment:  {args.environment}")
    print(f"Region:       {args.region}")
    print(f"Dry Run:      {args.dry_run}")
    print("=" * 70)

    # Create converter
    converter = JSONArrayConverter(
        environment=args.environment, region=args.region, dry_run=args.dry_run
    )

    # Convert each pond
    for pond in args.pond:
        try:
            converter.convert_pond(pond, args.data_type, args.max_files)
        except KeyboardInterrupt:
            print("\n\n⚠ Interrupted by user")
            converter.print_summary()
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error converting {pond}: {e}")
            import traceback

            traceback.print_exc()

    print("\n✅ All conversions complete!\n")
    print("Next steps:")
    print(f"  1. Run Glue crawlers to catalog the queryable data")
    print(f"  2. Query via Athena using database: noaa_queryable_{args.environment}")
    print()


if __name__ == "__main__":
    main()
