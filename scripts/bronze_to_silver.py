import sys, json, boto3
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.job import Job
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'LAKE_BUCKET', 'ENV'])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

bronze_path = f"s3://{args['LAKE_BUCKET']}/bronze/raw_weather/"
silver_path = f"s3://{args['LAKE_BUCKET']}/silver/cleaned_weather/"

df = glueContext.create_dynamic_frame.from_options("s3", {"paths": [bronze_path]}, "json")
df = df.drop_fields(['humidity'])
glueContext.write_dynamic_frame.from_options(frame=df, connection_type="s3",
    connection_options={"path": silver_path}, format="json")
job.commit()

