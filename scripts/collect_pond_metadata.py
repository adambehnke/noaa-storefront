#!/usr/bin/env python3
"""
Collect metadata about NOAA Data Lake ponds from S3
Gathers freshness, file counts, sizes, and ingestion statistics

Usage:
    python collect_pond_metadata.py --profile noaa-target --output pond_metadata.json
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3

# S3 bucket configuration
BUCKET_NAME = "noaa-federated-lake-899626030376-dev"
PONDS = ["atmospheric", "oceanic", "buoy", "climate", "spatial", "terrestrial"]

# Layer prefixes
LAYERS = ["bronze", "silver", "gold"]


def get_s3_client(profile=None):
    """Get configured S3 client"""
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    return session.client("s3")


def analyze_pond(s3_client, bucket, pond):
    """
    Analyze a single pond across all layers

    Returns metadata including:
    - Total files
    - Total size
    - Latest file timestamp (data freshness)
    - File breakdown by layer
    - Endpoint statistics
    """
    print(f"  Analyzing {pond} pond...")

    pond_metadata = {
        "pond_name": pond,
        "layers": {},
        "total_files": 0,
        "total_size_bytes": 0,
        "total_size_mb": 0,
        "latest_ingestion": None,
        "oldest_ingestion": None,
        "endpoints": {},
        "status": "active",
    }

    all_timestamps = []

    # Analyze each layer
    for layer in LAYERS:
        prefix = f"{layer}/{pond}/"
        layer_data = {
            "file_count": 0,
            "size_bytes": 0,
            "size_mb": 0,
            "latest_file": None,
            "oldest_file": None,
            "endpoints": {},
        }

        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            layer_timestamps = []
            endpoint_stats = defaultdict(
                lambda: {"count": 0, "size": 0, "latest": None}
            )

            for page in pages:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    size = obj["Size"]
                    modified = obj["LastModified"]

                    # Skip directories
                    if key.endswith("/"):
                        continue

                    layer_data["file_count"] += 1
                    layer_data["size_bytes"] += size
                    layer_timestamps.append(modified)
                    all_timestamps.append(modified)

                    # Extract endpoint from path
                    # Format: layer/pond/endpoint=xxx/...
                    parts = key.split("/")
                    endpoint = "unknown"
                    for part in parts:
                        if part.startswith("endpoint="):
                            endpoint = part.split("=")[1]
                            break
                        elif part.startswith("service="):
                            endpoint = part.split("=")[1]
                            break

                    # Track endpoint statistics
                    endpoint_stats[endpoint]["count"] += 1
                    endpoint_stats[endpoint]["size"] += size
                    if (
                        endpoint_stats[endpoint]["latest"] is None
                        or modified > endpoint_stats[endpoint]["latest"]
                    ):
                        endpoint_stats[endpoint]["latest"] = modified

            # Calculate layer statistics
            if layer_timestamps:
                layer_data["latest_file"] = max(layer_timestamps).isoformat()
                layer_data["oldest_file"] = min(layer_timestamps).isoformat()
                layer_data["size_mb"] = round(
                    layer_data["size_bytes"] / (1024 * 1024), 2
                )

            # Store endpoint statistics
            layer_data["endpoints"] = {
                ep: {
                    "file_count": stats["count"],
                    "size_mb": round(stats["size"] / (1024 * 1024), 2),
                    "latest_ingestion": stats["latest"].isoformat()
                    if stats["latest"]
                    else None,
                }
                for ep, stats in endpoint_stats.items()
            }

            pond_metadata["layers"][layer] = layer_data
            pond_metadata["total_files"] += layer_data["file_count"]
            pond_metadata["total_size_bytes"] += layer_data["size_bytes"]

            # Aggregate endpoint stats across layers
            for ep, stats in layer_data["endpoints"].items():
                if ep not in pond_metadata["endpoints"]:
                    pond_metadata["endpoints"][ep] = {
                        "file_count": 0,
                        "size_mb": 0,
                        "latest_ingestion": None,
                    }
                pond_metadata["endpoints"][ep]["file_count"] += stats["file_count"]
                pond_metadata["endpoints"][ep]["size_mb"] += stats["size_mb"]

                # Update latest timestamp
                if stats["latest_ingestion"]:
                    if (
                        pond_metadata["endpoints"][ep]["latest_ingestion"] is None
                        or stats["latest_ingestion"]
                        > pond_metadata["endpoints"][ep]["latest_ingestion"]
                    ):
                        pond_metadata["endpoints"][ep]["latest_ingestion"] = stats[
                            "latest_ingestion"
                        ]

        except Exception as e:
            print(f"    Error analyzing {layer} layer: {e}")
            layer_data["error"] = str(e)
            pond_metadata["layers"][layer] = layer_data

    # Calculate overall statistics
    pond_metadata["total_size_mb"] = round(
        pond_metadata["total_size_bytes"] / (1024 * 1024), 2
    )
    pond_metadata["total_size_gb"] = round(
        pond_metadata["total_size_bytes"] / (1024 * 1024 * 1024), 2
    )

    if all_timestamps:
        latest = max(all_timestamps)
        oldest = min(all_timestamps)
        pond_metadata["latest_ingestion"] = latest.isoformat()
        pond_metadata["oldest_ingestion"] = oldest.isoformat()

        # Calculate freshness (minutes since last update)
        now = datetime.now(timezone.utc)
        freshness_minutes = int((now - latest).total_seconds() / 60)
        pond_metadata["freshness_minutes"] = freshness_minutes

        if freshness_minutes < 30:
            pond_metadata["freshness_status"] = "excellent"
        elif freshness_minutes < 120:
            pond_metadata["freshness_status"] = "good"
        elif freshness_minutes < 360:
            pond_metadata["freshness_status"] = "moderate"
        else:
            pond_metadata["freshness_status"] = "stale"
    else:
        pond_metadata["status"] = "empty"
        pond_metadata["freshness_status"] = "no_data"

    return pond_metadata


def collect_all_metadata(profile=None):
    """Collect metadata for all ponds"""
    s3_client = get_s3_client(profile)

    print(f"\nCollecting metadata from S3 bucket: {BUCKET_NAME}")
    print("=" * 70)

    metadata = {
        "collection_timestamp": datetime.now(timezone.utc).isoformat(),
        "bucket": BUCKET_NAME,
        "ponds": {},
        "summary": {
            "total_ponds": len(PONDS),
            "total_files": 0,
            "total_size_mb": 0,
            "total_size_gb": 0,
            "active_ponds": 0,
            "total_endpoints": 0,
        },
    }

    for pond in PONDS:
        pond_data = analyze_pond(s3_client, BUCKET_NAME, pond)
        metadata["ponds"][pond] = pond_data

        # Update summary
        metadata["summary"]["total_files"] += pond_data["total_files"]
        metadata["summary"]["total_size_mb"] += pond_data["total_size_mb"]
        metadata["summary"]["total_size_gb"] += pond_data.get("total_size_gb", 0)

        if pond_data["status"] == "active":
            metadata["summary"]["active_ponds"] += 1

        metadata["summary"]["total_endpoints"] += len(pond_data["endpoints"])

    # Round summary values
    metadata["summary"]["total_size_mb"] = round(
        metadata["summary"]["total_size_mb"], 2
    )
    metadata["summary"]["total_size_gb"] = round(
        metadata["summary"]["total_size_gb"], 2
    )

    return metadata


def print_summary(metadata):
    """Print a human-readable summary"""
    print("\n" + "=" * 70)
    print("NOAA DATA LAKE METADATA SUMMARY")
    print("=" * 70)
    print(f"\nCollection Time: {metadata['collection_timestamp']}")
    print(f"\nTotal Ponds: {metadata['summary']['total_ponds']}")
    print(f"Active Ponds: {metadata['summary']['active_ponds']}")
    print(f"Total Files: {metadata['summary']['total_files']:,}")
    print(
        f"Total Size: {metadata['summary']['total_size_gb']:.2f} GB ({metadata['summary']['total_size_mb']:.2f} MB)"
    )
    print(f"Total Endpoints: {metadata['summary']['total_endpoints']}")

    print("\n" + "-" * 70)
    print("POND DETAILS")
    print("-" * 70)

    for pond_name, pond_data in metadata["ponds"].items():
        print(f"\n{pond_name.upper()} Pond:")
        print(f"  Status: {pond_data['status']}")
        print(f"  Files: {pond_data['total_files']:,}")
        print(f"  Size: {pond_data['total_size_mb']:.2f} MB")
        print(f"  Endpoints: {len(pond_data['endpoints'])}")

        if pond_data.get("latest_ingestion"):
            print(f"  Latest Ingestion: {pond_data['latest_ingestion']}")
            print(
                f"  Freshness: {pond_data.get('freshness_minutes', 0)} minutes ago ({pond_data.get('freshness_status', 'unknown')})"
            )

        if pond_data["endpoints"]:
            print(f"  Active Endpoints:")
            for endpoint, ep_data in list(pond_data["endpoints"].items())[:5]:
                print(
                    f"    - {endpoint}: {ep_data['file_count']} files, {ep_data['size_mb']:.2f} MB"
                )
            if len(pond_data["endpoints"]) > 5:
                print(f"    ... and {len(pond_data['endpoints']) - 5} more")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Collect metadata about NOAA Data Lake ponds from S3"
    )
    parser.add_argument(
        "--profile",
        default="noaa-target",
        help="AWS profile to use (default: noaa-target)",
    )
    parser.add_argument(
        "--output",
        default="pond_metadata.json",
        help="Output JSON file (default: pond_metadata.json)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress console output")

    args = parser.parse_args()

    try:
        # Collect metadata
        metadata = collect_all_metadata(args.profile)

        # Save to file
        with open(args.output, "w") as f:
            json.dump(metadata, f, indent=2)

        if not args.quiet:
            print_summary(metadata)
            print(f"\nMetadata saved to: {args.output}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
