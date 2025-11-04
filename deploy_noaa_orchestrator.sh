#!/bin/bash
set -e
echo "🚀 Deploying NOAA Federated Medallion Pipeline..."
aws cloudformation deploy --template-file noaa-datalake.yaml --stack-name noaa-datalake-dev --capabilities CAPABILITY_IAM
aws cloudformation deploy --template-file noaa-ai-pipeline.yaml --stack-name noaa-ai-pipeline-dev --capabilities CAPABILITY_IAM
aws cloudformation deploy --template-file noaa-ai-query.yaml --stack-name noaa-ai-query-dev --capabilities CAPABILITY_IAM
aws stepfunctions create-state-machine \
  --name noaa-medallion-orchestrator-dev \
  --definition file://noaa_medallion_pipeline.asl.json \
  --role-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/noaa-etl-role-dev \
  --region us-east-1 || echo "State machine exists, updating..."
aws events put-rule --name noaa-pipeline-schedule-dev --schedule-expression "rate(6 hours)"
echo "✅ Deployment complete."

