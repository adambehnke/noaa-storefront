#!/usr/bin/env python3
"""
Lambda Function for NDBC Buoy Data Ingestion
Triggered by EventBridge schedule to ingest buoy observations
"""

import json
import logging
import subprocess
import sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Lambda wrapper for buoy ingestion"""
    env = event.get("env", "dev")
    stations = event.get("stations", None)  # Optional: specific stations

    try:
        # Build command
        cmd = [sys.executable, "buoy_ingest.py", "--env", env]

        if stations:
            cmd.extend(["--stations"] + stations)

        logger.info(f"Starting buoy ingestion with command: {' '.join(cmd)}")

        # Run the ingestion script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd="/var/task",
        )

        logger.info(f"Script stdout: {result.stdout}")

        if result.stderr:
            logger.warning(f"Script stderr: {result.stderr}")

        if result.returncode == 0:
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Buoy data ingestion completed successfully",
                        "env": env,
                        "stations_requested": stations,
                        "output": result.stdout[-500:] if result.stdout else "",
                    }
                ),
            }
        else:
            logger.error(f"Script failed with return code: {result.returncode}")
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "message": "Buoy data ingestion failed",
                        "error": result.stderr[-500:]
                        if result.stderr
                        else "Unknown error",
                        "returncode": result.returncode,
                    }
                ),
            }

    except subprocess.TimeoutExpired:
        logger.error("Ingestion script timed out after 5 minutes")
        return {
            "statusCode": 504,
            "body": json.dumps(
                {
                    "message": "Buoy data ingestion timed out",
                    "error": "Script execution exceeded 5 minutes",
                }
            ),
        }

    except Exception as e:
        logger.exception("Error running buoy ingestion")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": "Buoy data ingestion error", "error": str(e)}
            ),
        }


# For local testing
if __name__ == "__main__":
    test_event = {"env": "dev"}
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
