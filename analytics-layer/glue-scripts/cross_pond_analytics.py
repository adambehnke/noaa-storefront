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

print(f"Running cross-pond analytics for {args['ENVIRONMENT']}")

# Read from multiple ponds
atmospheric_df = spark.read.parquet(f"s3://{args['DATA_LAKE_BUCKET']}/gold/atmospheric/")
oceanic_df = spark.read.parquet(f"s3://{args['DATA_LAKE_BUCKET']}/gold/oceanic/")

# Join on common fields (time, location)
cross_df = atmospheric_df.alias('atm').join(
    oceanic_df.alias('oc'),
    (F.col('atm.observation_time') == F.col('oc.observation_time')) &
    (F.col('atm.latitude') == F.col('oc.latitude')) &
    (F.col('atm.longitude') == F.col('oc.longitude')),
    'inner'
)

# Calculate correlations
correlations = cross_df.select(
    F.corr('atm.temperature', 'oc.water_temperature').alias('temp_correlation'),
    F.corr('atm.pressure', 'oc.water_level').alias('pressure_water_correlation')
)

# Write results
cross_df.write.mode('overwrite') \
    .parquet(f"s3://{args['DATA_LAKE_BUCKET']}/analytics/cross-pond/")

job.commit()
