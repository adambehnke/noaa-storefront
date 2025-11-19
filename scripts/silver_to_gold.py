import sys, boto3
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.job import Job
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'LAKE_BUCKET', 'ENV'])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

silver_path = f"s3://{args['LAKE_BUCKET']}/silver/cleaned_weather/"
gold_path = f"s3://{args['LAKE_BUCKET']}/gold/analytics_weather/"

df = glueContext.create_dynamic_frame.from_options("s3", {"paths": [silver_path]}, "json")
df = df.drop_fields(['station'])
glueContext.write_dynamic_frame.from_options(frame=df, connection_type="s3",
    connection_options={"path": gold_path}, format="parquet")
job.commit()

