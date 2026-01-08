import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from datetime import datetime, timedelta

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'DATA_LAKE_BUCKET', 'ANALYTICS_DATABASE', 'ENVIRONMENT'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Hourly aggregation logic
print(f"Running hourly aggregation for {args['ENVIRONMENT']}")

# Read from Gold layer
ponds = ['atmospheric', 'oceanic', 'buoy', 'climate', 'terrestrial', 'spatial']

for pond in ponds:
    try:
        print(f"Processing pond: {pond}")
        df = spark.read.parquet(f"s3://{args['DATA_LAKE_BUCKET']}/gold/{pond}/")

        # Aggregate by hour
        hourly_df = df.groupBy(
            F.date_trunc('hour', F.col('observation_time')).alias('aggregation_hour'),
            F.lit(pond).alias('pond_name')
        ).agg(
            F.count('*').alias('record_count'),
            F.avg('value').alias('avg_value'),
            F.min('value').alias('min_value'),
            F.max('value').alias('max_value'),
            F.stddev('value').alias('std_dev')
        )

        # Write to analytics layer
        hourly_df.write.mode('append').partitionBy('pond_name') \
            .parquet(f"s3://{args['DATA_LAKE_BUCKET']}/analytics/hourly/")

        print(f"Completed aggregation for {pond}")

    except Exception as e:
        print(f"Error processing {pond}: {str(e)}")

job.commit()
