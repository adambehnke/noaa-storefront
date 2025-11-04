import sys, os, json, boto3, requests
from datetime import datetime
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'LAKE_BUCKET', 'ENV'])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

url = "https://api.weather.gov/alerts/active"
resp = requests.get(url, timeout=15)
data = resp.json().get("features", [])

bronze_path = f"s3://{args['LAKE_BUCKET']}/bronze/raw_nws/"
s3 = boto3.client("s3")
key = f"bronze/raw_nws/alerts_{datetime.utcnow().isoformat()}.json"
s3.put_object(Bucket=args['LAKE_BUCKET'], Key=key, Body=json.dumps(data))

job.commit()

