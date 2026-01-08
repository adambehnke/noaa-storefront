#!/bin/bash
###############################################################################
# NOAA Federated Data Lake - Enhanced Features Deployment Script
#
# This script deploys three major enhancements:
# 1. Real-time streaming infrastructure (Kinesis)
# 2. Advanced analytics layer (Glue, Athena)
# 3. QuickSight dashboards
#
# Usage:
#   ./deploy_enhancements.sh [streaming|analytics|quicksight|all]
#
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source environment configuration
if [ -f "${SCRIPT_DIR}/config/environment.sh" ]; then
    source "${SCRIPT_DIR}/config/environment.sh"
else
    echo -e "${RED}Error: environment.sh not found${NC}"
    exit 1
fi

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if stack exists
stack_exists() {
    local stack_name=$1
    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        >/dev/null 2>&1
}

# Wait for stack operation to complete
wait_for_stack() {
    local stack_name=$1
    local operation=$2

    log_info "Waiting for ${operation} to complete for ${stack_name}..."

    aws cloudformation wait "stack-${operation}-complete" \
        --stack-name "${stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}"

    if [ $? -eq 0 ]; then
        log_success "${operation} completed for ${stack_name}"
        return 0
    else
        log_error "${operation} failed for ${stack_name}"
        return 1
    fi
}

# Deploy CloudFormation stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local parameters=$3

    log_info "Deploying stack: ${stack_name}"
    log_info "Template: ${template_file}"

    if [ ! -f "${template_file}" ]; then
        log_error "Template file not found: ${template_file}"
        return 1
    fi

    # Check if stack exists
    if stack_exists "${stack_name}"; then
        log_info "Stack exists. Updating..."

        aws cloudformation update-stack \
            --stack-name "${stack_name}" \
            --template-body "file://${template_file}" \
            --parameters ${parameters} \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" \
            --tags Key=Environment,Value=${ENVIRONMENT} \
                   Key=Project,Value=NOAA-Federated-Lake \
                   Key=ManagedBy,Value=CloudFormation \
            2>&1 | tee /tmp/stack-output.txt

        if grep -q "No updates are to be performed" /tmp/stack-output.txt; then
            log_warning "No updates needed for ${stack_name}"
            return 0
        fi

        wait_for_stack "${stack_name}" "update"
    else
        log_info "Stack does not exist. Creating..."

        aws cloudformation create-stack \
            --stack-name "${stack_name}" \
            --template-body "file://${template_file}" \
            --parameters ${parameters} \
            --capabilities CAPABILITY_NAMED_IAM \
            --profile "${AWS_PROFILE}" \
            --region "${AWS_REGION}" \
            --tags Key=Environment,Value=${ENVIRONMENT} \
                   Key=Project,Value=NOAA-Federated-Lake \
                   Key=ManagedBy,Value=CloudFormation

        wait_for_stack "${stack_name}" "create"
    fi

    return $?
}

# Get stack outputs
get_stack_output() {
    local stack_name=$1
    local output_key=$2

    aws cloudformation describe-stacks \
        --stack-name "${stack_name}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text
}

###############################################################################
# Deployment Functions
###############################################################################

deploy_streaming() {
    log_info "===== Deploying Real-Time Streaming Infrastructure ====="

    local stack_name="noaa-streaming-${ENVIRONMENT}"
    local template_file="${SCRIPT_DIR}/real-time-streaming/streaming-infrastructure.yaml"

    local parameters="ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
                     ParameterKey=AccountId,ParameterValue=${AWS_ACCOUNT_ID} \
                     ParameterKey=DataLakeBucket,ParameterValue=${DATA_LAKE_BUCKET} \
                     ParameterKey=ShardCount,ParameterValue=2 \
                     ParameterKey=RetentionHours,ParameterValue=24"

    if deploy_stack "${stack_name}" "${template_file}" "${parameters}"; then
        log_success "Streaming infrastructure deployed successfully"

        # Display outputs
        log_info "Stream ARNs:"
        echo "  Atmospheric: $(get_stack_output ${stack_name} AtmosphericStreamArn)"
        echo "  Oceanic: $(get_stack_output ${stack_name} OceanicStreamArn)"
        echo "  Buoy: $(get_stack_output ${stack_name} BuoyStreamArn)"

        return 0
    else
        log_error "Failed to deploy streaming infrastructure"
        return 1
    fi
}

