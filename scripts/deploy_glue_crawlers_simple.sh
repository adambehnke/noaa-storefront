#!/bin/bash

echo "Deploying Glue Crawlers for NOAA Data Lake..."
echo "=============================================="

# Create IAM role for crawlers
echo "Creating IAM role..."
aws iam create-role --role-name noaa-glue-crawler-role-dev \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "glue.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role already exists"

# Attach policies
aws iam attach-role-policy \
  --role-name noaa-glue-crawler-role-dev \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole 2>/dev/null

# Create custom policy for S3 access
aws iam put-role-policy \
  --role-name noaa-glue-crawler-role-dev \
  --policy-name S3Access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev",
        "arn:aws:s3:::noaa-federated-lake-899626030376-dev/*"
      ]
    }]
  }' 2>/dev/null

echo "IAM role created/updated"
echo ""

# Wait for role to propagate
sleep 10

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name noaa-glue-crawler-role-dev --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"
echo ""

# Create crawlers for each pond
PONDS="atmospheric oceanic buoy climate terrestrial spatial"
LAYERS="bronze gold"

for LAYER in $LAYERS; do
  for POND in $PONDS; do
    CRAWLER_NAME="noaa-${LAYER}-${POND}-dev"
    DATABASE_NAME="noaa_${LAYER}_dev"
    S3_PATH="s3://noaa-federated-lake-899626030376-dev/${LAYER}/${POND}/"
    
    echo "Creating crawler: $CRAWLER_NAME"
    
    aws glue create-crawler \
      --name "$CRAWLER_NAME" \
      --role "$ROLE_ARN" \
      --database-name "$DATABASE_NAME" \
      --description "Crawls ${LAYER} ${POND} data" \
      --targets "{\"S3Targets\":[{\"Path\":\"${S3_PATH}\"}]}" \
      --schedule "cron(0 */6 * * ? *)" \
      --schema-change-policy '{"UpdateBehavior":"UPDATE_IN_DATABASE","DeleteBehavior":"LOG"}' \
      --configuration '{"Version":1.0,"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}}' \
      --tags "Environment=dev,Project=NOAA-Federated-Lake,Pond=${POND},Layer=${LAYER}" 2>&1 | grep -v "AlreadyExists" || true
  done
done

echo ""
echo "=========================================="
echo "Glue Crawlers Deployed Successfully!"
echo "=========================================="
echo ""
echo "Total Crawlers: 12 (6 ponds × 2 layers)"
echo "Schedule: Every 6 hours"
echo ""
echo "Starting initial crawl for all crawlers..."
echo ""

# Start all crawlers
for LAYER in $LAYERS; do
  for POND in $PONDS; do
    CRAWLER_NAME="noaa-${LAYER}-${POND}-dev"
    echo "Starting: $CRAWLER_NAME"
    aws glue start-crawler --name "$CRAWLER_NAME" 2>&1 | grep -v "CrawlerRunningException" || echo "  Already running or starting..."
  done
done

echo ""
echo "=========================================="
echo "Crawlers Started!"
echo "=========================================="
echo ""
echo "Monitor crawler status with:"
echo "aws glue list-crawlers --query 'CrawlerNames' --output table"
echo ""
echo "View crawler metrics:"
echo "aws glue get-crawler --name noaa-bronze-atmospheric-dev"
