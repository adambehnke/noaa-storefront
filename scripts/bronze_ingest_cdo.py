import sys, os, json, boto3, requests
from datetime import datetime, timedelta
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from pyspark.context import SparkContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'LAKE_BUCKET', 'ENV'])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

API_KEY = os.environ.get('NOAA_CDO_TOKEN')
ENDPOINT = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
headers = {'token': API_KEY}
params = {
    "datasetid": "GHCND",
    "locationid": "CITY:US480019",
    "startdate": (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d'),
    "enddate": datetime.utcnow().strftime('%Y-%m-%d'),
    "limit": 100
}
resp = requests.get(ENDPOINT, headers=headers, params=params)
data = resp.json().get("results", [])

bronze_path = f"s3://{args['LAKE_BUCKET']}/bronze/raw_cdo/"
s3 = boto3.client("s3")
key = f"bronze/raw_cdo/data_{datetime.utcnow().isoformat()}.json"
s3.put_object(Bucket=args['LAKE_BUCKET'], Key=key, Body=json.dumps(data))

job.commit()

