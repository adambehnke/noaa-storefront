import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'DATA_LAKE_BUCKET', 'ANALYTICS_DATABASE', 'ENVIRONMENT'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print(f"Running daily aggregation for {args['ENVIRONMENT']}")

# Read hourly aggregates
hourly_df = spark.read.parquet(f"s3://{args['DATA_LAKE_BUCKET']}/analytics/hourly/")

# Aggregate by day
daily_df = hourly_df.groupBy(
    F.date_trunc('day', F.col('aggregation_hour')).alias('aggregation_date'),
    'pond_name'
).agg(
    F.sum('record_count').alias('record_count'),
    F.avg('avg_value').alias('avg_value'),
    F.min('min_value').alias('min_value'),
    F.max('max_value').alias('max_value'),
    F.avg('std_dev').alias('std_dev'),
    F.expr('percentile_approx(avg_value, 0.25)').alias('percentile_25'),
    F.expr('percentile_approx(avg_value, 0.50)').alias('percentile_50'),
    F.expr('percentile_approx(avg_value, 0.75)').alias('percentile_75')
)

# Write to analytics layer
daily_df.write.mode('append').partitionBy('pond_name') \
    .parquet(f"s3://{args['DATA_LAKE_BUCKET']}/analytics/daily/")

job.commit()