deploy_analytics() {
    log_info "===== Deploying Advanced Analytics Layer ====="

    local stack_name="noaa-analytics-${ENVIRONMENT}"
    local template_file="${SCRIPT_DIR}/analytics-layer/analytics-infrastructure.yaml"

    local parameters="ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
                     ParameterKey=AccountId,ParameterValue=${AWS_ACCOUNT_ID} \
                     ParameterKey=DataLakeBucket,ParameterValue=${DATA_LAKE_BUCKET} \
                     ParameterKey=AthenaResultsBucket,ParameterValue=${ATHENA_RESULTS_BUCKET}"

    # First, upload Glue ETL scripts
    log_info "Uploading Glue ETL scripts..."
    upload_glue_scripts

    if deploy_stack "${stack_name}" "${template_file}" "${parameters}"; then
        log_success "Analytics layer deployed successfully"

        # Display outputs
        log_info "Analytics Resources:"
        echo "  Analytics Database: $(get_stack_output ${stack_name} AnalyticsDatabaseName)"
        echo "  ML Database: $(get_stack_output ${stack_name} MLDatabaseName)"
        echo "  Analytics Workgroup: $(get_stack_output ${stack_name} AnalyticsWorkgroupName)"

        return 0
    else
        log_error "Failed to deploy analytics layer"
        return 1
    fi
}

deploy_quicksight() {
    log_info "===== Deploying QuickSight Dashboards ====="

    # Check if QuickSight is enabled
    if ! aws quicksight describe-account-subscription \
        --aws-account-id "${AWS_ACCOUNT_ID}" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        >/dev/null 2>&1; then
        log_error "QuickSight is not enabled in this account"
        log_info "Please enable QuickSight first: https://quicksight.aws.amazon.com/"
        return 1
    fi

    # Get QuickSight username
    local quicksight_user=$(aws quicksight list-users \
        --aws-account-id "${AWS_ACCOUNT_ID}" \
        --namespace default \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --query 'UserList[0].UserName' \
        --output text)

    if [ -z "${quicksight_user}" ]; then
        log_warning "No QuickSight users found. Using default 'admin' username."
        quicksight_user="admin"
    fi

    local stack_name="noaa-quicksight-${ENVIRONMENT}"
    local template_file="${SCRIPT_DIR}/quicksight-dashboards/quicksight-infrastructure.yaml"

    local parameters="ParameterKey=Environment,ParameterValue=${ENVIRONMENT} \
                     ParameterKey=AccountId,ParameterValue=${AWS_ACCOUNT_ID} \
                     ParameterKey=DataLakeBucket,ParameterValue=${DATA_LAKE_BUCKET} \
                     ParameterKey=AthenaResultsBucket,ParameterValue=${ATHENA_RESULTS_BUCKET} \
                     ParameterKey=QuickSightUsername,ParameterValue=${quicksight_user} \
                     ParameterKey=GoldDatabase,ParameterValue=${GOLD_DATABASE} \
                     ParameterKey=AnalyticsDatabase,ParameterValue=noaa_analytics_${ENVIRONMENT}"

    if deploy_stack "${stack_name}" "${template_file}" "${parameters}"; then
        log_success "QuickSight dashboards deployed successfully"

        # Display outputs
        log_info "QuickSight Resources:"
        echo "  Dashboard URL: $(get_stack_output ${stack_name} DashboardURL)"
        echo "  Operational Dashboard: $(get_stack_output ${stack_name} OperationalDashboardId)"
        echo "  Analytics Dashboard: $(get_stack_output ${stack_name} AnalyticsDashboardId)"

        return 0
    else
        log_error "Failed to deploy QuickSight dashboards"
        return 1
    fi
}

