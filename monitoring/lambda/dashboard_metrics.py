import json
from datetime import datetime, timedelta

import boto3

s3 = boto3.client("s3")
BUCKET = "noaa-federated-lake-899626030376-dev"


def lambda_handler(event, context):
    """
    Dashboard metrics Lambda - Returns pond statistics and recent data samples.
    Lambda Function URL handles CORS automatically - no CORS headers needed.
    """
    params = event.get("queryStringParameters", {}) or {}
    pond = params.get("pond_name", "")

    if not pond:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "pond_name required"}),
        }

    recent_data = []
    total_files_today = 0
    total_files_yesterday = 0

    # Discover what product types exist for this pond
    try:
        result = s3.list_objects_v2(
            Bucket=BUCKET, Prefix=f"bronze/{pond}/", Delimiter="/"
        )
        products = [
            p["Prefix"].split("/")[-2] for p in result.get("CommonPrefixes", [])
        ]
    except Exception as e:
        print(f"Error discovering products: {e}")
        products = []

    if not products:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "pond_name": pond,
                    "recent_data": [],
                    "products_found": [],
                    "total_files": 0,
                    "total_files_today": 0,
                    "total_files_yesterday": 0,
                    "error": "No products found",
                }
            ),
        }

    # Get today and yesterday's dates
    today = datetime.utcnow()
    yesterday = today - timedelta(days=1)

    today_year, today_month, today_day = (
        today.strftime("%Y"),
        today.strftime("%m"),
        today.strftime("%d"),
    )
    yesterday_year, yesterday_month, yesterday_day = (
        yesterday.strftime("%Y"),
        yesterday.strftime("%m"),
        yesterday.strftime("%d"),
    )

    # Count files and get samples for each product
    for product in products:
        # Count today's files
        today_prefix = f"bronze/{pond}/{product}/year={today_year}/month={today_month}/day={today_day}/"
        try:
            paginator = s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=BUCKET, Prefix=today_prefix)

            for page in page_iterator:
                if "Contents" in page:
                    # Count all files
                    total_files_today += len(page["Contents"])

                    # Get samples from first page only
                    if len(recent_data) < 5:
                        files = sorted(
                            page["Contents"],
                            key=lambda x: x["LastModified"],
                            reverse=True,
                        )

                        for file in files[:2]:
                            if len(recent_data) >= 5:
                                break
                            if file["Key"].endswith(".json") and file["Size"] < 1000000:
                                try:
                                    obj = s3.get_object(Bucket=BUCKET, Key=file["Key"])
                                    content = json.loads(obj["Body"].read())
                                    if isinstance(content, list):
                                        content = content[0] if content else {}

                                    recent_data.append(
                                        {
                                            "key": file["Key"],
                                            "size": file["Size"],
                                            "last_modified": file[
                                                "LastModified"
                                            ].isoformat(),
                                            "data": content,
                                        }
                                    )
                                except Exception as e:
                                    print(f"Error reading sample file: {e}")
                                    pass
        except Exception as e:
            print(f"Error processing today's files for {product}: {e}")

        # Count yesterday's files for comparison
        yesterday_prefix = f"bronze/{pond}/{product}/year={yesterday_year}/month={yesterday_month}/day={yesterday_day}/"
        try:
            paginator = s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=BUCKET, Prefix=yesterday_prefix)

            for page in page_iterator:
                if "Contents" in page:
                    total_files_yesterday += len(page["Contents"])
        except Exception as e:
            print(f"Error processing yesterday's files for {product}: {e}")

    # Calculate growth
    growth = total_files_today - total_files_yesterday
    growth_pct = (
        (growth / total_files_yesterday * 100) if total_files_yesterday > 0 else 0
    )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "pond_name": pond,
                "recent_data": recent_data,
                "products_found": products,
                "total_files": total_files_today,
                "total_files_today": total_files_today,
                "total_files_yesterday": total_files_yesterday,
                "growth": growth,
                "growth_percentage": round(growth_pct, 1),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
    }
