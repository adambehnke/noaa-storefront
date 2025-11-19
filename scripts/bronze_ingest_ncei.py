import sys, boto3, json
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

source_bucket = "noaa-ghcn-pds"
s3 = boto3.client("s3")
prefix = "csv/2025/"

objects = s3.list_objects_v2(Bucket=source_bucket, Prefix=prefix, MaxKeys=3)
records = []
for o in objects.get("Contents", []):
    records.append({"key": o["Key"], "size": o["Size"]})

target = f"bronze/raw_ncei/index_{datetime.utcnow().isoformat()}.json"
s3.put_object(Bucket=args['LAKE_BUCKET'], Key=target, Body=json.dumps(records))
job.commit()