upload_glue_scripts() {
    log_info "Uploading Glue ETL scripts to S3..."

    local scripts_dir="${SCRIPT_DIR}/analytics-layer/glue-scripts"

    # Create Glue scripts directory if it doesn't exist
    mkdir -p "${scripts_dir}"

    # Create placeholder scripts (these will be replaced with actual implementations)
    cat > "${scripts_dir}/hourly_aggregation.py" << 'EOF'
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
EOF

    cat > "${scripts_dir}/daily_aggregation.py" << 'EOF'
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
EOF

    cat > "${scripts_dir}/ml_feature_engineering.py" << 'EOF'
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
EOF

    cat > "${scripts_dir}/cross_pond_analytics.py" << 'EOF'
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
EOF

    # Upload scripts to S3
    aws s3 sync "${scripts_dir}" "s3://${DATA_LAKE_BUCKET}/glue-scripts/" \
        --profile "${AWS_PROFILE}" \
        --region "${AWS_REGION}" \
        --exclude "*.pyc" \
        --exclude "__pycache__/*"

    log_success "Glue ETL scripts uploaded successfully"
}

###############################################################################
# Validation Functions
###############################################################################

validate_prerequisites() {
    log_info "Validating prerequisites..."

    local errors=0

    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        ((errors++))
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity --profile "${AWS_PROFILE}" >/dev/null 2>&1; then
        log_error "Cannot authenticate with AWS profile: ${AWS_PROFILE}"
        ((errors++))
    fi

    # Check if data lake bucket exists
    if ! aws s3 ls "s3://${DATA_LAKE_BUCKET}" --profile "${AWS_PROFILE}" >/dev/null 2>&1; then
        log_error "Data lake bucket does not exist: ${DATA_LAKE_BUCKET}"
        ((errors++))
    fi

    # Check if Athena results bucket exists
    if ! aws s3 ls "s3://${ATHENA_RESULTS_BUCKET}" --profile "${AWS_PROFILE}" >/dev/null 2>&1; then
        log_error "Athena results bucket does not exist: ${ATHENA_RESULTS_BUCKET}"
        ((errors++))
    fi

    if [ $errors -eq 0 ]; then
        log_success "Prerequisites validation passed"
        return 0
    else
        log_error "Prerequisites validation failed with ${errors} error(s)"
        return 1
    fi
}

###############################################################################
# Main Execution
###############################################################################

print_banner() {
    echo ""
    echo "============================================================"
    echo "  NOAA Federated Data Lake - Enhanced Features Deployment"
    echo "============================================================"
    echo ""
    echo "  Account:     ${AWS_ACCOUNT_ID}"
    echo "  Profile:     ${AWS_PROFILE}"
    echo "  Region:      ${AWS_REGION}"
    echo "  Environment: ${ENVIRONMENT}"
    echo ""
    echo "============================================================"
    echo ""
}

print_usage() {
    echo "Usage: $0 [streaming|analytics|quicksight|all]"
    echo ""
    echo "Components:"
    echo "  streaming   - Deploy real-time streaming infrastructure"
    echo "  analytics   - Deploy advanced analytics layer"
    echo "  quicksight  - Deploy QuickSight dashboards"
    echo "  all         - Deploy all components"
    echo ""
}

main() {
    local component=${1:-all}

    print_banner

    # Validate prerequisites
    if ! validate_prerequisites; then
        log_error "Prerequisites check failed. Please fix the errors and try again."
        exit 1
    fi

    case "${component}" in
        streaming)
            deploy_streaming
            ;;
        analytics)
            deploy_analytics
            ;;
        quicksight)
            deploy_quicksight
            ;;
        all)
            log_info "Deploying all enhancement components..."

            if deploy_streaming; then
                log_success "✓ Streaming infrastructure deployed"
            else
                log_error "✗ Streaming infrastructure failed"
                exit 1
            fi

            if deploy_analytics; then
                log_success "✓ Analytics layer deployed"
            else
                log_error "✗ Analytics layer failed"
                exit 1
            fi

            if deploy_quicksight; then
                log_success "✓ QuickSight dashboards deployed"
            else
                log_warning "✗ QuickSight dashboards failed (this is optional)"
            fi

            log_success "All enhancements deployed successfully!"
            ;;
        *)
            log_error "Unknown component: ${component}"
            print_usage
            exit 1
            ;;
    esac

    echo ""
    log_success "Deployment completed!"
    echo ""
}

# Run main function
main "$@"
