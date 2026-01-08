import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'DATA_LAKE_BUCKET', 'ML_DATABASE', 'ENVIRONMENT'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print(f"Running ML feature engineering for {args['ENVIRONMENT']}")

# Read from Gold layer
df = spark.read.parquet(f"s3://{args['DATA_LAKE_BUCKET']}/gold/")

# Create time-based features
window_7d = Window.partitionBy('station_id').orderBy('observation_time').rowsBetween(-168, 0)
window_1d = Window.partitionBy('station_id').orderBy('observation_time').rowsBetween(-24, 0)

features_df = df.withColumn('rolling_avg_7d', F.avg('value').over(window_7d)) \
    .withColumn('rolling_avg_1d', F.avg('value').over(window_1d)) \
    .withColumn('rolling_std_7d', F.stddev('value').over(window_7d)) \
    .withColumn('hour_of_day', F.hour('observation_time')) \
    .withColumn('day_of_week', F.dayofweek('observation_time')) \
    .withColumn('month', F.month('observation_time'))

# Write ML features
features_df.write.mode('overwrite').partitionBy('year', 'month') \
    .parquet(f"s3://{args['DATA_LAKE_BUCKET']}/ml-datasets/features/")

job.commit()
